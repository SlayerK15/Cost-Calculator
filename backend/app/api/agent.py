"""AI Agent chatbot API with SSE streaming."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.agent import AgentChatRequest
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agent", tags=["agent"])

_agent = AgentService()


@router.post("/chat")
async def agent_chat(req: AgentChatRequest):
    """
    Chat with the AI assistant. Returns SSE stream.
    Works without auth — the agent uses public tools only.
    """
    async def event_stream():
        full_response = ""
        async for chunk in _agent.chat(
            message=req.message,
            context=req.context,
            history=req.history,
        ):
            full_response += chunk
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/sync")
async def agent_chat_sync(req: AgentChatRequest):
    """Non-streaming version of the agent chat. Returns full response."""
    full_response = ""
    async for chunk in _agent.chat(
        message=req.message,
        context=req.context,
        history=req.history,
    ):
        full_response += chunk

    return {"message": full_response}
