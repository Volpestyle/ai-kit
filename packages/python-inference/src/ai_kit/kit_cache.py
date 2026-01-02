from __future__ import annotations

from typing import Callable, Dict

from .hub import Kit

_KIT_CACHE: Dict[str, Kit] = {}


def get_cached_kit(cache_key: str, factory: Callable[[], Kit]) -> Kit:
    cached = _KIT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    kit = factory()
    _KIT_CACHE[cache_key] = kit
    return kit


def list_provider_models(kit: Kit, provider: str, refresh: bool = False) -> list[str]:
    models = kit.list_models(providers=[provider], refresh=refresh)
    model_ids: list[str] = []
    seen: set[str] = set()
    for model in models or []:
        if isinstance(model, dict):
            model_id = model.get("id")
        else:
            model_id = getattr(model, "id", None)
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        model_ids.append(model_id)
    return model_ids
