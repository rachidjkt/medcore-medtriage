MedCore – MedTriage AI

AI-assisted medical triage and care coordination powered by Google MedGemma

Overview

MedCore / MedTriage AI is a clinical workflow prototype that combines medical image analysis with patient–clinician coordination.

The system allows:

Patients to upload scans and receive structured triage guidance

Clinicians to review patient results and manage cases

AI-assisted hospital referral based on urgency and specialty

The application is built with Python, Streamlit, and MedGemma (HAI-DEF) and demonstrates how open medical models can support healthcare workflows while keeping humans in control of final decisions.

Instead of only generating model predictions, MedCore focuses on the entire care loop:

image → triage → clinician review → scheduling → referral
Key Features
AI Triage

Uses MedGemma 1.5 4B vision-language model to analyze medical images and produce structured outputs:

triage level

suspected findings

red flags

recommended next steps

specialty category

patient-friendly summary

Outputs are validated using Pydantic schemas before being displayed.

Patient Portal

Patients can:

Upload medical images

View AI triage summaries

Track scan history

Confirm proposed appointments

View recommended hospitals

Clinician Portal

Healthcare professionals can:

View patient list

Review patient profiles

Run MedGemma analysis on behalf of a patient

Propose appointment slots

Track patient cases

Hospital Referral Engine

Hospitals are ranked based on:

medical specialty

trauma capability

ICU availability

triage severity

Supports Ottawa + Gatineau hospitals with geographic coordinates for future routing.

medtriage_app/
│
├── app
│   ├── main.py
│   ├── ui.py
│   └── pages
│       ├── auth.py
│       ├── patient.py
│       ├── professional.py
│       ├── patients.py
│       ├── upload.py
│       ├── results.py
│       └── referral.py
│
├── models
│   └── medgemma_runner.py
│
├── pipelines
│   ├── preprocess.py
│   ├── postprocess.py
│   ├── referral_logic.py
│   ├── schemas.py
│   └── storage.py
│
├── data
│   └── hospitals_ottawa.json
│
├── eval
│   └── evaluate.py
│
└── requirements.txt

Running Locally
git clone https://github.com/rachidjkt/medcore-medtriage
cd medtriage_app

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

streamlit run app/main.py

The app will open at:

http://localhost:8501
MedGemma Setup

Access to the model requires HuggingFace authentication.

Request access here:

https://huggingface.co/google/medgemma-1.5-4b-it

Then login:

huggingface-cli login

or set an environment variable:

HF_TOKEN=your_token
Hardware

Recommended:

GPU with ≥8GB VRAM

Supported:

CPU (slower)

The model automatically loads on CUDA if available.

Evaluation

The repository includes a simple evaluation script for batch testing.

python -m eval.evaluate

Metrics include:

triage accuracy

escalation rate

critical recall

Safety

This system follows the HAI-DEF philosophy:

AI assists clinicians rather than replacing them.

Outputs are:

advisory

explainable

validated before display

Limitations

Current prototype limitations:

No DICOM ingestion yet

No secure PHI storage (demo database only)

No clinical validation

Hospital ranking not distance-aware yet

Future Work

DICOM integration

real geolocation routing

hospital API integration

clinician feedback loop

model confidence calibration

secure deployment

Competition

Built for the MedGemma Impact Challenge.

Focus areas:

human-centered AI

real clinical workflows

open model deployment

Disclaimer

This application is for research and demonstration purposes only.

It must not be used to make real medical decisions.

Always consult a qualified healthcare professional.

In an emergency call 911.

Author

Rachid J. Tarnagda
University of Ottawa
Biomedical Science + Computer Science