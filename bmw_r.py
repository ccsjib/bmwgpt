import os
import json
import shutil
import requests
from langchain_community.document_loaders import WikipediaLoader, PyPDFLoader, DirectoryLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from tqdm import tqdm

# --- CONFIGURATION ---
DB_PATH = "bmw_knowledge_db_rag"
DATA_PATH = "rag_data"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# defining the focus cars (1980s-2000s)
# note: longer codes (e36-7) must come before shorter ones (e36) 
# to prevent partial match errors!
FOCUS_CARS = [
    "E24", "E28", "E30", "E31", "E32", "E34", 
    "E36-7", "E36-8", "E36", # z3 variants before standard e36
    "E38", "E39", "E46", 
    "E52", # z8
    "E53", # x5
    "E83", # x3
    "Z1"
]

# 1. load target models
if not os.path.exists('bmw_class_names.json'):
    raise FileNotFoundError("critical error! bmw_class_names.json not found")

with open('bmw_class_names.json', 'r') as f:
    class_map = json.load(f)
    all_models = list(class_map.values()) 

print(f"loaded {len(all_models)} total classes from json")

def is_focus_car(car_name):
    # normalize check
    car_name_upper = car_name.upper()
    for code in FOCUS_CARS:
        if code in car_name_upper:
            return code 
    return None

def get_fcp_url_slug(code):
    """
    translates technical chassis codes to fcp euro's url format.
    e.g. E52 -> z8, E36-7 -> z3, E83 -> x3
    """
    code = code.lower()
    
    # special handling for z-cars and x-cars where fcp uses the model name
    if code in ['e36-7', 'e36-8']:
        return 'z3'
    if code == 'e52':
        return 'z8'
    if code == 'e53':
        return 'x5' # sometimes fcp uses e53, sometimes x5-e53. 
    if code == 'e83':
        return 'x3'
    
    # default behavior (e30 -> e30)
    return code

def build_smart_database():
    documents = []
    
    scraped_fcp_codes = set()

    print("\n wiki time!")
    # scraping wiki for everything
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

    print("\n deep diving into focus cars (pdfs + fcp euro)!")
    
    for model_name in all_models:
        if "non_bmw" in model_name or "non_cars" in model_name:
            continue

        chassis_code = is_focus_car(model_name)
        
        if chassis_code:
            # 1. FCP EURO GUIDES (Web)
            # handle 'z3' deduplication (so we don't scrape z3 guide for e36-7 AND e36-8)
            url_slug = get_fcp_url_slug(chassis_code)
            
            if url_slug not in scraped_fcp_codes:
                print(f"  found new focus car: {chassis_code} (slug: {url_slug})! grabbing guides...")
                
                urls_to_try = [
                    f"https://blog.fcpeuro.com/bmw-{url_slug}-buyers-guide",
                    f"https://blog.fcpeuro.com/the-definitive-guide-to-the-bmw-{url_slug}",
                    f"https://blog.fcpeuro.com/most-common-bmw-{url_slug}-problems",
                    # sometimes they format it like "bmw-x5-e53"
                    f"https://blog.fcpeuro.com/bmw-{url_slug}-{chassis_code.lower()}-buyers-guide"
                ]
                
                valid_urls = []
                for url in urls_to_try:
                    try:
                        response = requests.head(url, timeout=3)
                        if response.status_code == 200:
                            valid_urls.append(url)
                    except:
                        pass
                
                if valid_urls:
                    print(f"     found {len(valid_urls)} fcp euro guides! scraping em...")
                    try:
                        loader = WebBaseLoader(valid_urls)
                        web_docs = loader.load()
                        for doc in web_docs:
                            # tag with original chassis code so filters work
                            doc.metadata["car_model"] = chassis_code 
                            doc.metadata["source_type"] = "FCP Euro Guide"
                            doc.page_content = doc.page_content.replace("\n", " ") 
                        documents.extend(web_docs)
                        
                        scraped_fcp_codes.add(url_slug)
                    except Exception as e:
                        print(f"     scraping failed: {e}")
            
            # 2. PDF MANUALS (Local)
            model_folder = os.path.join(DATA_PATH, model_name)
            
            if os.path.exists(model_folder) and os.path.isdir(model_folder):
                # check if empty
                if not os.listdir(model_folder):
                    continue

                print(f"     checking for pdfs in {model_folder}...")
                loader = DirectoryLoader(model_folder, glob="*.pdf", loader_cls=PyPDFLoader)
                pdf_docs = loader.load()
                
                if pdf_docs:
                    print(f"     success! loaded {len(pdf_docs)} pdf pages")
                    for doc in pdf_docs:
                        doc.metadata["car_model"] = model_name
                        doc.metadata["source_type"] = "Service Manual"
                        doc.page_content = doc.page_content.replace('\n', ' ')
                    documents.extend(pdf_docs)
        
    print(f"\nTotal Documents: {len(documents)}")
    if not documents:
        print("no docs found! check your json or internet connection")
        return

    print("chunking and embedding!")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)
    
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)
        
    embedding_func = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    db = Chroma(persist_directory=DB_PATH, embedding_function=embedding_function)
    
    # batch process
    batch_size = 100
    for i in tqdm(range(0, len(splits), batch_size), desc="indexing"):
        db.add_documents(splits[i:i + batch_size])
        
    print(f"\n smart database ready! {DB_PATH}")

if __name__ == "__main__":
    build_smart_database()