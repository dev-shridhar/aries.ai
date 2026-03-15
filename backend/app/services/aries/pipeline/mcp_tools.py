import logging
from typing import Any, Optional

from app.infrastructure.mcp.client import mcp_infra
from langchain_core.tools import StructuredTool
from pydantic import Field, create_model

logger = logging.getLogger(__name__)


class MCPToolFactory:
    """Factory to convert MCP tools into LangChain StructuredTool objects.

    This class serves as the bridge between the Model Context Protocol (MCP) tool
    definitions and the LangChain ecosystem. It ensures that only authorized
    public tools are integrated into the Aries reasoning loop.

    Attributes:
        PUBLIC_TOOLS (set): A whitelist of LeetCode MCP tools that do not
            require a session cookie and are safe for public use.
    """

    PUBLIC_TOOLS = {
        "get_daily_challenge",
        "get_problem",
        "search_problems",
        "list_problem_solutions",
        "get_problem_solution",
        "get_user_profile",
        "get_user_contest_ranking",
    }

    @classmethod
    async def get_tools(cls) -> list[StructuredTool]:
        """Dynamically discovers and wraps authorized MCP tools.

        This method connects to the local MCP infrastructure, retrieves available
        tool metadata, filters against the public whitelist, and dynamically
        generates LangChain StructuredTool objects with validated Pydantic schemas.

        Returns:
            List[StructuredTool]: A list of LangChain-compatible tool objects.
        """
        try:
            async with mcp_infra.get_session() as (session, tools_metadata):
                mcp_tools = []

                for metadata in tools_metadata:
                    func_name = metadata["function"]["name"]

                    # Security Filter: Only expose tools from the public whitelist
                    if func_name not in cls.PUBLIC_TOOLS:
                        continue

                    def create_tool_fn(name: str):
                        """Creates a closure to preserve tool name during async execution."""

                        async def tool_fn(**kwargs) -> str:
                            """Internal execution wrapper for the MCP tool call."""
                            # We use a one-off session pattern for public tools to ensure
                            # they are stateless and don't leak context between users.
                            async with mcp_infra.get_session() as (conn, _):
                                return await mcp_infra.call_tool(conn, name, kwargs)

                        return tool_fn

                    # PHASE 3: Dynamic Schema Generation
                    # We map MCP JSON-schema types to Python types using pydantic.create_model.
                    # This allows LangChain's StructuredTool to correctly validate and
                    # pass arguments from the LLM during the agentic reasoning loop.
                    params = metadata["function"].get(
                        "parameters", {"type": "object", "properties": {}}
                    )
                    properties = params.get("properties", {})
                    required = params.get("required", [])

                    type_map = {
                        "string": str,
                        "integer": int,
                        "number": float,
                        "boolean": bool,
                        "array": list,
                        "object": dict,
                    }

                    fields = {}
                    for prop_name, prop_data in properties.items():
                        python_type = type_map.get(prop_data.get("type", "string"), Any)
                        description = prop_data.get("description", "")

                        if prop_name in required:
                            fields[prop_name] = (
                                python_type,
                                Field(description=description),
                            )
                        else:
                            fields[prop_name] = (
                                Optional[python_type],
                                Field(default=None, description=description),
                            )

                    # Create the dynamic Pydantic model for argument validation
                    ArgsSchema = create_model(f"{func_name}_schema", **fields)

                    tool = StructuredTool.from_function(
                        coroutine=create_tool_fn(func_name),
                        name=func_name,
                        description=metadata["function"].get("description", ""),
                        args_schema=ArgsSchema,
                    )

                    mcp_tools.append(tool)

                return mcp_tools

        except Exception as e:
            logger.error(f"MCP_FACTORY: Failed to dynamically load tools: {e}")
            return []


async def get_mcp_tools() -> list[StructuredTool]:
    """Helper function to retrieve all public MCP tools for the Aries Brain.

    Returns:
        List[StructuredTool]: List of discovered and authorized tools.
    """
    return await MCPToolFactory.get_tools()
