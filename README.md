# MedCore / MedTriage

A **Python and Streamlit healthcare-workflow prototype** connecting image-analysis outputs with patient records, clinician review, appointment proposals, and hospital-referral suggestions.

Built for the **MedGemma Impact Challenge**. The project explores the application workflow around a model, including structured output handling and persistence.

[Open the hosted workflow demo](https://medcore-medtriage-xtcvvezhgxpcstf5nrng2p.streamlit.app/) · [Model integration](models/medgemma_runner.py) · [Evaluation script](eval/evaluate.py)

**Research and demonstration only.** This is not a clinically validated system. Use synthetic information and non-sensitive example images; the demo authentication and storage are not suitable for real patient data.

## Two execution modes

| Mode | Behavior |
|---|---|
| Demo mode — enabled by default | Uses a fixed example payload to demonstrate the workflow; it does not analyze the uploaded image with a model |
| Model mode | Calls the MedGemma wrapper, preprocesses the image, and parses the generated output into a structured object |

Demo outputs are examples, not evidence of prediction quality.

## Implemented workflow

- Patient and professional views with a demo sign-in flow.
- Image upload with optional contextual information.
- MedGemma integration for structured image-analysis outputs.
- JSON extraction and Pydantic validation, with a labeled fallback when parsing fails.
- Patient profiles and report history.
- Appointment proposals and confirmation workflows.
- Rule-based hospital ranking using a local Ottawa/Gatineau dataset.

Schema validation checks output structure; it does not establish medical correctness. Hospital ranking uses static attributes, not live ICU capacity, wait times, or verified real-time availability.

## Architecture

| Component | Responsibility |
|---|---|
| [app/main.py](app/main.py) | Streamlit entry point, navigation, role views, and demo toggle |
| [app/pages/](app/pages/) | Patient, professional, upload, results, and referral interfaces |
| [models/medgemma_runner.py](models/medgemma_runner.py) | MedGemma loading and generation |
| [pipelines/preprocess.py](pipelines/preprocess.py) | RGB conversion, resizing, and optional autocontrast |
| [pipelines/postprocess.py](pipelines/postprocess.py) | JSON extraction, validation, and parsing fallback |
| [pipelines/storage.py](pipelines/storage.py) | JSON-backed persistence used by the main application |
| [pipelines/referral_logic.py](pipelines/referral_logic.py) | Rule-based hospital scoring |
| [storage/](storage/) | Additional database, export, and encryption modules |
| [eval/evaluate.py](eval/evaluate.py) | Labeled-case evaluation harness |

The main application's active storage path is `data/app_db.json`. The presence of separate encryption/database modules does not mean the running JSON-backed workflow uses them.

## Run locally

Python 3.10 or newer is required by the source syntax.

```bash
git clone https://github.com/rachidjkt/medcore-medtriage.git
cd medcore-medtriage
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install dependencies and launch from the repository root:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app/main.py
```

Keep **Demo Mode** enabled for a workflow walkthrough without loading model weights.

The application seeds demonstration accounts on first initialization:

| Role | Email | Password |
|---|---|---|
| Patient | patient@demo.com | demo |
| Professional | doctor@demo.com | demo |

These are intentionally public demonstration credentials. Do not reuse real passwords.

### Model mode prerequisites

The wrapper targets `google/medgemma-1.5-4b-it`. Model access is subject to its Hugging Face access requirements and terms. Supply authentication through a local login or the `HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN` environment variable; never commit tokens.

The current wrapper selects CUDA when available and CPU otherwise. It attempts 4-bit loading on CUDA and falls back to FP16. It does not currently select Apple's MPS backend.

Model loading may download substantial weights. Hardware requirements and inference latency have not been established by a published benchmark in this repository. The broad lower bounds in `requirements.txt` are not a verified model-mode compatibility matrix.

## Evaluation

The harness expects:

- Labeled cases in `eval/cases.json`.
- Corresponding images in `data/demo_images/`.

Example case file:

```json
[
  {
    "image_filename": "example.png",
    "context": "Synthetic example context",
    "ground_truth_triage_level": "routine"
  }
]
```

Run:

```bash
python -m eval.evaluate
```

The script prints a per-case comparison, overall accuracy, critical recall, and escalation rate. It currently processes at most **10 cases**. The repository does not include the labeled case file, evaluation images, or a published results report.

Parsing failures return a fallback labeled `urgent`. Evaluation needs to distinguish those fallbacks from successful model predictions before interpreting escalation or recall.

## Scope and limitations

- No clinical validation or calibrated confidence estimates.
- PNG/JPG upload workflow; no native DICOM ingestion.
- Local JSON persistence and demonstration authentication.
- Static hospital metadata and no distance-based ranking.
- Dependency compatibility and model-mode execution require further verification.

## Next improvements

- Add a reproducible environment and synthetic workflow checks.
- Separate parsing-fallback rates from prediction metrics.
- Publish a documented evaluation set and results.
- Consolidate storage and add production-grade authentication before considering any real deployment.

## Author

**Rachid Tarnagda** — Biomedical Science, Computer Science minor, University of Ottawa.

[GitHub](https://github.com/rachidjkt) · [LinkedIn](https://www.linkedin.com/in/rachid-jonathan-k-tarnagda-97296a284/)
