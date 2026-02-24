"""
eval/evaluate.py

Evaluation script for MedTriage App.

Loads labeled cases from eval/cases.json (if present) and runs inference on each,
comparing predicted triage_level to the ground-truth label.

Metrics computed:
  - Critical Recall: fraction of true-critical cases correctly predicted as critical
  - Escalation Rate: fraction of cases predicted as critical or urgent
  - Per-case comparison table

Usage:
  python -m eval.evaluate

If eval/cases.json is not present, prints instructions for creating it.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_CASES_PATH = Path(__file__).parent / "cases.json"
_DEMO_IMAGES_DIR = Path(__file__).parent.parent / "data" / "demo_images"

_CASES_SCHEMA_EXAMPLE = """
[
  {
    "image_filename": "chest_xray_01.png",
    "context": "65-year-old with acute chest pain.",
    "ground_truth_triage_level": "critical"
  },
  ...
]
"""


def _load_cases() -> list[dict[str, Any]]:
    """Load eval cases from JSON file."""
    if not _CASES_PATH.exists():
        print(
            "\n[MedTriage Eval] eval/cases.json not found.\n"
            "To run evaluation, create eval/cases.json with the following schema:\n"
            f"{_CASES_SCHEMA_EXAMPLE}\n"
            "Place corresponding images in data/demo_images/.\n"
            "Then re-run: python -m eval.evaluate\n"
        )
        sys.exit(0)

    with _CASES_PATH.open("r", encoding="utf-8") as f:
        cases: list[dict[str, Any]] = json.load(f)

    print(f"[MedTriage Eval] Loaded {len(cases)} cases from {_CASES_PATH}.")
    return cases[:10]  # cap at 10 for evaluation


def _run_single_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run inference on a single labeled case and return result dict."""
    from PIL import Image
    from models.medgemma_runner import get_runner
    from pipelines.preprocess import preprocess_image
    from pipelines.postprocess import parse_model_output

    image_path = _DEMO_IMAGES_DIR / case["image_filename"]
    if not image_path.exists():
        return {
            "image": case["image_filename"],
            "ground_truth": case["ground_truth_triage_level"],
            "predicted": "ERROR",
            "match": False,
            "error": f"Image not found: {image_path}",
        }

    try:
        image = Image.open(image_path)
        processed = preprocess_image(image)
        runner = get_runner()

        raw_output: str = ""
        triage_result = None
        last_error = ""

        for attempt in range(1, 3):
            raw_output = runner.analyze_image(processed, case.get("context", ""))
            try:
                triage_result = parse_model_output(raw_output)
                break
            except ValueError as exc:
                last_error = str(exc)
                logger.warning("Case %s attempt %d failed: %s", case["image_filename"], attempt, exc)

        if triage_result is None:
            return {
                "image": case["image_filename"],
                "ground_truth": case["ground_truth_triage_level"],
                "predicted": "PARSE_ERROR",
                "match": False,
                "error": last_error,
            }

        predicted = triage_result.triage_level
        ground_truth = case["ground_truth_triage_level"]
        return {
            "image": case["image_filename"],
            "ground_truth": ground_truth,
            "predicted": predicted,
            "match": predicted == ground_truth,
            "error": None,
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error for case %s", case["image_filename"])
        return {
            "image": case["image_filename"],
            "ground_truth": case["ground_truth_triage_level"],
            "predicted": "ERROR",
            "match": False,
            "error": str(exc),
        }


def main() -> None:
    """Run evaluation and print results table."""
    cases = _load_cases()
    results: list[dict[str, Any]] = []

    for i, case in enumerate(cases, start=1):
        print(f"  [{i}/{len(cases)}] Evaluating: {case['image_filename']} ...")
        result = _run_single_case(case)
        results.append(result)

    # ---------------------------------------------------------------------------
    # Metrics
    # ---------------------------------------------------------------------------
    total = len(results)
    critical_cases = [r for r in results if r["ground_truth"] == "critical"]
    critical_correct = [r for r in critical_cases if r["predicted"] == "critical"]
    escalated = [r for r in results if r["predicted"] in ("critical", "urgent")]

    critical_recall = len(critical_correct) / len(critical_cases) if critical_cases else float("nan")
    escalation_rate = len(escalated) / total if total else float("nan")
    overall_accuracy = sum(1 for r in results if r["match"]) / total if total else float("nan")

    # ---------------------------------------------------------------------------
    # Print table
    # ---------------------------------------------------------------------------
    header = f"{'Image':<35} {'Ground Truth':<15} {'Predicted':<15} {'Match':<8} {'Error'}"
    print("\n" + "=" * 90)
    print("MEDTRIAGE EVALUATION RESULTS")
    print("=" * 90)
    print(header)
    print("-" * 90)
    for r in results:
        match_str = "✓" if r["match"] else "✗"
        error_str = r["error"] or ""
        print(f"{r['image']:<35} {r['ground_truth']:<15} {r['predicted']:<15} {match_str:<8} {error_str[:40]}")

    print("=" * 90)
    print(f"Total cases:       {total}")
    print(f"Overall accuracy:  {overall_accuracy:.1%}")
    print(f"Critical recall:   {critical_recall:.1%}  ({len(critical_correct)}/{len(critical_cases)} critical cases correct)")
    print(f"Escalation rate:   {escalation_rate:.1%}  ({len(escalated)}/{total} cases flagged critical or urgent)")
    print("=" * 90)


if __name__ == "__main__":
    main()
