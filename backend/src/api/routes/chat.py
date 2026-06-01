from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from src.api.schemas.chat import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatDeleteResponse,
    ChatSendResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
)
from src.auth.dependencies import get_current_user
from src.config.settings import get_settings
from src.db.models.chat import ChatMessage, ChatSession
from src.db.models.user import User, UserProfile
from src.db.session import get_db
from src.integrations.voice.hasab_client import translate_text_with_hasab
from src.integrations.voice.google_stt import transcribe_audio
from src.services.chat_orchestrator import run_chat_orchestrator
from src.services.language import language_name, language_to_bcp47, normalize_app_language


router = APIRouter(prefix="/api/chat", tags=["Chat"])


def _to_session_response(session: ChatSession) -> ChatSessionResponse:
    return ChatSessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _to_message_response(message: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        message_id=message.message_id,
        session_id=message.session_id,
        sender=message.sender,
        content=message.content,
        content_type=message.content_type or "text",
        message_content_english=message.message_content_english,
        media_url=message.media_url,
        language_used=message.language_used,
        sequence_no=message.sequence_no,
        created_at=message.created_at,
    )


def _get_owned_session(db: Session, session_id: UUID, user_id: str) -> ChatSession | None:
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == str(session_id),
            ChatSession.user_id == user_id,
        )
        .first()
    )


def _read_audio_upload(audio: UploadFile) -> bytes:
    content_type = (audio.content_type or "").lower()
    if not content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be an audio file.",
        )

    audio_bytes = audio.file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio is empty.",
        )

    settings = get_settings()
    if len(audio_bytes) > settings.voice_audio_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded audio is too large.",
        )

    return audio_bytes


def _translate_amharic_to_english(text: str) -> str:
    return translate_text_with_hasab(
        text,
        source_language="am-ET",
        target_language="en-US",
    )


def _translate_english_to_amharic(text: str) -> str:
    return translate_text_with_hasab(
        text,
        source_language="en-US",
        target_language="am-ET",
    )


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    title = payload.title.strip() if payload.title else "New chat"
    session = ChatSession(
        user_id=current_user.user_id,
        title=title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _to_session_response(session)


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_my_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSessionResponse]:
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.user_id)
        .order_by(ChatSession.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_to_session_response(s) for s in sessions]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_session_messages(
    session_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessageResponse]:
    session = _get_owned_session(db, session_id, current_user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.session_id)
        .order_by(ChatMessage.sequence_no.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_to_message_response(m) for m in messages]


@router.post("/sessions/{session_id}/messages", response_model=ChatSendResponse)
def send_message(
    session_id: UUID,
    message: str | None = Form(default=None),
    language_code: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    audio: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSendResponse:
    session = _get_owned_session(db, session_id, current_user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    text = (message or "").strip()
    if image is None and audio is None and not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide message, image, or audio",
        )

    image_bytes: bytes | None = None
    image_mime_type: str | None = None
    if image is not None:
        content_type = (image.content_type or "").lower()
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file must be an image.",
            )
        image_bytes = image.file.read()
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image is empty.",
            )
        image_mime_type = content_type

    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    effective_language = language_code or (profile.preferred_language if profile else None)
    normalized_language = normalize_app_language(effective_language, default="en")
    bcp47_language = language_to_bcp47(effective_language)
    language_used = language_name(normalized_language)

    transcript: str | None = None
    user_content_english: str | None = None
    media_url: str | None = None
    if audio is not None:
        audio_bytes = _read_audio_upload(audio)
        try:
            transcription = transcribe_audio(
                audio_bytes,
                language_code=bcp47_language,
                filename=audio.filename or "voice-message.webm",
                content_type=audio.content_type or "audio/webm",
                translate_to_english=normalized_language == "am",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Voice transcription failed: {exc}",
            ) from exc

        transcript = transcription.transcript.strip()
        user_content_english = transcription.translation
        media_url = transcription.media_url
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not transcribe uploaded audio.",
            )
        text = transcript

    content_type = "audio" if audio is not None else "image" if image is not None else "text"
    user_content = text if text else "[image uploaded for diagnosis]"
    if not user_content_english and normalized_language == "en":
        user_content_english = user_content
    elif not user_content_english and normalized_language == "am" and text:
        try:
            user_content_english = _translate_amharic_to_english(user_content)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Amharic-to-English translation failed: {exc}",
            ) from exc

    chosen_route, assistant_text_english = run_chat_orchestrator(
        db=db,
        session_id=session.session_id,
        profile=profile,
        message=user_content_english or user_content,
        image_bytes=image_bytes,
        image_mime_type=image_mime_type,
        language_code=bcp47_language,
    )
    assistant_text = assistant_text_english
    if normalized_language == "am":
        try:
            assistant_text = _translate_english_to_amharic(assistant_text_english)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"English-to-Amharic translation failed: {exc}",
            ) from exc

    last_seq = (
        db.query(ChatMessage.sequence_no)
        .filter(ChatMessage.session_id == session.session_id)
        .order_by(ChatMessage.sequence_no.desc())
        .first()
    )
    next_seq = (last_seq[0] if last_seq else 0) + 1

    user_message = ChatMessage(
        session_id=session.session_id,
        sender="user",
        content=user_content,
        content_type=content_type,
        message_content_english=user_content_english,
        media_url=media_url,
        language_used=language_used,
        sequence_no=next_seq,
    )
    db.add(user_message)

    assistant_message = ChatMessage(
        session_id=session.session_id,
        sender="assistant",
        content=assistant_text,
        content_type="text",
        message_content_english=assistant_text_english,
        media_url=None,
        language_used=language_used,
        sequence_no=next_seq + 1,
    )
    db.add(assistant_message)

    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return ChatSendResponse(
        session_id=session.session_id,
        user_message=_to_message_response(user_message),
        assistant_message=_to_message_response(assistant_message),
        chosen_route=chosen_route,
        transcript=transcript,
    )


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
def rename_session(
    session_id: UUID,
    payload: ChatSessionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    session = _get_owned_session(db, session_id, current_user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    title = payload.title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session title cannot be empty",
        )

    session.title = title
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return _to_session_response(session)


@router.delete("/sessions/{session_id}", response_model=ChatDeleteResponse)
def delete_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatDeleteResponse:
    session = _get_owned_session(db, session_id, current_user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    deleted_id = UUID(session.session_id)
    db.delete(session)
    db.commit()
    return ChatDeleteResponse(
        message="Chat session deleted successfully",
        session_id=deleted_id,
    )
