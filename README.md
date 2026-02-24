# MedCore – MedTriage AI 🏥

AI-assisted medical triage and care coordination powered by **Google MedGemma**

Built for the **MedGemma Impact Challenge**


demo-website(no model, hosting-friendly) : https://medcore-medtriage-xtcvvezhgxpcstf5nrng2p.streamlit.app/
---

# Overview

MedCore / MedTriage AI is a clinical workflow prototype that combines medical image analysis with patient–clinician coordination.

The system allows:

• Patients to upload scans and receive structured triage guidance  
• Clinicians to review patient results and manage cases  
• AI-assisted hospital referral based on urgency and specialty  

The application is built with **Python**, **Streamlit**, and **MedGemma (HAI-DEF)** and demonstrates how open medical models can support healthcare workflows while keeping humans in control of final decisions.

Instead of only generating model predictions, MedCore focuses on the entire care loop:

image → triage → clinician review → scheduling → referral

---

# Architecture

```
medtriage_app/
│
├── app/
│   ├── main.py                  ← Streamlit entry point + navigation
│   └── pages/
│       ├── auth.py              ← Login + role selection
│       ├── patient.py           ← Patient dashboard
│       ├── professional.py      ← Clinician dashboard
│       ├── patients.py          ← Case management
│       ├── upload.py            ← Image upload + context input + Demo Mode
│       ├── results.py           ← Triage report display
│       └── referral.py          ← Hospital ranking + Find Care
│
├── models/
│   └── medgemma_runner.py       ← HuggingFace model wrapper + inference
│
├── pipelines/
│   ├── preprocess.py            ← Image → RGB, resize, autocontrast
│   ├── postprocess.py           ← JSON extraction + validation
│   ├── referral_logic.py        ← Hospital scoring + ranking
│   ├── schemas.py               ← Pydantic models
│   └── storage.py               ← Case storage layer
│
├── storage/
│   ├── db.py                    ← Local demo database
│   ├── models.py                ← Case models
│   ├── export.py                ← Data export tools
│   └── crypto.py                ← Encryption helpers
│
├── data/
│   ├── hospitals_ottawa.json    ← Ottawa hospital dataset
│
├── eval/
│   └── evaluate.py              ← Batch evaluation + metrics
│
├── requirements.txt
└── README.md
```

---

# Data Flow

```
User Upload
    │
    ▼
preprocess_image()          ← RGB, resize to 512px, autocontrast
    │
    ▼
MedGemmaRunner.analyze_image()   ← HuggingFace inference (GPU/CPU)
    │
    ▼
parse_model_output()        ← JSON extraction + Pydantic validation
    │
    ▼
TriageOutput                ← Structured result (triage_level, findings, etc.)
    │
    ▼
rank_hospitals()            ← Score hospitals by specialty + capability
    │
    ▼
Streamlit UI                ← Patient + Clinician dashboards
```

---

# Key Features

## AI Triage

Uses **MedGemma-1.5-4B-it**, a multimodal medical vision-language model, to analyze medical images and generate structured outputs:

• triage level  
• suspected findings  
• red flags  
• recommended next steps  
• specialty category  
• patient-friendly summary  

Outputs are validated with **Pydantic schemas** before being shown in the interface.

---

# Patient Portal

Patients can:

• Upload medical images  
• View AI triage summaries  
• Track scan history  
• Confirm proposed appointments  
• View recommended hospitals  

---

# Clinician Portal

Healthcare professionals can:

• View patient list  
• Review patient profiles  
• Run MedGemma analysis on behalf of a patient  
• Propose appointment slots  
• Track patient cases  

---

# Hospital Referral Engine

Hospitals are ranked using:

• medical specialty  
• trauma capability  
• ICU availability  
• triage severity  

Supports **Ottawa and Gatineau hospitals** with geographic coordinates for future routing.

---

# Demo Mode

The system can run without loading the model, allowing it to:

• deploy on free hosting platforms  
• demonstrate UI features without GPU  
• test workflows safely

---

# How to Run Locally

```bash
git clone https://github.com/rachidjkt/medcore-medtriage
cd medcore-medtriage

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

streamlit run app/main.py
```

The app will open at:

http://localhost:8501

---

# MedGemma Setup

Access to the model requires HuggingFace authentication.

Request access here:

https://huggingface.co/google/medgemma-1.5-4b-it

Then login:

```bash
huggingface-cli login
```

or set an environment variable:

Windows

```
setx HF_TOKEN "your_token"
```

Linux / macOS

```
export HF_TOKEN=your_token
```

---

# Hardware Notes

| Hardware | Inference Speed | Notes |
|---|---|---|
| NVIDIA GPU (≥8GB VRAM) | ~5–15 seconds | Recommended |
| Apple Silicon | ~20–40 seconds | Works with MPS |
| CPU | ~1–3 minutes | Slow but functional |

The model loads automatically on CUDA when available.

---

# Evaluation

Place labeled cases in:

```
eval/cases.json
```

Example:

```json
[
  {
    "image_filename": "chest_xray_01.png",
    "context": "65-year-old with acute chest pain.",
    "ground_truth_triage_level": "critical"
  }
]
```

Then run:

```bash
python -m eval.evaluate
```

Metrics:

• triage accuracy  
• escalation rate  
• critical recall  

---

# Limitations

Current prototype limitations:

• No DICOM ingestion yet  
• No secure PHI storage (demo database only)  
• No clinical validation  
• Hospital ranking not distance-aware yet  

---

# Future Work

• DICOM integration  
• real geolocation routing  
• hospital API integration  
• clinician feedback loop  
• model confidence calibration  
• secure deployment

---

# Safety

This system follows the **HAI-DEF philosophy**:

AI assists clinicians rather than replacing them.

Outputs are:

• advisory  
• explainable  
• validated before display

---

# Disclaimer

This application is for **research and demonstration purposes only.**

It must not be used to make real medical decisions.

Always consult a qualified healthcare professional.

In an emergency call **911**.

---

# Author

**Rachid J. Tarnagda**  
University of Ottawa  
Biomedical Science + Computer Science  

GitHub  
https://github.com/rachidjkt

LinkedIn  
https://www.linkedin.com/in/rachid-jonathan-k-tarnagda-97296a284/

---

Built for the **MedGemma Impact Challenge**
