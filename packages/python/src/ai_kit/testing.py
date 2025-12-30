from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List

from .errors import ErrorKind, AiKitError, KitErrorPayload
from .types import (
    GenerateInput,
    GenerateOutput,
    ImageGenerateInput,
    ImageGenerateOutput,
    MeshGenerateInput,
    MeshGenerateOutput,
    ModelMetadata,
    Provider,
    StreamChunk,
    as_json_dict,
)

FixtureInput = GenerateInput | ImageGenerateInput | MeshGenerateInput


@dataclass
class FixtureKeyInput:
    type: str
    input: FixtureInput


@dataclass
class FixtureEntry:
    generate: GenerateOutput | None = None
    stream: List[StreamChunk] | None = None
    image: ImageGenerateOutput | None = None
    mesh: MeshGenerateOutput | None = None


@dataclass
class FixtureCalls:
    generate: List[GenerateInput] = field(default_factory=list)
    stream_generate: List[GenerateInput] = field(default_factory=list)
    generate_image: List[ImageGenerateInput] = field(default_factory=list)
    generate_mesh: List[MeshGenerateInput] = field(default_factory=list)


class FixtureAdapter:
    def __init__(
        self,
        provider: Provider,
        fixtures: Dict[str, FixtureEntry],
        models: List[ModelMetadata] | None = None,
        key_fn: Callable[[FixtureKeyInput], str] | None = None,
        default_chunk_size: int = 24,
    ) -> None:
        self.provider = provider
        self.fixtures = fixtures
        self.models = models or []
        self.key_fn = key_fn or fixture_key
        self.default_chunk_size = default_chunk_size
        self.calls = FixtureCalls()

    def list_models(self):
        return self.models

    def generate(self, input: GenerateInput) -> GenerateOutput:
        self.calls.generate.append(input)
        entry = self._require_fixture("generate", input)
        if entry.generate is None:
            raise self._missing_fixture_error("generate", input)
        return entry.generate

    def stream_generate(self, input: GenerateInput) -> Iterable[StreamChunk]:
        self.calls.stream_generate.append(input)
        entry = self._require_fixture("stream", input)
        if entry.stream is not None:
            return iter(entry.stream)
        if entry.generate is None:
            raise self._missing_fixture_error("stream", input)
        return iter(build_stream_chunks(entry.generate, self.default_chunk_size))

    def generate_image(self, input: ImageGenerateInput) -> ImageGenerateOutput:
        self.calls.generate_image.append(input)
        entry = self._require_fixture("image", input)
        if entry.image is None:
            raise self._missing_fixture_error("image", input)
        return entry.image

    def generate_mesh(self, input: MeshGenerateInput) -> MeshGenerateOutput:
        self.calls.generate_mesh.append(input)
        entry = self._require_fixture("mesh", input)
        if entry.mesh is None:
            raise self._missing_fixture_error("mesh", input)
        return entry.mesh

    def _require_fixture(self, kind: str, input: FixtureInput):
        key = self.key_fn(FixtureKeyInput(type=kind, input=input))
        entry = self.fixtures.get(key)
        if entry is None:
            raise AiKitError(
                KitErrorPayload(
                    kind=ErrorKind.VALIDATION,
                    message=f"Fixture not found (key: {key}).",
                    provider=self.provider,
                )
            )
        return entry

    def _missing_fixture_error(self, kind: str, input: FixtureInput) -> AiKitError:
        key = self.key_fn(FixtureKeyInput(type=kind, input=input))
        return AiKitError(
            KitErrorPayload(
                kind=ErrorKind.VALIDATION,
                message=f"Fixture for {kind} is missing (key: {key}).",
                provider=self.provider,
            )
        )


def fixture_key(input: FixtureKeyInput) -> str:
    payload = {
        "type": input.type,
        "provider": input.input.provider,
        "model": input.input.model,
        "input": as_json_dict(input.input),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"{input.type}:{input.input.provider}:{input.input.model}:{digest}"


def build_stream_chunks(output: GenerateOutput, chunk_size: int) -> List[StreamChunk]:
    chunks: List[StreamChunk] = []
    if output.text:
        for part in _chunk_text(output.text, chunk_size):
            chunks.append(StreamChunk(type="delta", textDelta=part))
    if output.toolCalls:
        for call in output.toolCalls:
            chunks.append(StreamChunk(type="tool_call", call=call))
    chunks.append(
        StreamChunk(
            type="message_end",
            usage=output.usage,
            finishReason=output.finishReason,
        )
    )
    return chunks


def _chunk_text(text: str, chunk_size: int) -> List[str]:
    if not text:
        return []
    if chunk_size <= 0:
        return [text]
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]
