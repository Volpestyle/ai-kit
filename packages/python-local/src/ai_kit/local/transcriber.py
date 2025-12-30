from __future__ import annotations

import base64
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple
from urllib.request import urlopen

from ai_kit.errors import AiKitError, ErrorKind, KitErrorPayload
from ai_kit.types import AudioInput, TranscriptSegment, TranscribeInput, TranscribeOutput

from .device import resolve_device


class LocalWhisperAdapter:
    provider = "local"

    def __init__(
        self,
        *,
        default_model: str = "base",
        device: object | None = None,
        download_root: Optional[str] = None,
    ) -> None:
        self.default_model = default_model
        self.device = device
        self.download_root = download_root

    def list_models(self):
        return []

    def transcribe(self, input: TranscribeInput) -> TranscribeOutput:
        model_name = input.model or self.default_model
        device = resolve_device(self.device)
        model = _load_whisper_model(model_name, str(device), self.download_root)
        audio_path, cleanup = _materialize_audio(input.audio)
        try:
            kwargs = {}
            if input.language:
                kwargs["language"] = input.language
            if input.prompt:
                kwargs["prompt"] = input.prompt
            if input.temperature is not None:
                kwargs["temperature"] = input.temperature
            kwargs["fp16"] = getattr(device, "type", str(device)) != "cpu"
            result = model.transcribe(audio_path, **kwargs)
        finally:
            if cleanup:
                Path(audio_path).unlink(missing_ok=True)
        segments = [
            TranscriptSegment(
                start=float(segment.get("start", 0)),
                end=float(segment.get("end", 0)),
                text=str(segment.get("text", "")),
            )
            for segment in result.get("segments", []) or []
            if isinstance(segment, dict)
        ]
        return TranscribeOutput(
            text=result.get("text"),
            language=result.get("language"),
            duration=result.get("duration"),
            segments=segments or None,
            raw=result,
        )


@lru_cache(maxsize=4)
def _load_whisper_model(model: str, device: str, download_root: Optional[str]):
    import whisper

    return whisper.load_model(model, device=device, download_root=download_root)


def _materialize_audio(audio: AudioInput) -> Tuple[str, bool]:
    if audio.path:
        return audio.path, False
    if audio.base64:
        data, media_type = _decode_base64(audio.base64, audio.mediaType)
        return _write_temp_audio(data, media_type), True
    if audio.url:
        with urlopen(audio.url) as response:
            data = response.read()
            media_type = audio.mediaType or response.headers.get("content-type")
        return _write_temp_audio(data, media_type), True
    raise AiKitError(
        KitErrorPayload(
            kind=ErrorKind.VALIDATION,
            message="Transcribe input requires audio.url, audio.base64, or audio.path",
            provider="local",
        )
    )


def _decode_base64(raw: str, explicit_type: Optional[str]) -> Tuple[bytes, str]:
    payload = raw
    media_type = explicit_type or ""
    if raw.startswith("data:"):
        header, _, payload = raw.partition(",")
        if not media_type and ";" in header:
            media_type = header.split(";", 1)[0].replace("data:", "")
    if not media_type:
        media_type = "application/octet-stream"
    return base64.b64decode(payload), media_type


def _write_temp_audio(data: bytes, media_type: Optional[str]) -> str:
    suffix = _suffix_for_media(media_type)
    with tempfile.NamedTemporaryFile(prefix="ai_kit_audio_", suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        return tmp.name


def _suffix_for_media(media_type: Optional[str]) -> str:
    if not media_type:
        return ".audio"
    normalized = media_type.lower()
    if "wav" in normalized:
        return ".wav"
    if "mpeg" in normalized:
        return ".mp3"
    if "mp4" in normalized:
        return ".mp4"
    if "webm" in normalized:
        return ".webm"
    if "ogg" in normalized:
        return ".ogg"
    return ".audio"
