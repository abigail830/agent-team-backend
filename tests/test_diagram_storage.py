import uuid

from app.proposal.storage import (
    artifact_download_filename,
    artifact_media_type,
    resolve_artifact_path,
    save_diagram_artifact,
)


def test_save_diagram_artifact_variants(tmp_path, monkeypatch):
    chat_id = uuid.uuid4()
    artifact_id = "diag-test123"
    monkeypatch.setattr("app.proposal.storage.ARTIFACTS_ROOT", tmp_path)

    save_diagram_artifact(
        chat_id,
        artifact_id,
        svg='<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        png=b"\x89PNG",
        filename_base="auth-flow",
    )

    svg_path = resolve_artifact_path(chat_id, artifact_id)
    png_path = resolve_artifact_path(chat_id, artifact_id, variant="png")
    assert svg_path is not None and svg_path.suffix == ".svg"
    assert png_path is not None and png_path.suffix == ".png"
    assert artifact_download_filename(chat_id, artifact_id) == "auth-flow.svg"
    assert artifact_download_filename(chat_id, artifact_id, variant="png") == "auth-flow.png"
    assert artifact_media_type(chat_id, artifact_id, variant="png") == "image/png"
