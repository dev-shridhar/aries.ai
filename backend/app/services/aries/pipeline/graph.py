import logging
import operator
from collections.abc import Sequence
from typing import Annotated, Any, TypedDict

from app.services.aries.pipeline.brain import brain_adapter
from app.services.aries.pipeline.tools import get_full_aries_tools
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """The state schema for the Aries LangGraph agent.

    This dictionary tracks the conversation flow and provides the LLM with
    the necessary sensory context for decision-making.

    Attributes:
        messages (Annotated[Sequence[BaseMessage], operator.add]): The cumulative
            list of messages in the current reasoning loop.
        session_id (str): The unique identifier for the user's active session.
        username (str): The name of the user for personalized memory recall.
        system_prompt (str): The dynamic instruction set used to guide Aries' behavior.
    """

    messages: Annotated[Sequence[BaseMessage], operator.add]
    session_id: str
    username: str
    system_prompt: str


# --- UTILITIES ---


def should_continue(state: AgentState) -> str:
    """Determines the next path in the LangGraph reasoning loop.

    If the last message from the AI contains tool calls, the graph routes
    to the 'tools' node. Otherwise, it ends the conversation turn.

    Args:
        state (AgentState): The current state of the agent.

    Returns:
        str: Either the name of the next node ('tools') or the 'END' signal.
    """
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return END

    return "tools"


# --- DYNAMIC GRAPH FACTORY ---

# Global cache to prevent redundant graph compilation.
_cached_graph = None


async def get_aries_graph() -> Any:
    """Dynamically compiles the Aries LangGraph with the latest tools.

    This factory performs the following steps:
    1. Discovers all core and MCP (External) tools.
    2. Binds these tools to the primary LLM (BrainAdapter).
    3. Defines the 'agent' node for reasoning and 'tools' node for execution.
    4. Compiles the cyclic graph with conditional routing.

    Returns:
        Any: A compiled LangGraph `CompiledGraph` object ready for invocation.
    """
    global _cached_graph
    if _cached_graph:
        return _cached_graph

    logger.info("GRAPH: Compiling Aries dynamic reasoning loop...")

    # 1. Discover all tools (Core Sensing + LeetCode MCP)
    all_tools = await get_full_aries_tools()

    # 2. Bind Tools to LLM (Provides the LLM with the ability to call tools)
    llm_with_tools = brain_adapter.groq_llm.bind_tools(all_tools)

    # 3. Define the 'Agent' node logic
    async def call_model(state: AgentState) -> dict:
        """Invokes the LLM with the current state and system prompt."""
        messages = state["messages"]
        system_prompt = state.get("system_prompt", "You are Aries, a coding companion.")

        # Ensure the system prompt is always at the top of the message list
        full_messages = [SystemMessage(content=system_prompt)] + list(messages)

        logger.info(f"GRAPH: Invoking LLM for session {state.get('session_id')}")
        response = await llm_with_tools.ainvoke(full_messages)

        # Update the state with the model's response
        return {"messages": [response]}

    # 4. Define Graph Topology
    workflow = StateGraph(AgentState)

    # Add primary nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(all_tools))

    # Define edges and routing
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")

    # Compile and cache
    _cached_graph = workflow.compile()
    logger.info("GRAPH: Aries Graph compiled successfully.")

    return _cached_graph


# Placeholder for backward compatibility during the LangChain migration.
aries_graph = None
