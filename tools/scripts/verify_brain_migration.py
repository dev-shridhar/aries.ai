import asyncio
import os
import sys

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.infrastructure.aries.mongo_client import aries_mongo
from app.infrastructure.aries.redis_client import aries_redis
from app.services.aries.pipeline.graph import aries_graph
from app.services.aries.service import aries_service
from langchain_core.messages import HumanMessage


async def test_langchain_flow():
    session_id = "test_langchain_session_unique"
    username = "Shridhar"

    print("Connecting to DBs...")
    await aries_redis.connect()
    await aries_mongo.connect()

    # 1. Clean previous test state
    await aries_redis.client.delete(f"aries:session:{session_id}:code")
    await aries_redis.client.delete(f"aries:session:{session_id}:problem")
    await aries_redis.client.delete(f"aries:history:{session_id}")

    # 2. Pre-seed sensory state
    print("Seeding sensory state...")
    await aries_redis.set_current_code(
        session_id,
        "def fibonacci(n):\n    if n <= 1: return n\n    return fibonacci(n-1) + fibonacci(n-2)",
    )
    await aries_redis.set_current_problem(
        session_id,
        {"title": "Fibonacci Number", "slug": "fibonacci-number", "difficulty": "Easy"},
    )

    print("\n--- PHASE 1: TESTING WELCOME FLOW ---")
    async for response in aries_service.process_welcome_interaction(
        session_id, username
    ):
        if response.text:
            print(f"Aries: {response.text}", end="")
    print("\n")

    print("--- PHASE 2: TESTING ZERO-STUFFING REASONING ---")
    print("User: 'What problem am I looking at and what is the current code?'")

    initial_state = {
        "messages": [
            HumanMessage(
                content="What problem am I looking at and what is the current code?"
            )
        ],
        "session_id": session_id,
        "username": username,
        "system_prompt": "You are Aries, a coding companion. You have ZERO initial context about the user's code or problem. You MUST call your tools (get_current_state, get_recent_history) to see what the user is talking about. Do not guess.",
    }

    print("\nGraph Execution Trace:")
    async for event in aries_graph.astream(
        initial_state, config={"configurable": {"thread_id": session_id}}
    ):
        for node, output in event.items():
            print(f"\n[Node: {node}]")
            if "messages" in output:
                last_msg = output["messages"][-1]
                if last_msg.tool_calls:
                    for tc in last_msg.tool_calls:
                        print(f"  >>> CALLING TOOL: {tc['name']}({tc['args']})")
                elif last_msg.content:
                    print(f"  <<< RESPONSE: {last_msg.content}")

    # 3. Cleanup
    await aries_redis.disconnect()
    await aries_mongo.disconnect()


if __name__ == "__main__":
    asyncio.run(test_langchain_flow())
