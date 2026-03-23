import pytest
import re
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage, SystemMessage
from app.services.aries.pipeline.graph import get_aries_graph, AgentState

@pytest.fixture
async def sample_state():
    return {
        "messages": [
            HumanMessage(content="What are my stats?"),
            AIMessage(content="", tool_calls=[{"name": "search_available_tools", "args": {"query": "stats"}, "id": "call_1"}]),
            ToolMessage(
                content="Found the following specialized tools. You can now call them by name:\n- NAME: get_user_stats\n  DESC: Get LeetCode stats",
                name="search_available_tools",
                tool_call_id="call_1"
            )
        ],
        "session_id": "test_session",
        "username": "testuser",
        "system_prompt": "You are Aries."
    }

@pytest.fixture
def mock_extended_tools():
    # Create a mock tool with a .name attribute
    tool = MagicMock()
    tool.name = "get_user_stats"
    tool.description = "Get LeetCode stats"
    return [tool]

@pytest.mark.asyncio
async def test_dynamic_tool_binding(sample_state, mock_extended_tools):
    """Verify that specialized tools are bound ONLY after a search result is present."""
    
    # We need to mock brain_adapter.groq_llm.bind_tools
    # and get_extended_aries_tools
    
    with patch("app.services.aries.pipeline.tools.get_extended_aries_tools", return_value=mock_extended_tools), \
         patch("langchain_groq.ChatGroq.bind_tools") as mock_bind:
        
        # mock_bind needs to return a mock LLM that we can call ainvoke on
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="I found your stats."))
        mock_bind.return_value = mock_llm
        
        # Get the compiled graph
        # Note: get_aries_graph caches the graph, so we might need to reset it or test the node logic directly
        # For simplicity, let's test the call_model logic if we can access it, or just use the graph.
        
        from app.services.aries.pipeline.graph import get_aries_graph
        # Reset the cache for the test
        import app.services.aries.pipeline.graph as graph_module
        graph_module._cached_graph = None
        
        graph = await get_aries_graph()
        
        # The 'agent' node is the first one
        await graph.ainvoke(sample_state, config={"configurable": {"thread_id": "test_thread"}})
        
        # Verify mock_bind was called with get_user_stats in the list
        args, kwargs = mock_bind.call_args
        bound_tools = args[0]
        bound_names = [t.name if hasattr(t, 'name') else t.__name__ for t in bound_tools]
        
        assert "search_available_tools" in bound_names
        assert "get_user_stats" in bound_names
        assert "get_current_state" in bound_names # Also check core tools

@pytest.mark.asyncio
async def test_no_search_no_binding(mock_extended_tools):
    """Verify that specialized tools are NOT bound without a search result."""
    state = {
        "messages": [HumanMessage(content="Hello")],
        "session_id": "test_session",
        "username": "testuser",
        "system_prompt": "You are Aries."
    }
    
    with patch("app.services.aries.pipeline.tools.get_extended_aries_tools", return_value=mock_extended_tools), \
         patch("langchain_groq.ChatGroq.bind_tools") as mock_bind:
        
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Hi"))
        mock_bind.return_value = mock_llm
        
        import app.services.aries.pipeline.graph as graph_module
        graph_module._cached_graph = None
        graph = await get_aries_graph()
        
        await graph.ainvoke(state, config={"configurable": {"thread_id": "test_thread"}})
        
        args, kwargs = mock_bind.call_args
        bound_tools = args[0]
        bound_names = [t.name if hasattr(t, 'name') else t.__name__ for t in bound_tools]
        
        assert "get_user_stats" not in bound_names
        assert "search_available_tools" in bound_names
