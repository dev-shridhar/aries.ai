import asyncio
import os
import sys

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from langchain_core.messages import HumanMessage

from app.infrastructure.aries.mongo_client import aries_mongo
from app.infrastructure.aries.redis_client import aries_redis
from app.services.aries.pipeline.graph import aries_graph
from app.services.aries.service import aries_service


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

    print("\n--- PHASE 1: WELCOME ---")
    async for response in aries_service.process_welcome_interaction(
        session_id, username
    ):
        if response.text:
            print(f"Aries: {response.text}")
    print("\n")

    print("--- PHASE 2: DISCOVERY (User is weak at Binary Search) ---")
    print("User: 'Hey Aries, I am weak at binary search.'")

    # We use process_text_interaction to see the full service logic
    async for response in aries_service.process_text_interaction(
        text_input="Hey Aries, I am weak at binary search.",
        session_id=session_id,
        username=username
    ):
        if response.text:
            print(f"Aries: {response.text}")
        if response.action:
            print(f"  >>> SIGNAL TO UI: {response.action} ({response.action_payload})")

    print("\n--- PHASE 3: ACTION (User selects a problem) ---")
    print("User: 'Load the standard Binary Search problem for me.'")

    async for response in aries_service.process_text_interaction(
        text_input="Load the standard Binary Search problem for me.",
        session_id=session_id,
        username=username
    ):
        if response.text:
            print(f"Aries: {response.text}")
        if response.action:
            print(f"  >>> SIGNAL TO UI: {response.action} ({response.action_payload})")

    # 3. Cleanup
    await aries_redis.disconnect()
    await aries_mongo.disconnect()


if __name__ == "__main__":
    asyncio.run(test_langchain_flow())
