import pytest
from app.chat_store import chat_store


@pytest.mark.asyncio
async def test_add_and_get_history():
    await chat_store.connect()
    await chat_store.add_turn("test-session", "user", "hello")
    await chat_store.add_turn("test-session", "assistant", "hi")
    history = await chat_store.get_history("test-session")
    assert len(history) >= 2
