from datetime import datetime

from pydantic import BaseModel, Field


class ChatSessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)


class ChatSessionResponse(BaseModel):
    session_id: str
    user_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    message_id: str
    session_id: str
    sender: str
    content: str
    sequence_no: int
    created_at: datetime


class ChatMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatSendResponse(BaseModel):
    session_id: str
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
