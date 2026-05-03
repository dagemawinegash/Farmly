from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from src.db.models.chat import ChatMessage, ChatSession
from src.db.models.user import User, UserProfile
from src.db.session import get_db
from src.integrations.llm.gemini_adapter import generate_reply


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
        sequence_no=message.sequence_no,
        created_at=message.created_at,
    )


def _fallback_assistant_reply(user_text: str) -> str:
    trimmed = user_text.strip()
    preview = trimmed[:120]
    return (
        "Thanks, I got your message: "
        f"'{preview}'. "
        "This is a temporary Farmly fallback reply. "
        "AI advisory response will be improved in the next phase."
    )


def _split_crops(value: str | None) -> list[str]:
    if not value:
        return []
    return [crop.strip() for crop in value.split(",") if crop.strip()]


def _build_profile_context(profile: UserProfile | None) -> dict[str, str]:
    if not profile:
        return {}
    return {
        "full_name": profile.full_name or "",
        "location": profile.location or "",
        "preferred_language": profile.preferred_language or "",
        "user_type": profile.user_type or "",
        "years_experience": (
            str(profile.years_experience) if profile.years_experience is not None else ""
        ),
        "main_goal": profile.main_goal or "",
        "crops_grown": ", ".join(_split_crops(profile.crops_grown)),
    }


def _get_owned_session(db: Session, session_id: UUID, user_id: str) -> ChatSession | None:
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == str(session_id),
            ChatSession.user_id == user_id,
        )
        .first()
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
    payload: ChatMessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSendResponse:
    session = _get_owned_session(db, session_id, current_user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    text = payload.content.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty",
        )

    last_seq = (
        db.query(ChatMessage.sequence_no)
        .filter(ChatMessage.session_id == session.session_id)
        .order_by(ChatMessage.sequence_no.desc())
        .first()
    )
    next_seq = (last_seq[0] if last_seq else 0) + 1

    recent_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.session_id)
        .order_by(ChatMessage.sequence_no.desc())
        .limit(8)
        .all()
    )
    recent_messages = list(reversed(recent_messages))[-5:]

    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    profile_context = _build_profile_context(profile)

    try:
        assistant_text = generate_reply(
            latest_user_message=text,
            recent_messages=[
                {"sender": m.sender, "content": m.content} for m in recent_messages
            ],
            profile_context=profile_context,
        )
    except Exception:
        assistant_text = _fallback_assistant_reply(text)

    user_message = ChatMessage(
        session_id=session.session_id,
        sender="user",
        content=text,
        sequence_no=next_seq,
    )
    db.add(user_message)

    assistant_message = ChatMessage(
        session_id=session.session_id,
        sender="assistant",
        content=assistant_text,
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
