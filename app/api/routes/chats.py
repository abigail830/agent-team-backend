import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AttachmentOut,
    ChatCreate,
    ChatListOut,
    ChatOut,
    MessageCreate,
    MessageOut,
    ProposalDraftOut,
    ProposalExportOut,
    ProposalExportRequest,
    ProposalPreviewOut,
)
from app.db.models import AgentModel, Chat
from app.platform.current_user import get_current_user, get_current_user_id, get_owned_chat
from app.db.session import get_db
from app.services.attachment_service import AttachmentService
from app.services.chat_run import ChatRunService, list_chat_messages
from app.services.stream_errors import user_facing_stream_error
from app.services.proposal_preview_service import get_chat_proposal_draft, get_chat_proposal_preview, load_chat_proposal_draft
from app.proposal.export_service import ProposalExportError, generate_proposal_docx
from app.proposal.storage import load_artifact_payload

router = APIRouter(prefix="/chats", tags=["chats"])


def _chat_list_out(chat: Chat) -> ChatListOut:
    return ChatListOut(
        id=chat.id,
        agent_id=chat.agent_id,
        title=chat.title,
        created_at=chat.created_at.isoformat() if chat.created_at else None,
        updated_at=chat.updated_at.isoformat() if chat.updated_at else None,
    )


@router.get("", response_model=list[ChatListOut])
async def list_chats(
    agent_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[ChatListOut]:
    result = await db.execute(
        select(Chat)
        .where(
            Chat.user_id == user_id,
            Chat.agent_id == agent_id,
        )
        .order_by(Chat.updated_at.desc())
        .limit(50)
    )
    return [_chat_list_out(c) for c in result.scalars().all()]


@router.post("", response_model=ChatOut, status_code=201)
async def create_chat(
    body: ChatCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    agent = await db.get(AgentModel, body.agent_id)
    if agent is None or agent.slug is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    chat = Chat(
        user_id=user_id,
        agent_id=body.agent_id,
        title=body.title or "New Chat",
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return ChatOut(id=chat.id, user_id=chat.user_id, agent_id=chat.agent_id, title=chat.title)


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def get_messages(
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    rows = await list_chat_messages(db, chat.id)
    return [MessageOut(**row) for row in rows]


@router.get("/{chat_id}/proposal/preview", response_model=ProposalPreviewOut)
async def get_proposal_preview(
    chat: Chat = Depends(get_owned_chat),
    draft: bool = True,
    db: AsyncSession = Depends(get_db),
) -> ProposalPreviewOut:
    try:
        payload = await get_chat_proposal_preview(db, chat.id, draft=draft)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProposalPreviewOut(**payload)


@router.get("/{chat_id}/proposal/draft", response_model=ProposalDraftOut)
async def get_proposal_draft(
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> ProposalDraftOut:
    try:
        payload = await get_chat_proposal_draft(db, chat.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProposalDraftOut(**payload)


@router.post("/{chat_id}/proposal/export", response_model=ProposalExportOut)
async def export_proposal(
    body: ProposalExportRequest,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> ProposalExportOut:
    if body.format != "docx":
        raise HTTPException(status_code=422, detail="Only format=docx is supported.")
    try:
        draft = await load_chat_proposal_draft(db, chat.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not draft:
        raise HTTPException(status_code=422, detail="Proposal draft is not initialized.")
    try:
        payload = generate_proposal_docx(draft, chat_id=chat.id, force=body.force, persist=True)
    except ProposalExportError as exc:
        detail: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.code == "blocked":
            from app.proposal.draft import build_draft_preview

            preview = build_draft_preview(draft)
            detail["missing_required"] = (preview.get("completeness") or {}).get("missing_required") or []
        raise HTTPException(status_code=exc.http_status, detail=detail) from exc
    return ProposalExportOut(**payload)


@router.get("/{chat_id}/artifacts/{artifact_id}")
async def download_artifact(
    artifact_id: str,
    chat: Chat = Depends(get_owned_chat),
    format: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    _ = db
    variant = format.strip().lower() if format else None
    payload = load_artifact_payload(chat.id, artifact_id, variant=variant)
    if payload is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return StreamingResponse(
        iter([payload.data]),
        media_type=payload.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{payload.filename}"',
        },
    )


@router.post("/{chat_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> AttachmentOut:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    data = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    service = AttachmentService(db)
    try:
        payload = await service.upload(
            chat.id,
            filename=file.filename,
            mime_type=mime_type,
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"File upload failed: {exc}") from exc

    return AttachmentOut(
        id=uuid.UUID(payload["id"]),
        chat_id=chat.id,
        filename=payload["filename"],
        mime_type=payload["mime_type"],
        size_bytes=payload["size_bytes"],
        provider=payload["provider"],
        provider_file_id=payload["provider_file_id"],
        created_at=None,
    )


@router.post("/{chat_id}/messages")
async def post_message(
    body: MessageCreate,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ChatRunService(db)
    try:
        text = await service.run_message(
            chat.id,
            body.content,
            attachment_ids=body.attachment_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"chat_id": str(chat.id), "text": text}


@router.post("/{chat_id}/stream")
async def stream_message(
    body: MessageCreate,
    chat: Chat = Depends(get_owned_chat),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    service = ChatRunService(db)

    def _stream_error_message(exc: Exception) -> str:
        return user_facing_stream_error(exc)

    async def event_generator():
        try:
            async for event in service.stream_message(
                chat.id,
                body.content,
                attachment_ids=body.attachment_ids,
            ):
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
        except ValueError as exc:
            payload = {"error": str(exc)}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as exc:
            payload = {"error": _stream_error_message(exc)}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
