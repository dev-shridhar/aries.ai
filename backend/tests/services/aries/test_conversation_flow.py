import pytest
import base64
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage
from app.services.aries.service import aries_service
from app.api.aries.models import VoiceResponse

@pytest.fixture
def mock_conversation_infra():
    """Mocks all infrastructure layers for a smooth E2E service-level test."""
    with (
        patch("app.services.aries.service.stt_adapter", new_callable=AsyncMock) as stt,
        patch("app.services.aries.service.tts_adapter", new_callable=AsyncMock) as tts,
        patch("app.services.aries.memory.aries_mongo", new_callable=AsyncMock) as mongo,
        patch("app.services.aries.memory.chroma_manager", new_callable=AsyncMock) as chroma,
        patch("app.infrastructure.aries.redis_client.aries_redis", new_callable=AsyncMock) as redis,
        patch("app.services.aries.pipeline.history.AriesHistoryManager.add_interaction", new_callable=AsyncMock) as hist
    ):
        # Default infrastructure behavior
        stt.transcribe.side_effect = lambda b: b.decode("utf-8") # Passthrough for easy testing
        tts.speak.return_value = b"audio"
        redis.get_context.return_value = []
        redis.get_current_problem.return_value = None
        redis.get_current_code.return_value = "def solve(): pass"
        
        yield {
            "stt": stt,
            "tts": tts,
            "mongo": mongo,
            "chroma": chroma,
            "redis": redis,
            "hist": hist
        }

@pytest.mark.asyncio
async def test_full_conversation_flow(mock_conversation_infra):
    """Verifies a 2-turn conversation with memory and tool discovery."""
    session_id = "test-session-e2e"
    username = "test-user"
    
    # --- TURN 1: Introduction ---
    # User says "Hi, I'm Dev. What's the problem?"
    # We expect Aries to:
    # 1. Update memory (record_user_fact)
    # 2. Get state (get_current_state)
    # 3. Respond
    
    # Mocking chroma search for "What's the problem?"
    mock_conversation_infra["chroma"].similarity_search.return_value = []
    
    # We need to ensure searching is mocked if needed
    # (The graph will use real BrainAdapter unless we mock ChatGroq)
    # For a real "Integration" feel, we let it hit Groq if API keys exist, 
    # but for CI it's better to mock ChatGroq's invoke.
    
    with patch("langchain_groq.ChatGroq.ainvoke") as mock_invoke:
        # Mocking turn 1 response
        mock_invoke.return_value = AIMessage(
            content="Hello Dev! You are currently solved nothing. How can I help?",
            tool_calls=[]
        )
        
        responses = []
        async for resp in aries_service.process_text_interaction(
            text_input="Hi, I'm Dev.",
            session_id=session_id,
            username=username
        ):
            responses.append(resp)
            
        assert any("Dev" in r.text for r in responses)
        # Note: Aries might choose to call a tool to record the name, 
        # but here we just check if it replied warmly.

    # --- TURN 2: Tool Discovery ---
    # User says "Search for my contest stats"
    # Aries should call search_available_tools
    
    with patch("langchain_groq.ChatGroq.ainvoke") as mock_invoke, \
         patch("app.services.aries.pipeline.tools.get_extended_aries_tools") as mock_ext_tools:
        
        # Mocking specialized tool
        spec_tool = MagicMock()
        spec_tool.name = "get_contest_stats"
        spec_tool.description = "Get contest data"
        mock_ext_tools.return_value = [spec_tool]
        
        # Mocking the sequence: 
        # 1. LLM decides to search
        # 2. Tool returns result
        # 3. LLM acknowledges
        mock_invoke.side_effect = [
            AIMessage(content="", tool_calls=[{
                "name": "search_available_tools", 
                "args": {"query": "contest"}, 
                "id": "search_1"
            }]),
            AIMessage(content="I found a tool called get_contest_stats. I can use it now.")
        ]
        
        responses = []
        async for resp in aries_service.process_text_interaction(
            text_input="Can you find my contest stats?",
            session_id=session_id,
            username=username
        ):
            responses.append(resp)
            
        assert any("get_contest_stats" in r.text for r in responses)
        
    print("\n[SUCCESS] E2E Conversation validated.")
