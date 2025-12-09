import os
import json
import shutil
import requests
import re
import numpy as np
import easyocr 
from pdf2image import convert_from_path 
from bs4 import BeautifulSoup
from urllib.parse import urljoin 
from langchain_community.document_loaders import WikipediaLoader, WebBaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from tqdm import tqdm
import torch

# --- CONFIGURATION ---
DB_PATH = "bmw_knowledge_db_rag"
DATA_PATH = "bmw_rag_data"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# 1980s-2000s focus list
# order matters! longer matches first
FOCUS_CARS = [
    "E24", "E28", "E30", "E31", "E32", "E34", 
    "E36-7", "E36-8", "E36", 
    "E38", "E39", "E46", 
    "E52", "E53", "E83", 
    "Z1", "Z3", "Z8"
]

# --- NEW: CHASSIS INFERENCE LOGIC ---
class ChassisInferrer:
    def __init__(self):
        # Define production years for US models (Approximate)
        self.ranges = {
            "3-Series": [
                (1984, 1991, "E30"), # 1992/93 convertibles are E30 too, but 92 sedan is E36. Overlap is tricky.
                (1992, 1999, "E36"),
                (1999, 2006, "E46")
            ],
            "5-Series": [
                (1982, 1988, "E28"),
                (1989, 1995, "E34"),
                (1996, 2003, "E39") # 1996 was a gap year in US, but E39 globally
            ],
            "7-Series": [
                (1988, 1994, "E32"),
                (1995, 2001, "E38")
            ],
            "8-Series": [
                (1990, 1999, "E31")
            ],
            "Z-Series": [
                (1989, 1991, "Z1"),
                (1996, 2002, "Z3"), # Covers E36-7
                (2000, 2003, "Z8")  # E52
            ],
            "X-Series": [
                (2000, 2006, "E53"), # X5
                (2004, 2010, "E83")  # X3
            ]
        }

    def infer(self, text):
        """
        Takes a string like "1989 BMW 325i Repair Manual" 
        and returns "E30".
        """
        text = text.upper()
        
        # 1. Extract Year
        year_match = re.search(r'\b(19[89]\d|200\d)\b', text) # Matches 1980-2009
        if not year_match:
            return None
        year = int(year_match.group(1))

        # 2. Identify Series based on Model Name patterns
        series = None
        
        # 3-Series Patterns: "325i", "318is", "M3"
        if re.search(r'\b3\d\d[idtxi]*\b', text) or "M3" in text or "3-SERIES" in text:
            series = "3-Series"
        
        # 5-Series Patterns: "525i", "535i", "M5"
        elif re.search(r'\b5\d\d[idtxi]*\b', text) or "M5" in text or "5-SERIES" in text:
            series = "5-Series"
            
        # 7-Series Patterns
        elif re.search(r'\b7\d\d[il]*\b', text) or "7-SERIES" in text:
            series = "7-Series"

        # 8-Series
        elif "850" in text or "840" in text or "8-SERIES" in text:
            series = "8-Series"

        # Z3/Z8
        elif "Z3" in text or "M ROADSTER" in text or "M COUPE" in text:
            series = "Z-Series"
            return "Z3" # Shortcut for Z3 since year range is tight
        elif "Z8" in text:
            return "Z8"

        # X5
        elif "X5" in text:
            return "E53" if 2000 <= year <= 2006 else None
        elif "X3" in text:
            return "E83" if 2004 <= year <= 2010 else None

        # 3. Lookup Code based on Year
        if series and series in self.ranges:
            for start, end, code in self.ranges[series]:
                if start <= year <= end:
                    return code
        
        return None

# Initialize Inferrer
inferrer = ChassisInferrer()

# Load target models
if not os.path.exists('bmw_class_names.json'):
    raise FileNotFoundError("critical error! bmw_class_names.json not found")

with open('bmw_class_names.json', 'r') as f:
    class_map = json.load(f)
    all_models = list(class_map.values()) 

print(f"loaded {len(all_models)} total classes from json")

def get_matching_chassis(text_to_check):
    """
    Checks if a url or title contains a code (E30) OR implies one (1989 325i).
    """
    # 1. Explicit Check (Search for "E30")
    text_upper = text_to_check.upper()
    for code in FOCUS_CARS:
        if code.upper() in text_upper:
            return code
            
    # 2. Implicit Check (Search for "1989 325i")
    inferred_code = inferrer.infer(text_to_check)
    if inferred_code:
        return inferred_code
        
    return None

def is_focus_car(car_name):
    car_name_upper = car_name.upper()
    for code in FOCUS_CARS:
        if code in car_name_upper:
            return code 
    return None

# --- CRAWLER 1: FCP EURO ---
def scrape_fcp_index():
    found_articles = {} 
    base_url = "https://www.fcpeuro.com/blog/tag/bmw?page="
    
    print(f"\n crawling fcp euro blog (pages 1-36)...")
    
    for page in tqdm(range(1, 37), desc="scanning fcp blog"):
        try:
            r = requests.get(f"{base_url}{page}", timeout=5)
            if r.status_code != 200: continue
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/blog/' in href:
                    full_url = href if href.startswith('http') else f"https://www.fcpeuro.com{href}"
                    
                    # We check the URL text for clues
                    matched_code = get_matching_chassis(full_url)
                    
                    if matched_code:
                        found_articles[full_url] = matched_code
                        
        except Exception as e:
            print(f"  error on page {page}: {e}")
            
    print(f"  found {len(found_articles)} fcp articles!")
    return found_articles

# --- CRAWLER 2: PELICAN PARTS ---
def scrape_pelican_index():
    found_articles = {}
    master_url = "https://www.pelicanparts.com/bmw/techarticles/tech_main.htm"
    
    print(f"\n crawling pelican parts master list...")
    
    try:
        r = requests.get(master_url, timeout=10)
        if r.status_code != 200: 
            print("  failed to reach pelican master page")
            return {}

        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 1. find sub-index pages
        sub_pages = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text()
            
            # Check Text (e.g. "BMW 3-Series 1992-1999") for hidden codes
            code = get_matching_chassis(text) 
            if not code:
                # Also check the link itself
                code = get_matching_chassis(href)

            if code and "tech_main" in href:
                full_url = urljoin(master_url, href)
                sub_pages.add((full_url, code))
        
        print(f"  found {len(sub_pages)} chassis-specific sub-indexes. scanning them now...")

        # 2. scan each sub-page
        for sub_url, chassis_code in tqdm(sub_pages, desc="scanning pelican sub-pages"):
            try:
                sub_r = requests.get(sub_url, timeout=5)
                sub_soup = BeautifulSoup(sub_r.text, 'html.parser')
                
                for a in sub_soup.find_all('a', href=True):
                    href = a['href']
                    link_text = a.get_text() # e.g. "Replacing the Water Pump"
                    
                    # We only care about DIY articles
                    if "techarticles" in href and href.endswith(".htm") and "tech_main" not in href:
                        full_article_url = urljoin(sub_url, href)
                        
                        # Sometimes Pelican mixes E30 and E36 articles on the same page.
                        # Double check if the Article Title specific implies a different car
                        refined_code = get_matching_chassis(link_text)
                        
                        # Use refined code if found, otherwise use the page's main code
                        final_code = refined_code if refined_code else chassis_code
                        
                        found_articles[full_article_url] = final_code
                        
            except:
                continue

    except Exception as e:
        print(f"  pelican crawl failed: {e}")

    print(f"  found {len(found_articles)} pelican diy guides!")
    return found_articles

def build_smart_database():
    documents = []
    
    # --- PHASE 1: WIKI ---
    print("\n wiki time!")
    for model in tqdm(all_models, desc="scraping Wikipedia"):
        if "non_bmw" in model or "non_cars" in model:
            continue
        try:
            loader = WikipediaLoader(query=model.replace("_", " "), load_max_docs=1)
            wiki_docs = loader.load()
            for doc in wiki_docs:
                doc.metadata["car_model"] = model
                doc.metadata["source_type"] = "General History"
            documents.extend(wiki_docs)
        except:
            continue 

    # --- PHASE 2: WEB CRAWLERS ---
    print("\n unleashing the web crawlers!")
    
    fcp_articles = scrape_fcp_index()
    pelican_articles = scrape_pelican_index()
    
    all_web_articles = {**fcp_articles, **pelican_articles}
    
    if all_web_articles:
        urls = list(all_web_articles.keys())
        print(f"  downloading content from {len(urls)} total guides...")
        
        batch_size = 10
        for i in tqdm(range(0, len(urls), batch_size), desc="downloading"):
            batch_urls = urls[i:i+batch_size]
            try:
                loader = WebBaseLoader(batch_urls)
                loader.requests_per_second = 2
                web_docs = loader.load()
                
                for doc in web_docs:
                    url = doc.metadata.get('source', '')
                    code = fcp_articles.get(url) or pelican_articles.get(url) or "General"
                    
                    doc.metadata["car_model"] = code
                    doc.metadata["source_type"] = "Expert Guide" if "fcpeuro" in url else "Pelican DIY"
                    doc.page_content = doc.page_content.replace("\n", " ")
                
                documents.extend(web_docs)
            except Exception as e:
                print(f"  batch failed: {e}")

    # --- PHASE 3: PDF MANUALS (GPU OCR) ---
    print("\n checking local pdfs (activating AI vision eyes!)")
    print("  loading EasyOCR model into GPU memory...")
    reader = easyocr.Reader(['en'], gpu=True) 

    for model_name in all_models:
        if "non_bmw" in model_name or "non_cars" in model_name:
            continue
            
        model_folder = os.path.join(DATA_PATH, model_name)
        if os.path.exists(model_folder) and os.path.isdir(model_folder):
            
            pdf_files = [f for f in os.listdir(model_folder) if f.endswith('.pdf')]
            if not pdf_files: continue

            # TRY TO INFER CODE FROM FOLDER NAME FIRST
            folder_code = is_focus_car(model_name)
            
            # If folder name is vague ("Manuals"), infer from the PDF filename!
            if not folder_code: 
                 # Just use the first file to guess the folder content
                 folder_code = get_matching_chassis(pdf_files[0])
            
            if not folder_code: folder_code = model_name 

            print(f"  processing {len(pdf_files)} manuals for {folder_code}...")

            for pdf_file in pdf_files:
                pdf_path = os.path.join(model_folder, pdf_file)
                print(f"    reading {pdf_file}...")
                
                try:
                    images = convert_from_path(pdf_path)
                    full_text = ""
                    for i, img in enumerate(images):
                        result = reader.readtext(np.array(img), detail=0)
                        page_text = " ".join(result)
                        full_text += f" [Page {i+1}] {page_text}"
                    
                    new_doc = Document(
                        page_content=full_text,
                        metadata={
                            "car_model": folder_code,
                            "source_type": "Service Manual (EasyOCR)",
                            "filename": pdf_file
                        }
                    )
                    documents.append(new_doc)
                    print(f"    ✅ successfully read {pdf_file}")
                    
                except Exception as e:
                    print(f"    ❌ OCR failed on {pdf_file}: {e}")

    # --- FINAL BUILD ---
    print(f"\nTotal Documents: {len(documents)}")
    if not documents:
        print("no docs found! check your connection")
        return

    print("chunking and embedding!")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)
    
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)
        
    print("  loading embedding model to GPU...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_kwargs = {'device': device}
    encode_kwargs = {'normalize_embeddings': False}

    embedding_func = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )
    
    db = Chroma(persist_directory=DB_PATH, embedding_function=embedding_func)
    
    batch_size = 100
    for i in tqdm(range(0, len(splits), batch_size), desc="indexing"):
        db.add_documents(splits[i:i + batch_size])
        
    print(f"\n smart database ready! {DB_PATH}")

if __name__ == "__main__":
    build_smart_database()