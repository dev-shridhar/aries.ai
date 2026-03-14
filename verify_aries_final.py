import asyncio
import base64
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure we can import from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

# Mock all dependencies before importing app modules
os.environ["DEEPGRAM_API_KEY"] = "fake_key"
os.environ["GROQ_API_KEY"] = "fake_key"
os.environ["MONGO_URI"] = "mongodb://localhost:27017" # satisfy settings
os.environ["REDIS_URL"] = "redis://localhost:6379"    # satisfy settings
os.environ["BRAIN_PROVIDER"] = "groq"
os.environ["BRAIN_MODEL"] = "llama3-70b-8192"

async def test_aries_logic():
    print("🚀 Starting Aries Pipeline Verification (using .venv)...")
    
    # Define Mocks FIRST
    mock_stt = AsyncMock()
    mock_brain = AsyncMock()
    mock_tts = AsyncMock()
    mock_memory = AsyncMock()

    mock_brain_response = "Hi! I'm Aries. I can help you with DSA problems like Merge Sort or Dynamic Programming. What should I call you?"
    
    # We patch the adapters and memory service in their source locations
    with patch("app.services.aries.pipeline.stt.stt_adapter", mock_stt), \
         patch("app.services.aries.pipeline.brain.brain_adapter", mock_brain), \
         patch("app.services.aries.pipeline.tts.tts_adapter", mock_tts), \
         patch("app.services.aries.memory.memory_service", mock_memory):
        
        # Setup Mocks
        mock_stt.transcribe = AsyncMock(return_value="Hey Aries")
        mock_brain.generate_response = AsyncMock(return_value=mock_brain_response)
        mock_tts.speak = AsyncMock(return_value=b"mocked_audio_bytes")
        
        mock_memory.get_full_context = AsyncMock(return_value={
            "history": [],
            "current_code": "",
            "current_problem": None,
            "user_facts": [],
            "semantic_knowledge": [],
            "code_results": [],
            "episodes": []
        })
        
        # 2. Initialize Service
        # We import here so it takes the patches and environment variables
        from app.services.aries.service import AriesService
        service = AriesService()
        
        # 3. Simulate Voice Interaction (Discrete Blob)
        print("Feeding audio blob to AriesService...")
        fake_audio = b"fake_wav_header_and_data"
        response = await service.process_voice_interaction(
            audio_bytes=fake_audio,
            session_id="test-session",
            username="test-user"
        )
        
        # 4. Verify Flow
        print(f"Transcript Detected: 'Hey Aries' (Mocked)")
        print(f"Aries Text Response: '{response.text}'")
        
        if not response.text:
             print("ERROR: response.text is empty!")
             # Maybe check why
        
        assert "Aries" in response.text
        assert "call you" in response.text.lower()
        assert response.audio_chunk is not None
        
        audio_content = base64.b64decode(response.audio_chunk)
        assert audio_content == b"mocked_audio_bytes"
        
        # 5. Verify Memory Interaction
        mock_memory.record_interaction.assert_called_once()
        print("✅ Memory record interaction called.")
        
        print("\n✨ Aries Voice Pipeline logic is SOUND!")

if __name__ == "__main__":
    asyncio.run(test_aries_logic())
