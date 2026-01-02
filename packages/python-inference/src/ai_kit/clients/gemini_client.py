from __future__ import annotations

import base64
import os
import random
import ssl
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image


def _load_genai():
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - dependency issue
        raise RuntimeError(
            "google-genai is required for Gemini image generation. "
            "Install it with `pip install google-genai`."
        ) from exc
    return genai, types


def _env_api_key() -> str:
    return (
        os.getenv("AI_KIT_GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    )


def _coerce_image(value: Union[Image.Image, bytes, bytearray, str, Path]) -> Image.Image:
    if isinstance(value, Image.Image):
        return value
    if isinstance(value, (bytes, bytearray)):
        with Image.open(BytesIO(value)) as img:
            return img.copy()
    if isinstance(value, (str, Path)):
        with Image.open(value) as img:
            return img.copy()
    raise TypeError(f"Unsupported image input type: {type(value)}")


def _extract_images(response: Any) -> List[bytes]:
    images: List[bytes] = []

    def _inline_to_bytes(inline: Any) -> Optional[bytes]:
        if isinstance(inline, dict):
            data = inline.get("data")
        else:
            data = getattr(inline, "data", None)
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        if isinstance(data, str):
            try:
                return base64.b64decode(data)
            except Exception:
                return None
        return None

    def _part_to_bytes(part: Any) -> Optional[bytes]:
        inline = getattr(part, "inline_data", None)
        if inline is not None:
            inline_bytes = _inline_to_bytes(inline)
            if inline_bytes:
                return inline_bytes
        try:
            img = part.as_image()
        except Exception:
            return None
        buf = BytesIO()
        if isinstance(img, Image.Image):
            img.save(buf, format="PNG")
        else:
            try:
                img.save(buf)
            except TypeError:
                img.save(buf, "PNG")
        return buf.getvalue()

    parts = getattr(response, "parts", None) or []
    for part in parts:
        data = _part_to_bytes(part)
        if data:
            images.append(data)
    if images:
        return images
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        candidate_parts = getattr(content, "parts", None) or []
        for part in candidate_parts:
            data = _part_to_bytes(part)
            if data:
                images.append(data)
    return images


def _retry_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    delay = min(max_delay, base_delay * (2 ** attempt))
    jitter = random.uniform(0, min(1.0, delay * 0.1))
    return delay + jitter


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, ssl.SSLError):
        return True
    message = str(exc).lower()
    return any(
        hint in message
        for hint in (
            "ssl",
            "tls",
            "bad record mac",
            "eof occurred in violation of protocol",
            "connection reset",
        )
    )


class GeminiImageClient:
    def __init__(self, *, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or _env_api_key()
        self._client = None

    def generate_images(
        self,
        *,
        model: str,
        prompt: str,
        input_image: Union[Image.Image, bytes, bytearray, str, Path],
        response_modalities: Optional[List[str]] = None,
        image_config: Optional[Dict[str, Any]] = None,
    ) -> List[bytes]:
        if not prompt:
            raise ValueError("Prompt is required for Gemini image generation")
        genai, types = _load_genai()
        client = self._get_client(genai)
        image = _coerce_image(input_image)
        config_kwargs: Dict[str, Any] = {}
        modalities = response_modalities or ["Image"]
        if modalities:
            config_kwargs["response_modalities"] = modalities
        if image_config:
            config_kwargs["image_config"] = types.ImageConfig(**image_config)
        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
        max_retries = int(os.getenv("AI_KIT_GEMINI_MAX_RETRIES", "5"))
        base_delay = float(os.getenv("AI_KIT_GEMINI_BASE_DELAY_S", "1.0"))
        max_delay = float(os.getenv("AI_KIT_GEMINI_MAX_DELAY_S", "10.0"))
        attempt = 0
        while True:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[prompt, image],
                    config=config,
                )
                break
            except Exception as exc:
                if attempt >= max_retries or not _is_retryable_error(exc):
                    raise
                time.sleep(_retry_delay(attempt, base_delay, max_delay))
                attempt += 1
                self._client = None
                client = self._get_client(genai)
        images = _extract_images(response)
        if not images:
            raise RuntimeError("Gemini response did not include image data")
        return images

    def _get_client(self, genai_module):
        if self._client is None:
            if self.api_key:
                self._client = genai_module.Client(api_key=self.api_key)
            else:
                self._client = genai_module.Client()
        return self._client
