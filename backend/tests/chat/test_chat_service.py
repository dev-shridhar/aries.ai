import pytest
from app.services.chat.service import AriesTutorAgent
from app.services.mcp.service import MCPService


@pytest.mark.asyncio
async def test_agent_initialization():
    """Ensure the agent initializes with its dependencies."""
    mcp = MCPService()
    agent = AriesTutorAgent(mcp_service=mcp)
    assert agent.model == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_agent_process_message_mock():
    """Basic test for message processing (requires GROQ_API_KEY)."""
    # This might fail in CI if key is missing, but good for local dev
    import os

    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set")

    mcp = MCPService()
    agent = AriesTutorAgent(mcp_service=mcp)
    response = await agent.process_message("Hi, who are you?")
    assert len(response) > 0
