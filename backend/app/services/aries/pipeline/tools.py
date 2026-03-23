import asyncio
import logging
import time
from typing import Any

from langchain_core.tools import tool

from app.infrastructure.aries.chroma_client import chroma_manager
from app.infrastructure.aries.redis_client import aries_redis

logger = logging.getLogger(__name__)


class AriesTools:
    """Standardized tools for the Aries Brain to interact with system state and memory.

    This class provides the core 'Sensory' and 'Retrieval' tools that enable Aries
    to be an autonomous agent. Instead of 'stuffing' the prompt with all context,
    Aries uses these tools to pull exactly what it needs when it needs it.
    """

    @staticmethod
    @tool
    async def get_recent_history(session_id: str, limit: int = 10) -> str:
        """Retrieves the last N messages from the current conversation session.

        Use this tool when you need context from 5-10 minutes ago that is not present
        in your immediate context window. It helps in maintaining continuity.

        Args:
            session_id (str): The unique identifier for the current user session.
            limit (int, optional): Number of messages to retrieve. Defaults to 10.

        Returns:
            str: A formatted string of the conversation history for LLM consumption.
        """
        try:
            history = await aries_redis.get_context(session_id)
            # Format as simple text for the LLM to read easily
            formatted = "\n".join(
                [f"{m['role'].upper()}: {m['content']}" for m in history[-limit:]]
            )
            return formatted or "No recent history found."
        except Exception as e:
            logger.error(f"TOOL_ERROR (get_recent_history): {e}")
            return f"Error retrieving history: {str(e)}"

    @staticmethod
    @tool
    async def get_current_state(session_id: str) -> str:
        """Retrieves the 'Sensory State' of the integrated development environment.

        Fetches information about what the user is currently doing, including
        the code in their editor and the metadata of the problem they are solving.

        Args:
            session_id (str): The unique identifier for the current user session.

        Returns:
            str: A multi-line summary of the editor content and active problem state.
        """
        try:
            code = await aries_redis.get_current_code(session_id)
            problem = await aries_redis.get_current_problem(session_id)

            state = f"--- CURRENT EDITOR CODE ---\n{code or 'Editor is empty.'}\n\n"
            if problem:
                state += (
                    f"--- ACTIVE PROBLEM ---\n"
                    f"Title: {problem.get('title')}\n"
                    f"Slug: {problem.get('slug')}\n"
                    f"Difficulty: {problem.get('difficulty')}"
                )
            else:
                state += "--- ACTIVE PROBLEM ---\nNo problem currently loaded."

            return state
        except Exception as e:
            logger.error(f"TOOL_ERROR (get_current_state): {e}")
            return f"Error retrieving state: {str(e)}"

    @staticmethod
    @tool
    async def search_memory_palace(query: str, username: str) -> str:
        """Searches the 'Memory Palace' (Semantic Memory) for user-specific facts.

        Use this tool to recall preferences, names, past mistakes, or technical
        strengths/weaknesses stored across sessions.

        Args:
            query (str): The semantic search query (e.g., 'What is the user's name?').
            username (str): The unique identifier for the user.

        Returns:
            str: A list of relevant facts retrieved from ChromaDB.
        """
        try:
            # PHASE 2: High-performance vector search in ChromaDB
            t_start = time.time()
            results = await chroma_manager.similarity_search(
                collection_name="user_memory",
                query=query,
                limit=3,
                filter={"username": username},
            )
            logger.info(f"TOOL: search_memory_palace took {time.time() - t_start:.2f}s")

            if not results:
                return f"No memories found for query: '{query}'"

            formatted = "\n".join(
                [
                    f"- {r['metadata'].get('concept', 'fact')}: {r['content']}"
                    for r in results
                ]
            )
            return f"Found relevant memories:\n{formatted}"
        except Exception as e:
            logger.error(f"TOOL_ERROR (search_memory_palace): {e}")
            return f"Error searching memory: {str(e)}"
    @staticmethod
    @tool
    async def trigger_load_problem(slug: str) -> str:
        """Load a LeetCode problem by its slug."""
        return f"SIGNAL:ACTION:LOAD_PROBLEM:{slug}"

    @staticmethod
    @tool
    async def trigger_run_code() -> str:
        """Run the current code."""
        return "SIGNAL:ACTION:RUN_CODE"

    @staticmethod
    @tool
    async def trigger_submit_code() -> str:
        """Submit the code for verification."""
        return "SIGNAL:ACTION:SUBMIT_CODE"

    @staticmethod
    @tool
    async def search_available_tools(query: str) -> str:
        """Searches the 'Extended Toolbelt' for specialized capabilities.

        Use this tool when none of your immediate tools (history, state, memory) 
        satisfy the user's request. It searches the LeetCode MCP server for 
        advanced tools (e.g., contest rankings, detailed problem solutions).

        Args:
            query (str): The functionality you are looking for (e.g., 'contest', 'solutions').

        Returns:
            str: A list of tool names and descriptions matching your query.
        """
        try:
            from app.services.aries.pipeline.tools import get_full_aries_tools
            all_tools = await get_full_aries_tools()
            
            # Filter tools that match the query in name or description
            query_lower = query.lower()
            matches = []
            for t in all_tools:
                # StructuredTool and BaseTool have name/description
                if query_lower in t.name.lower() or query_lower in t.description.lower():
                    matches.append(f"- NAME: {t.name}\n  DESC: {t.description}")
            
            if not matches:
                return f"No specialized tools found for '{query}'. Try a broader search."
            
            return "Found the following specialized tools. You can now call them by name:\n" + "\n".join(matches)
        except Exception as e:
            logger.error(f"TOOL_ERROR (search_available_tools): {e}")
            return f"Error searching tools: {str(e)}"

    @staticmethod
    @tool
    async def trigger_navigation(view: str) -> str:
        """Triggers the UI to navigate to a different view (e.g., 'home', 'problems', 'solve').
        
        Use this when the user wants to switch context or go back.
        """
        return f"SIGNAL:ACTION:NAVIGATE:{view}"


# Core tool list for static binding (sensory/short-term)
aries_core_tools = [
    AriesTools.get_recent_history,
    AriesTools.get_current_state,
    AriesTools.search_memory_palace,
    AriesTools.search_available_tools,
    AriesTools.trigger_load_problem,
    AriesTools.trigger_run_code,
    AriesTools.trigger_submit_code,
    AriesTools.trigger_navigation,
]


_cached_all_tools = None
_loading_task = None


async def preload_aries_tools():
    """Background task to discover and cache tools early."""
    global _cached_all_tools
    try:
        from app.services.aries.pipeline.mcp_tools import get_mcp_tools
        mcp_tools = await get_mcp_tools()
        _cached_all_tools = aries_core_tools + mcp_tools
        logger.info(f"TOOLS: Background discovery complete. {len(_cached_all_tools)} tools cached.")
    except Exception as e:
        logger.error(f"TOOLS: Background discovery failed: {e}")
        _cached_all_tools = aries_core_tools


async def get_extended_aries_tools() -> list[Any]:
    """Retrieves only the dynamically discovered MCP tools."""
    from app.services.aries.pipeline.mcp_tools import get_mcp_tools
    return await get_mcp_tools()


async def get_full_aries_tools() -> list[Any]:
    """Combines core internal tools with dynamically discovered MCP tools.

    This is the primary entry point for the LangGraph agent initialization.

    Returns:
        List[Any]: A complete list of all internal and external (MCP) tools.
    """
    global _cached_all_tools, _loading_task
    
    if _cached_all_tools is not None:
        return list(_cached_all_tools)

    if _loading_task is None:
        _loading_task = asyncio.create_task(preload_aries_tools())
    
    # Wait for the task if it's already running
    await _loading_task
    return list(_cached_all_tools or aries_core_tools)


# Legacy support for synchronous registries
aries_tools_list = aries_core_tools
