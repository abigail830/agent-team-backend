"""Proposal artifact specs streamed to the chat UI (preview / download)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ArtifactKind = Literal[
    "proposal_preview",
    "proposal_document",
    "proposal_word",
    "diagram_svg",
]
ArtifactFormat = Literal["markdown", "docx", "svg"]


class ArtifactSpec(BaseModel):
    kind: ArtifactKind
    title: str
    format: ArtifactFormat = "markdown"
    content: str
    filename: str
    artifact_id: str
    download_url: str | None = None
    png_download_url: str | None = None
    png_filename: str | None = None
    preview_truncated: bool = False
    source: str | None = None
