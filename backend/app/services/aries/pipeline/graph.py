import logging
import operator
import time
from collections.abc import Sequence
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.services.aries.pipeline.brain import brain_adapter
from app.services.aries.pipeline.tools import get_full_aries_tools

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

    This factory implements an 'Anthropic-style' deferred tool loading pattern:
    1. Core tools are always bound to the LLM.
    2. Specialized MCP tools are only bound IF discovered via 'search_available_tools'.
    3. The graph remains execute-ready for all tools via the ToolNode.

    Returns:
        Any: A compiled LangGraph `CompiledGraph` object ready for invocation.
    """
    global _cached_graph
    if _cached_graph:
        return _cached_graph

    logger.info("GRAPH: Compiling Aries dynamic reasoning loop...")

    # 1. Discover all possible tools (needed for the execution node)
    from app.services.aries.pipeline.tools import aries_core_tools, get_full_aries_tools, get_extended_aries_tools
    all_possible_tools = await get_full_aries_tools()
    extended_tools = await get_extended_aries_tools()

    # 2. Define the 'Agent' node with DYNAMIC tool binding
    async def call_model(state: AgentState) -> dict:
        """Invokes the LLM with a dynamically bound toolset."""
        messages = state["messages"]
        system_prompt = state.get("system_prompt", "You are Aries, a coding companion.")
        
        # Start with core tools
        active_tools = list(aries_core_tools)
        
        # Scan history for search_available_tools results
        # if the agent searched for tools, we "unlock" them in the LLM context
        from langchain_core.messages import ToolMessage
        import re
        
        discovered_names = set()
        for msg in messages:
            if isinstance(msg, ToolMessage) and msg.name == "search_available_tools":
                found = re.findall(r"- NAME: (\w+)", msg.content)
                discovered_names.update(found)
        
        if discovered_names:
            logger.info(f"GRAPH: Dynamically binding discovered tools: {discovered_names}")
            for t in extended_tools:
                if t.name in discovered_names:
                    active_tools.append(t)

        # Bind the active toolset to the LLM
        llm_with_tools = brain_adapter.groq_llm.bind_tools(active_tools)

        # Ensure the system prompt is always at the top
        full_messages = [SystemMessage(content=system_prompt)] + list(messages)

        logger.info(f"GRAPH: Invoking LLM with {len(active_tools)} tools bound.")
        t_start = time.time()
        response = await llm_with_tools.ainvoke(full_messages)
        logger.info(f"GRAPH: LLM invocation took {time.time() - t_start:.2f}s")

        return {"messages": [response]}

    # 3. Define Graph Topology
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(all_possible_tools)) # Execution node knows all

    # Define edges
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue)
    workflow.add_edge("tools", "agent")

    # 4. Persistence
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()

    _cached_graph = workflow.compile(checkpointer=checkpointer)
    logger.info("GRAPH: Aries Graph compiled with Dynamic Discovery pattern.")

    return _cached_graph


# Placeholder for backward compatibility during the LangChain migration.
aries_graph = None
