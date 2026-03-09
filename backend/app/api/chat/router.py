import logging
from fastapi import APIRouter, HTTPException

from app.core.chat.models import ChatRequest, ChatResponse
from app.core.database.manager import db_manager
from app.services.chat.service import AriesTutorAgent
from app.services.mcp.service import MCPService
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()
mcp_service = MCPService()
tutor_agent = AriesTutorAgent(mcp_service)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        # 1. Handle Session
        session_id = req.session_id or str(uuid.uuid4())
        await db_manager.get_or_create_session(session_id)

        # 2. Save User Message
        await db_manager.save_message(session_id, "user", req.message)

        # 3. Get Chat History
        history = await db_manager.get_chat_history(session_id)

        # 4. Prepare Context
        context = ""
        if req.problem_title and req.problem_slug:
            context = f"Current Problem: {req.problem_title} (slug: {req.problem_slug})"

        # 5. Process with Agent (passing history)
        response_text = await tutor_agent.process_message(
            req.message, session_id=session_id, user_context=context, history=history
        )

        # 6. Save Assistant Response
        await db_manager.save_message(session_id, "assistant", response_text)

        return ChatResponse(response=response_text, session_id=session_id)
    except Exception as e:
        logger.exception("chat_endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    try:
        history = await db_manager.get_chat_history(session_id)
        return {"history": history}
    except Exception as e:
        logger.exception("get_history failed")
        raise HTTPException(status_code=500, detail=str(e))
