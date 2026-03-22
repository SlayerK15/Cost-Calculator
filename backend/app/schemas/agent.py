from pydantic import BaseModel
from typing import Optional


class AgentChatRequest(BaseModel):
    message: str
    context: dict = {}  # {page, selected_model, etc.}
    history: list[dict] = []  # [{role, content}]


class AgentToolCall(BaseModel):
    tool_name: str
    arguments: dict
    result: str


class AgentChatResponse(BaseModel):
    message: str
    tool_calls: list[AgentToolCall] = []
