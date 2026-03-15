import os
from unittest.mock import AsyncMock, MagicMock, patch

# Mock environment
os.environ["DEEPGRAM_API_KEY"] = "fake_key"
os.environ["GROQ_API_KEY"] = "fake_key"

import pytest
from langchain_core.messages import AIMessage
from langgraph.graph import END

from app.services.aries.pipeline.graph import get_aries_graph, should_continue


@pytest.fixture
def mock_dependencies():
    with (
        patch(
            "app.services.aries.pipeline.graph.get_full_aries_tools",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.aries.pipeline.graph.brain_adapter", MagicMock()
        ) as mock_brain,
    ):
        # Mock the Groq LLM bind_tools
        mock_brain.groq_llm.bind_tools.return_value = AsyncMock()
        yield mock_brain


@pytest.mark.asyncio
async def test_get_aries_graph_caching(mock_dependencies):
    # Clear cache if any
    from app.services.aries.pipeline import graph

    graph._cached_graph = None

    graph1 = await get_aries_graph()
    graph2 = await get_aries_graph()

    assert graph1 is graph2
    assert graph1 is not None


def test_should_continue_end():
    state = {"messages": [AIMessage(content="Hello", tool_calls=[])]}
    result = should_continue(state)
    assert result == END


def test_should_continue_tools():
    state = {
        "messages": [
            AIMessage(
                content="", tool_calls=[{"name": "test_tool", "args": {}, "id": "1"}]
            )
        ]
    }
    result = should_continue(state)
    assert result == "tools"


@pytest.mark.asyncio
async def test_graph_compilation_structure(mock_dependencies):
    from app.services.aries.pipeline import graph

    graph._cached_graph = None

    compiled_graph = await get_aries_graph()

    # Check if nodes exist
    nodes = compiled_graph.nodes
    assert "agent" in nodes
    assert "tools" in nodes
