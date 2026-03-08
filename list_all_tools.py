
import asyncio
import json
import os
from mcp_leetcode_client import leetcode_mcp_session

async def main():
    async with leetcode_mcp_session() as (session, _):
        tools = await session.list_tools()
        print(json.dumps([t.name for t in tools.tools], indent=2))

if __name__ == "__main__":
    asyncio.run(main())
