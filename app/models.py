from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    system: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    forceClassicChat: bool = False
    backendAuthToken: str | None = None

