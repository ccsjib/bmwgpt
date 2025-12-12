# BMWChat (BMWGPT)



## What Is It?

BMWChat is built for beginner car enthusiasts who want to learn more about BMWs. Although it specifically focuses on most models produced from the 1980s to the 2000s, users can upload a picture of an unknown BMW to identify it and access a database of knowledge about any specific BMW. From basic specifications to repair procedures, BMWChat is capable of answering a vast array of questions.

## What It Does
BMWChat first uses a model trained on a wide array of over 10,000 images including most BMW models along with non-BMW and non-car images (appropriately weighted) to help it classify any image uploaded to the platform. It uses an 80/20 train/validation split. This dataset was curated by me using a combination of web scraping and manual additions. It was originally cleaned using the CLIP model and then manually cleaned to ensure accuracy. Based on this model, it then accesses a specially curated database of information for the idenitfied model. 

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

## Objectives

1. Accurately classify BMW models from user-uploaded images.

2. Retrieve accurate technical specifications and repair instructions from the database.

3. Provide a responsive user experience with human-like answers.

## Evaluation
* The identification model had noticiable improvement in testing when switching from ResNet-18 to EfficientNet-B4 due to the higher resolution processing. The model was able to more clearly differenciate between very similar cars. For example, a BMW sedan and Touring (station wagon) of the same generation tend to have the same front styling, but EfficientNet-B4 was able to more accurately notice this difference. 

* The database had much higher performance using PaddleOCR as compared to Tesseract. Large amounts of evidence pulled from the database using Tesseract included mispelled words due to poor OCR, keeping Gemini from accurately creating a response. 

* Objective 1: Model training cross-entropy loss began at ~2.84 and reduced to ~0.66 after 20 epochs. Validation accuracy reached 78.41% Dataset was then adjusted due to false positive BMW recognition. Loss began at ~1.53 and reduced to ~0.74 after 10 epochs. 

* Objective 2: Based on 10 manual trials of factual queries, the database was able to accurately respond with correct information 70% of the time. It correctly differentiated between a car and non-car 90% of the time, differentiated between a BMW and non-BMW 80% of the time, and correctly identified a specific BMW model 60% of the time. It often picked a similar BMW model, but does struggle with extremely small details just as when presented with a model that has an identically styles 2-door and 4-door version.

* Objective 3: Average identification time of ~1.8 seconds and average database response time of 4.2 seconds based on real-world trials on the web-hosted application (10 trials). 

## Individual Contributions

All work completed by me (solo project).
