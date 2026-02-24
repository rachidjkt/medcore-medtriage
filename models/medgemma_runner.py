"""
models/medgemma_runner.py

Loads and runs the google/medgemma-1.5-4b-it multimodal model.

Key fix:
- Gemma3/MedGemma expects chat formatting (apply_chat_template).
- The processor will insert the correct image tokens automatically.
- Do NOT manually inject <image> tokens.

Auth:
- If the repo is gated, you must be logged in OR provide a token via:
  HUGGINGFACE_HUB_TOKEN or HF_TOKEN
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

logger = logging.getLogger(__name__)

MODEL_NAME = "google/medgemma-1.5-4b-it"

# Keep prompt strict but short. Long “rules” often trigger refusal loops.
SYSTEM_INSTRUCTIONS = """You are a medical imaging triage assistant.
You do NOT provide a diagnosis. Use cautious language.
Return ONLY a valid JSON object that matches the schema exactly. No markdown, no extra text.
"""

JSON_SCHEMA = """{
  "triage_level": "critical|urgent|routine",
  "suspected_findings": [],
  "red_flags": [],
  "recommended_next_steps": [],
  "specialty_category": "respiratory|cardiac|neurological|trauma|oncology|general",
  "patient_summary": "",
  "confidence_level": "low|medium|high",
  "disclaimer": "This output is AI-generated and not a substitute for professional medical advice."
}"""


def _get_hf_token_optional() -> Optional[str]:
    """
    Return HF token if present. If the user already logged in via HF_HOME cache,
    Transformers may still work without passing token explicitly.
    """
    return os.environ.get("HUGGINGFACE_HUB_TOKEN") or os.environ.get("HF_TOKEN")


class MedGemmaRunner:
    """Wraps MedGemma for image + text triage inference (Gemma3 chat-template compatible)."""

    def __init__(self) -> None:
        self.device: str = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("MedGemmaRunner: using device=%s", self.device)

        token = _get_hf_token_optional()

        logger.info("Loading processor for %s ...", MODEL_NAME)
        self.processor = AutoProcessor.from_pretrained(
            MODEL_NAME,
            trust_remote_code=True,
            token=token,  # ok if None
        )

        # Load model
        if self.device == "cuda":
            # Try 4-bit if bitsandbytes is installed; otherwise fall back to fp16.
            try:
                from transformers import BitsAndBytesConfig  # type: ignore

                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                )

                logger.info("Loading model for %s (4-bit, device_map=auto) ...", MODEL_NAME)
                self.model = AutoModelForCausalLM.from_pretrained(
                    MODEL_NAME,
                    trust_remote_code=True,
                    token=token,
                    quantization_config=bnb_config,
                    device_map="auto",
                )
            except Exception as e:
                logger.warning("4-bit load failed (%s). Falling back to fp16.", str(e))
                logger.info("Loading model for %s (fp16, device_map=auto) ...", MODEL_NAME)
                self.model = AutoModelForCausalLM.from_pretrained(
                    MODEL_NAME,
                    trust_remote_code=True,
                    token=token,
                    torch_dtype=torch.float16,
                    device_map="auto",
                )
        else:
            logger.info("Loading model for %s (cpu fp32) ...", MODEL_NAME)
            self.model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                trust_remote_code=True,
                token=token,
                torch_dtype=torch.float32,
            ).to("cpu")

        self.model.eval()
        logger.info("MedGemmaRunner: model loaded successfully.")

    def _get_model_device(self) -> torch.device:
        """
        device_map models don't always expose `.device` cleanly.
        This tries a few safe ways to retrieve the real device.
        """
        dev = getattr(self.model, "device", None)
        if isinstance(dev, torch.device):
            return dev
        if isinstance(dev, str):
            return torch.device(dev)
        try:
            return next(self.model.parameters()).device
        except Exception:
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _build_chat_prompt(self, context: str) -> str:
        """
        Build a Gemma3-compatible chat prompt.
        The processor will add the correct special tokens.
        """
        ctx = (context or "").strip()
        if not ctx:
            ctx = "No additional context provided."

        # IMPORTANT: Gemma3 multimodal expects image placeholder via structured content.
        # We do NOT manually write <image> tokens.
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {
                        "type": "text",
                        "text": (
                            f"{SYSTEM_INSTRUCTIONS}\n"
                            f"Clinical context: {ctx}\n\n"
                            f"Schema:\n{JSON_SCHEMA}\n"
                        ),
                    },
                ],
            }
        ]

        # tokenize=False returns a string prompt with the model’s chat template applied
        prompt: str = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=False,
        )
        return prompt

    def _prepare_inputs(self, image: Image.Image, context: str) -> Dict[str, Any]:
        prompt = self._build_chat_prompt(context)

        batch = self.processor(
            text=prompt,
            images=image,
            return_tensors="pt",
        )

        model_device = self._get_model_device()
        return {k: (v.to(model_device) if hasattr(v, "to") else v) for k, v in batch.items()}

    def analyze_image(self, image: Image.Image, context: str) -> str:
        """
        Two-step pipeline:
        1) Run image analysis freely
        2) Convert output to strict JSON schema
        """

        # ---------- STEP 1: Free-form medical reasoning ----------
        analysis_prompt = self._build_chat_prompt(context)

        inputs = self._prepare_inputs(image, context)

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.2,
                do_sample=False,
            )

        input_len = int(inputs["input_ids"].shape[-1])
        generated_ids = output_ids[0][input_len:]

        analysis_text = self.processor.decode(
            generated_ids, skip_special_tokens=True
        ).strip()

        # ---------- STEP 2: Convert to strict JSON ----------
        format_prompt = f"""
Convert the following medical triage analysis into STRICT valid JSON.

Output ONLY valid JSON.
No markdown.
No explanations.

Schema:
{JSON_SCHEMA}

Analysis:
{analysis_text}
"""

        format_inputs = self.processor(
            text=format_prompt,
            return_tensors="pt"
        ).to(self._get_model_device())

        with torch.no_grad():
            format_ids = self.model.generate(
                **format_inputs,
                max_new_tokens=512,
                temperature=0.0,
                do_sample=False,
            )

        input_len2 = int(format_inputs["input_ids"].shape[-1])
        generated_ids2 = format_ids[0][input_len2:]

        json_text = self.processor.decode(
            generated_ids2, skip_special_tokens=True
        ).strip()

        return json_text



# ---------------------------------------------------------------------------
# Module-level singleton (lazy-loaded by the app layer)
# ---------------------------------------------------------------------------
_runner: Optional[MedGemmaRunner] = None


def get_runner() -> MedGemmaRunner:
    global _runner
    if _runner is None:
        _runner = MedGemmaRunner()
    return _runner
