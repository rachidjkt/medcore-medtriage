import json
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, ValidationError


class TriageOutput(BaseModel):
    triage_level: Literal["critical", "urgent", "routine"]
    suspected_findings: List[str]
    red_flags: List[str]
    recommended_next_steps: List[str]
    specialty_category: Literal[
        "respiratory", "cardiac", "neurological", "trauma", "oncology", "general"
    ]
    patient_summary: str
    confidence_level: Literal["low", "medium", "high"]
    disclaimer: str


def _extract_first_json_object(text: str) -> Optional[str]:
    """
    Extract the first {...} JSON object from a messy LLM output using a brace-matching scan.
    Returns the JSON string or None.
    """
    if not text:
        return None

    # Remove common markdown fences if present
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).replace("```", "")

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


def _fallback_output(raw_output: str, err: str) -> TriageOutput:
    """
    Hard fallback so the app never crashes during demo.
    Conservative defaults + embed raw model output for transparency.
    """
    clipped = (raw_output or "").strip()
    if len(clipped) > 800:
        clipped = clipped[:800] + "..."

    return TriageOutput(
        triage_level="urgent",
        suspected_findings=[],
        red_flags=["Model did not return structured JSON."],
        recommended_next_steps=[
            "Seek evaluation by a qualified clinician.",
            "If severe symptoms (difficulty breathing, chest pain, neuro deficits), seek emergency care.",
        ],
        specialty_category="general",
        patient_summary=f"⚠️ Parsing fallback used. Reason: {err}\n\nRaw model output:\n{clipped}",
        confidence_level="low",
        disclaimer="This output is AI-generated and not a medical diagnosis.",
    )


def parse_model_output(raw_output: str) -> TriageOutput:
    """
    Parse model output into TriageOutput.
    - Tries to extract JSON object from the output
    - Validates with Pydantic
    - If extraction/validation fails, returns a conservative fallback (never raises)
    """
    json_str = _extract_first_json_object(raw_output)
    if json_str is None:
        return _fallback_output(raw_output, "No JSON object found in model output.")

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return _fallback_output(raw_output, f"Invalid JSON: {e}")

    try:
        return TriageOutput(**data)
    except ValidationError as e:
        return _fallback_output(raw_output, f"Schema validation failed: {e}")
