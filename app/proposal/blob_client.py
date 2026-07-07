"""Minimal Vercel Blob REST client (Python backend has no official SDK)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_BLOB_API = "https://blob.vercel-storage.com"
_API_VERSION = "7"


def blob_storage_enabled() -> bool:
    settings = get_settings()
    mode = settings.artifact_storage.strip().lower()
    if mode == "local":
        return False
    if mode == "vercel_blob":
        return True
    return bool(_resolve_blob_token())


def _resolve_blob_token() -> str | None:
    settings = get_settings()
    token = (settings.blob_read_write_token or "").strip()
    return token or None


def _auth_headers(*, content_type: str | None = None) -> dict[str, str]:
    token = _resolve_blob_token()
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is required for Vercel Blob storage.")
    headers = {
        "authorization": f"Bearer {token}",
        "x-api-version": _API_VERSION,
    }
    if content_type:
        headers["content-type"] = content_type
    return headers


def blob_put(pathname: str, body: bytes | str, *, content_type: str) -> dict[str, Any]:
    settings = get_settings()
    payload = body.encode("utf-8") if isinstance(body, str) else body
    url = f"{_BLOB_API}/{pathname.lstrip('/')}"
    params = {
        "access": settings.blob_access,
        "addRandomSuffix": "false",
        "allowOverwrite": "true",
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.put(
            url,
            content=payload,
            headers=_auth_headers(content_type=content_type),
            params=params,
        )
    if response.status_code >= 400:
        detail = (response.text or "").strip() or response.reason_phrase
        raise RuntimeError(f"Vercel Blob upload failed ({response.status_code}): {detail}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Vercel Blob upload returned unexpected payload.")
    return data


def blob_get(pathname: str) -> bytes | None:
    url = f"{_BLOB_API}/{pathname.lstrip('/')}"
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=_auth_headers())
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        detail = (response.text or "").strip() or response.reason_phrase
        logger.warning("Vercel Blob read failed (%s): %s", response.status_code, detail)
        return None
    return response.content
