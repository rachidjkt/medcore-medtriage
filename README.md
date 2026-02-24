# MedTriage AI

## Overview

MedTriage AI is a production-ready medical image triage assistant built with Python 3.11 and Streamlit. It uses Google's **MedGemma-1.5-4b-it** — a multimodal vision-language model fine-tuned on biomedical data — to analyze medical images and generate structured triage assessments. The application accepts radiology scans, dermatology images, and other clinical visuals, then returns a validated JSON report covering triage level, suspected findings, red flags, and recommended next steps.

The system is designed around a clean separation of concerns: a model runner layer handles HuggingFace inference, a pipeline layer handles preprocessing and Pydantic-validated output parsing, and a Streamlit multipage UI handles user interaction and hospital referral. This architecture makes each component independently testable and replaceable.

MedGemma was selected because it is purpose-built for medical imaging tasks and follows the HAI-DEF (Human-AI Diagnostic Enhancement Framework) philosophy — augmenting clinician decision-making rather than replacing it. The model's instruction-following capability allows structured JSON output extraction, which is validated with Pydantic before display.

---

## Architecture

```
medtriage_app/
│
├── app/
│   ├── main.py                  ← Streamlit entry point + navigation
│   └── pages/
│       ├── upload.py            ← Image upload + context input + Demo Mode
│       ├── results.py           ← Triage report display
│       └── referral.py          ← Hospital ranking + Find Care
│
├── models/
│   └── medgemma_runner.py       ← HuggingFace model wrapper + inference
│
├── pipelines/
│   ├── preprocess.py            ← Image → RGB, resize, autocontrast
│   ├── postprocess.py           ← Pydantic TriageOutput + JSON extraction
│   └── referral_logic.py        ← Hospital scoring + ranking
│
├── data/
│   ├── hospitals_ottawa.json    ← 5 Ottawa hospital records
│   └── demo_images/             ← Place demo images here
│
├── eval/
│   └── evaluate.py              ← Batch evaluation + metrics
│
├── requirements.txt
└── README.md
```

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
rank_hospitals()            ← Score Ottawa hospitals by specialty + trauma level
    │
    ▼
Streamlit UI                ← Results page + Referral page
```

---

## How to Run Locally

```bash
# 1. Clone the repo and enter the project directory
cd medtriage_app

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the Streamlit app
streamlit run app/main.py
```

> The app will open at `http://localhost:8501` in your browser.

---

## Hardware Notes

| Hardware | Inference Speed | Notes |
|---|---|---|
| NVIDIA GPU (≥8 GB VRAM) | ~5–15 seconds | Recommended. Model loads in float16. |
| Apple Silicon (MPS) | ~20–40 seconds | Set `device_map` manually if needed. |
| CPU only | ~2–5 minutes | Supported but slow. Use for testing only. |

The model is automatically loaded to CUDA if available, otherwise CPU. Approximately **8–10 GB of disk space** is required to cache the MedGemma weights.

---

## Model

**Model:** [`google/medgemma-1.5-4b-it`](https://huggingface.co/google/medgemma-1.5-4b-it)

MedGemma is Google's medical-domain vision-language model, fine-tuned for instruction following on clinical and biomedical data. It supports multimodal inputs (image + text) and is optimized for medical question answering and image interpretation. The `-it` suffix indicates the instruction-tuned variant, which enables structured JSON output via prompt engineering.

---

## Evaluation

Place labeled cases in `eval/cases.json` with the following schema:

```json
[
  {
    "image_filename": "chest_xray_01.png",
    "context": "65-year-old with acute chest pain.",
    "ground_truth_triage_level": "critical"
  }
]
```

Place corresponding images in `data/demo_images/`. Then run:

```bash
python -m eval.evaluate
```

**Metrics computed:**
- **Overall Accuracy** — fraction of cases with correct triage level
- **Critical Recall** — fraction of true-critical cases correctly predicted as critical
- **Escalation Rate** — fraction of cases predicted as critical or urgent

---

## Limitations & Future Improvements

**Current limitations:**
- No DICOM support (images must be standard raster formats)
- Hospital ranking uses no real geocoding (location is display-only)
- No authentication or patient data persistence
- Model may hallucinate findings on out-of-distribution images

**Future improvements:**
- DICOM ingestion via `pydicom`
- Real-time geocoding for distance-based hospital ranking
- Fine-tuning on institution-specific labeled datasets
- Confidence calibration and uncertainty quantification
- HIPAA-compliant deployment configuration

---

## ⚠️ Safety Disclaimer

> **This application is intended for research and demonstration purposes only.**
>
> The AI-generated outputs from this tool are **not a substitute for professional medical advice, diagnosis, or treatment.** Always seek the guidance of a qualified healthcare provider with any questions regarding a medical condition. Do not disregard professional medical advice or delay seeking it because of something generated by this application.
>
> In a life-threatening emergency, call **911** immediately.
>
> The developers of this project assume no liability for clinical decisions made based on the outputs of this system.

---

## Demo Video

_A walkthrough video demonstrating the application will be linked here._

---

## Writeup / Report

_A technical writeup describing the architecture, model integration, and evaluation findings will be added here._
