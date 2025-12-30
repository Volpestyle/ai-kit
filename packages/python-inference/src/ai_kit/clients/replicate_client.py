from __future__ import annotations

import io
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import replicate
import requests
from PIL import Image


def _is_file_output(obj: Any) -> bool:
    return hasattr(obj, "read") and callable(getattr(obj, "read"))


def _read_file_output(obj: Any) -> bytes:
    # Replicate FileOutput supports .read() (sync)
    return obj.read()  # type: ignore[no-any-return]


def _download_url(url: str) -> bytes:
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    return r.content


class ReplicateClient:
    """
    Thin wrapper around the Replicate Python SDK.

    Replicate auth is resolved from env var REPLICATE_API_TOKEN by default.
    """

    def __init__(
        self,
        *,
        use_file_output: bool = True,
        max_retries: int = 3,
        base_delay_s: float = 2.0,
        max_delay_s: float = 30.0,
    ):
        self.use_file_output = use_file_output
        self.max_retries = max(0, max_retries)
        self.base_delay_s = max(0.1, base_delay_s)
        self.max_delay_s = max(self.base_delay_s, max_delay_s)

    def run(self, model: str, *, inputs: Dict[str, Any]) -> Any:
        # replicate.run(..., use_file_output=...) is supported in replicate>=1.0.0.
        attempt = 0
        while True:
            try:
                return replicate.run(model, input=inputs, use_file_output=self.use_file_output)
            except Exception as exc:
                if not self._should_retry(exc, attempt):
                    raise
                delay = self._retry_delay(exc, attempt)
                time.sleep(delay)
                attempt += 1

    def remove_background(
        self,
        *,
        model: str,
        image_path: Path,
        preserve_partial_alpha: bool = True,
        content_moderation: bool = False,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        with image_path.open("rb") as f:
            inputs: Dict[str, Any] = {
                "preserve_partial_alpha": preserve_partial_alpha,
                "content_moderation": content_moderation,
            }
            if parameters:
                inputs.update(parameters)
            inputs["image"] = f
            out = self.run(
                model,
                inputs=inputs,
            )
        return self._coerce_single_file(out)

    def multiview_zero123plusplus(
        self,
        *,
        model: str,
        image_path: Path,
        remove_background: bool = False,
        return_intermediate_images: bool = False,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Union[List[bytes], bytes]:
        with image_path.open("rb") as f:
            inputs: Dict[str, Any] = {
                "remove_background": remove_background,
                "return_intermediate_images": return_intermediate_images,
            }
            if parameters:
                inputs.update(parameters)
            inputs["image"] = f
            out = self.run(
                model,
                inputs=inputs,
            )
        # Common outputs: list[FileOutput] or list[url] or single FileOutput
        if isinstance(out, (list, tuple)):
            return [self._coerce_single_file(x) for x in out]
        return self._coerce_single_file(out)

    def depth_anything_v2(
        self,
        *,
        model: str,
        image_path: Path,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, bytes]:
        with image_path.open("rb") as f:
            inputs: Dict[str, Any] = {}
            if parameters:
                inputs.update(parameters)
            inputs["image"] = f
            out = self.run(model, inputs=inputs)
        # Expected dict with keys like "grey_depth" and "color_depth"
        if not isinstance(out, dict):
            # Some model variants might return a single output; normalize.
            return {"grey_depth": self._coerce_single_file(out)}
        result: Dict[str, bytes] = {}
        for k, v in out.items():
            result[str(k)] = self._coerce_single_file(v)
        return result

    def _coerce_single_file(self, out: Any) -> bytes:
        if out is None:
            raise RuntimeError("Replicate returned None output")
        if isinstance(out, bytes):
            return out
        if _is_file_output(out):
            return _read_file_output(out)
        if isinstance(out, str) and out.startswith("http"):
            return _download_url(out)
        # Some outputs can be dicts with 'url'
        if isinstance(out, dict) and "url" in out and isinstance(out["url"], str):
            return _download_url(out["url"])
        raise TypeError(f"Unsupported Replicate output type: {type(out)}")

    def _should_retry(self, exc: Exception, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False
        status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
        if status == 429:
            return True
        message = str(exc).lower()
        return "429" in message or "throttl" in message or "rate limit" in message

    def _retry_delay(self, exc: Exception, attempt: int) -> float:
        message = str(exc)
        match = re.search(r"reset(?:s)? in ~?(\\d+)s", message, re.IGNORECASE)
        if match:
            return min(self.max_delay_s, float(match.group(1)) + 1.0)
        base = min(self.max_delay_s, self.base_delay_s * (2 ** attempt))
        jitter = random.uniform(0, min(1.0, base * 0.1))
        return base + jitter

    @staticmethod
    def split_grid_image(
        *,
        grid_png: bytes,
        rows: int = 2,
        cols: int = 3,
        padding: int = 0,
    ) -> List[bytes]:
        """
        Best-effort helper for the case where a model returns a single PNG
        containing multiple views in a grid.

        Assumes all cells are equal size.
        """
        img = Image.open(io.BytesIO(grid_png)).convert("RGBA")
        w, h = img.size
        cell_w = (w - padding * (cols - 1)) // cols
        cell_h = (h - padding * (rows - 1)) // rows
        views: List[bytes] = []
        for r in range(rows):
            for c in range(cols):
                left = c * (cell_w + padding)
                top = r * (cell_h + padding)
                crop = img.crop((left, top, left + cell_w, top + cell_h))
                buf = io.BytesIO()
                crop.save(buf, format="PNG")
                views.append(buf.getvalue())
        return views
