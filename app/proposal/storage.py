"""Persist generated proposal documents for download."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = _BACKEND_ROOT / "data" / "proposal-artifacts"

ArtifactFormat = Literal["markdown", "docx", "svg", "png"]

_FORMAT_EXTENSIONS: dict[ArtifactFormat, str] = {
    "markdown": ".md",
    "docx": ".docx",
    "svg": ".svg",
    "png": ".png",
}

_MEDIA_TYPES: dict[ArtifactFormat, str] = {
    "markdown": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "svg": "image/svg+xml",
    "png": "image/png",
}


def new_artifact_id(*, prefix: str = "prop") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _meta_path(chat_id: uuid.UUID, artifact_id: str) -> Path:
    return ARTIFACTS_ROOT / str(chat_id) / f"{artifact_id}.meta.json"


def _load_meta(chat_id: uuid.UUID, artifact_id: str) -> dict:
    meta_path = _meta_path(chat_id, artifact_id)
    if not meta_path.is_file():
        return {}
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_meta(chat_id: uuid.UUID, artifact_id: str, *, filename: str, format: ArtifactFormat) -> None:
    meta_path = _meta_path(chat_id, artifact_id)
    meta_path.write_text(
        json.dumps(
            {
                "filename": filename,
                "format": format,
                "media_type": _MEDIA_TYPES[format],
            }
        ),
        encoding="utf-8",
    )


def save_markdown(chat_id: uuid.UUID, artifact_id: str, content: str, *, filename: str) -> Path:
    return save_artifact(
        chat_id,
        artifact_id,
        content=content,
        filename=filename,
        format="markdown",
    )


def _variant_meta(meta: dict, variant: str | None) -> dict:
    if not variant:
        return meta
    variants = meta.get("variants")
    if not isinstance(variants, dict):
        return {}
    entry = variants.get(variant)
    return entry if isinstance(entry, dict) else {}


def save_diagram_artifact(
    chat_id: uuid.UUID,
    artifact_id: str,
    *,
    svg: str,
    png: bytes,
    filename_base: str,
) -> None:
    chat_dir = ARTIFACTS_ROOT / str(chat_id)
    chat_dir.mkdir(parents=True, exist_ok=True)
    (chat_dir / f"{artifact_id}.svg").write_text(svg, encoding="utf-8")
    (chat_dir / f"{artifact_id}.png").write_bytes(png)
    svg_filename = f"{filename_base}.svg"
    png_filename = f"{filename_base}.png"
    _meta_path(chat_id, artifact_id).write_text(
        json.dumps(
            {
                "filename": svg_filename,
                "format": "svg",
                "media_type": _MEDIA_TYPES["svg"],
                "variants": {
                    "png": {
                        "filename": png_filename,
                        "format": "png",
                        "media_type": _MEDIA_TYPES["png"],
                        "extension": ".png",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def save_artifact(
    chat_id: uuid.UUID,
    artifact_id: str,
    *,
    filename: str,
    format: ArtifactFormat,
    content: str | None = None,
    binary: bytes | None = None,
) -> Path:
    chat_dir = ARTIFACTS_ROOT / str(chat_id)
    chat_dir.mkdir(parents=True, exist_ok=True)
    ext = _FORMAT_EXTENSIONS[format]
    path = chat_dir / f"{artifact_id}{ext}"
    if format in {"markdown", "svg"}:
        path.write_text(content or "", encoding="utf-8")
    else:
        path.write_bytes(binary or b"")
    _write_meta(chat_id, artifact_id, filename=filename, format=format)
    return path


def artifact_download_filename(chat_id: uuid.UUID, artifact_id: str, *, variant: str | None = None) -> str:
    meta = _load_meta(chat_id, artifact_id)
    entry = _variant_meta(meta, variant)
    name = str(entry.get("filename") or meta.get("filename") or "").strip()
    if name:
        return name
    if variant == "png":
        return f"diagram-{artifact_id[:8]}.png"
    return f"proposal-{artifact_id[:8]}.md"


def artifact_media_type(chat_id: uuid.UUID, artifact_id: str, *, variant: str | None = None) -> str:
    meta = _load_meta(chat_id, artifact_id)
    entry = _variant_meta(meta, variant)
    media_type = str(entry.get("media_type") or meta.get("media_type") or "").strip()
    if media_type:
        return media_type
    artifact_format = str(entry.get("format") or meta.get("format") or "markdown").strip()
    return _MEDIA_TYPES.get(artifact_format, _MEDIA_TYPES["markdown"])  # type: ignore[arg-type]


def resolve_artifact_path(chat_id: uuid.UUID, artifact_id: str, *, variant: str | None = None) -> Path | None:
    if not artifact_id or ".." in artifact_id or "/" in artifact_id:
        return None
    chat_dir = (ARTIFACTS_ROOT / str(chat_id)).resolve()
    meta = _load_meta(chat_id, artifact_id)
    if variant:
        entry = _variant_meta(meta, variant)
        ext = str(entry.get("extension") or _FORMAT_EXTENSIONS.get(variant, "")).strip()  # type: ignore[arg-type]
        if ext:
            path = (chat_dir / f"{artifact_id}{ext}").resolve()
            if str(path).startswith(str(chat_dir)) and path.is_file():
                return path
        return None
    artifact_format = str(meta.get("format") or "").strip()
    candidates: list[str] = []
    if artifact_format in _FORMAT_EXTENSIONS:
        candidates.append(f"{artifact_id}{_FORMAT_EXTENSIONS[artifact_format]}")  # type: ignore[index]
    candidates.extend([f"{artifact_id}.md", f"{artifact_id}.docx", f"{artifact_id}.svg", f"{artifact_id}.png"])
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        path = (chat_dir / name).resolve()
        if not str(path).startswith(str(chat_dir)):
            continue
        if path.is_file():
            return path
    return None
