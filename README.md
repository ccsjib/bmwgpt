# BMWChat (BMWGPT)



## What Is It?

BMWChat is built for beginner car enthusiasts who want to learn more about BMWs. Although it specifically focuses on most models produced from the 1980s to the 2000s, users can upload a picture of an unknown BMW to identify it and access a database of knowledge about any specific BMW. From basic specifications to repair procedures, BMWChat is capable of answering a vast array of questions.

## What It Does
BMWChat first uses a model trained on a wide array of over 10,000 images including most BMW models along with non-BMW and non-car images (appropriately weighted) to help it classify any image uploaded to the platform. This dataset was curated by me using a combination of web scraping and manual additions. It was originally cleaned using the CLIP model and then manually cleaned to ensure accuracy. Based on this model, it then accesses a specially curated database of information for the idenitfied model. 

The chat can then access the database for that model. Questions from specifications to repair instructions can be asked. It responds with more detail if the BMW is one of the supported models produced from the 1980s to the 2000s, and if not, it can provide more basic specifications through sources like Wikipedia. The chat is connected to Gemini to create more human-like responses and allow additional generalized information when the database lacks sufficient information to answer the question. 

## Notes

* [Dataset](https://github.com/ccsjib/bmwgpt/releases/tag/full-dataset) is stored in the **Releases** section of the repository. 

## Quick Start

### Prerequisites
* Python 3.9/3.10 (other versions not confirmed to be functional)
* Google AI Studio API Key

### Option 1: Website
Simply visit the BMWChat website here: [BMWChat](https://bmwchat.streamlit.app)

### Option 2: Run Locally

*Required: Git

Clone this repository and setup a Python virtual environment where you can download all required libraries in requirements.txt. Next, run ```streamlit run bmw.py``` in your terminal to locally host BMWChat. 

### API Key

Once BMWChat is running/open, follow the instructions in the sidebar to get your Google AI Studio API key from their website. Submit it to BMWChat to have access to the chat. Without this step, the identification model is still functional. 

For more details, check out [SETUP.md](./SETUP.md)

## Video Links
Demo video here:

Technical walkthrough here: 

## Evaluation
The identification model had noticiable improvement in testing when switching from ResNet-18 to EfficientNet-B4 due to the higher resolution processing and a newer, more efficient model. 

The database had much higher performance using PaddleOCR as compared to Tesseract. Large amounts of evidence pulled from the database using Tesseract included mispelled words, keeping Gemini from accurately creating a response. 

Average database response time of 4.2 seconds based on real-world trials on the web-hosted application. 

## Individual Contributions

All work completed by me (solo project).
