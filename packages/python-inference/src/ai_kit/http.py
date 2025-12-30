from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import requests

from .errors import KitErrorPayload, AiKitError, classify_status


def request_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    json_body: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    response = requests.request(
        method,
        url,
        headers=headers,
        json=json_body,
        timeout=timeout,
    )
    if response.status_code >= 400:
        body = (response.text or "").strip()
        message = body or f"Upstream HTTP {response.status_code} for {url}"
        raise AiKitError(
            KitErrorPayload(
                kind=classify_status(response.status_code),
                message=message,
                upstreamStatus=response.status_code,
            )
        )
    return response.json()


def request_stream(
    method: str,
    url: str,
    headers: Dict[str, str],
    json_body: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
):
    response = requests.request(
        method,
        url,
        headers=headers,
        json=json_body,
        timeout=timeout,
        stream=True,
    )
    if response.status_code >= 400:
        body = (response.text or "").strip()
        message = body or f"Upstream HTTP {response.status_code} for {url}"
        raise AiKitError(
            KitErrorPayload(
                kind=classify_status(response.status_code),
                message=message,
                upstreamStatus=response.status_code,
            )
        )
    return response


def request_multipart(
    method: str,
    url: str,
    headers: Dict[str, str],
    data: Optional[Dict[str, Any]] = None,
    file_field: Optional[Tuple[str, Tuple[str, bytes, str]]] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    files = None
    if file_field:
        field_name, file_tuple = file_field
        files = {field_name: file_tuple}
    response = requests.request(
        method,
        url,
        headers=headers,
        data=data,
        files=files,
        timeout=timeout,
    )
    if response.status_code >= 400:
        body = (response.text or "").strip()
        message = body or f"Upstream HTTP {response.status_code} for {url}"
        raise AiKitError(
            KitErrorPayload(
                kind=classify_status(response.status_code),
                message=message,
                upstreamStatus=response.status_code,
            )
        )
    return response.json()
