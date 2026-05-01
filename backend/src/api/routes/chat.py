from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.schemas.chat import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatSendResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
)
from src.auth.dependencies import get_current_user
from src.db.models.chat import ChatMessage, ChatSession
from src.db.models.user import User
from src.db.session import get_db


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


def _mock_assistant_reply(user_text: str) -> str:
    trimmed = user_text.strip()
    preview = trimmed[:120]
    return (
        "Thanks, I got your message: "
        f"'{preview}'. "
        "This is a temporary Farmly assistant reply for this Phase. "
        "AI advisory response will be added in the next phase."
    )


def _get_owned_session(db: Session, session_id: str, user_id: str) -> ChatSession | None:
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == session_id,
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSessionResponse]:
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.user_id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [_to_session_response(s) for s in sessions]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessageResponse]:
    session = _get_owned_session(db, session_id, current_user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    return [_to_message_response(m) for m in session.messages]


@router.post("/sessions/{session_id}/messages", response_model=ChatSendResponse)
def send_message(
    session_id: str,
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
        content=_mock_assistant_reply(text),
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
