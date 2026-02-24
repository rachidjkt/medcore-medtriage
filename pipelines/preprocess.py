"""
pipelines/preprocess.py

Image preprocessing utilities for MedTriage App.
Converts images to RGB, resizes to max side 512, and applies optional autocontrast.
"""

import logging

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_SIDE: int = 512


def preprocess_image(image: Image.Image, autocontrast: bool = True) -> Image.Image:
    """
    Prepare a PIL image for model inference.

    Steps:
      1. Convert to RGB (handles grayscale, RGBA, DICOM-derived, etc.)
      2. Resize so the longest side is MAX_SIDE, preserving aspect ratio.
      3. Optionally apply ImageOps.autocontrast for better model visibility.

    Args:
        image: Input PIL Image in any mode.
        autocontrast: Whether to apply autocontrast enhancement.

    Returns:
        Preprocessed PIL Image in RGB mode.
    """
    # Step 1: Ensure RGB
    if image.mode != "RGB":
        logger.debug("Converting image from mode=%s to RGB.", image.mode)
        image = image.convert("RGB")

    # Step 2: Resize preserving aspect ratio so max side == MAX_SIDE
    original_size = image.size  # (width, height)
    max_dim = max(original_size)
    if max_dim > MAX_SIDE:
        scale = MAX_SIDE / max_dim
        new_size = (int(original_size[0] * scale), int(original_size[1] * scale))
        image = image.resize(new_size, Image.LANCZOS)
        logger.debug("Resized image from %s to %s.", original_size, new_size)
    else:
        logger.debug("Image size %s within limit; no resize needed.", original_size)

    # Step 3: Optional autocontrast
    if autocontrast:
        image = ImageOps.autocontrast(image)
        logger.debug("Applied autocontrast.")

    return image
