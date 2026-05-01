from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.schemas.chat import (
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
)
from src.auth.dependencies import get_current_user
from src.db.models.chat import ChatSession
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
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.user_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    return [
        ChatMessageResponse(
            message_id=m.message_id,
            session_id=m.session_id,
            sender=m.sender,
            content=m.content,
            sequence_no=m.sequence_no,
            created_at=m.created_at,
        )
        for m in session.messages
    ]
