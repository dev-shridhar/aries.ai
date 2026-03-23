import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.infrastructure.aries.mongo_client import aries_mongo
from app.infrastructure.aries.redis_client import aries_redis
from app.services.aries.service import aries_service

async def run_exact_binary_search_demo():
    session_id = "demo_binary_search_unique"
    username = "User"

    print("Connecting to Services...")
    await aries_redis.connect()
    await aries_mongo.connect()

    # Clean state
    await aries_redis.client.delete(f"aries:session:{session_id}:code")
    await aries_redis.client.delete(f"aries:session:{session_id}:problem")
    await aries_redis.client.delete(f"aries:history:{session_id}")

    print("\n" + "="*50)
    print("LIVE E2E DEMO: BINARY SEARCH FLOW")
    print("="*50)

    # 1. WELCOME MESSAGE
    print("\n[STEP 1: WELCOME]")
    async for resp in aries_service.process_welcome_interaction(session_id, username):
        if resp.text:
            print(f"Agent: {resp.text}")

    # 2. USER RESPONDS: "binary search"
    print("\n[STEP 2: USER REVEALS WEAKNESS]")
    user_input_1 = "Hey Aries, i am week at binary search"
    print(f"{username}: {user_input_1}")
    
    async for resp in aries_service.process_text_interaction(
        text_input=user_input_1,
        session_id=session_id,
        username=username
    ):
        if resp.text:
            print(f"Agent: {resp.text}")
        if resp.action:
            print(f"  >>> UI ACTION: {resp.action} ({resp.action_payload})")

    # 3. USER SELECTS PROBLEM
    print("\n[STEP 3: USER SELECTS PROBLEM]")
    # We will look at step 2's output to find a problem slug to select
    # For the script, we'll try to select "binary-search" as a standard follow-up
    user_input_2 = "I want to solve the basic Binary Search problem. Can you load it for me?"
    print(f"{username}: {user_input_2}")

    async for resp in aries_service.process_text_interaction(
        text_input=user_input_2,
        session_id=session_id,
        username=username
    ):
        if resp.text:
            print(f"Agent: {resp.text}")
        if resp.action:
            print(f"  >>> UI ACTION: {resp.action} (Slug: {resp.action_payload.get('slug')})")

    # 4. TOOL DISCOVERY
    print("\n[STEP 4: DISCOVERY TEST]")
    user_input_3 = "Can you find my contest rankings? I want to see how I'm doing."
    print(f"{username}: {user_input_3}")

    async for resp in aries_service.process_text_interaction(
        text_input=user_input_3,
        session_id=session_id,
        username=username
    ):
        if resp.text:
            print(f"Agent: {resp.text}")
        if resp.action:
             print(f"  >>> UI ACTION: {resp.action}")

    print("\n" + "="*50)
    print("LIVE DEMO COMPLETE")
    print("="*50)

    await aries_redis.disconnect()
    await aries_mongo.disconnect()

if __name__ == "__main__":
    asyncio.run(run_exact_binary_search_demo())
