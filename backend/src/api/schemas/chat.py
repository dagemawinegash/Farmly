from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatSessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)


class ChatSessionUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class ChatSessionResponse(BaseModel):
    session_id: UUID
    user_id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    message_id: UUID
    session_id: UUID
    sender: str
    content: str
    sequence_no: int
    created_at: datetime


class ChatMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatSendResponse(BaseModel):
    session_id: UUID
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


class ChatDeleteResponse(BaseModel):
    message: str
    session_id: UUID
