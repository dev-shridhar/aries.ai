import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "backend")))

async def test_tts():
    from app.services.aries.pipeline.tts import tts_adapter
    print("Requesting TTS...")
    audio = await tts_adapter.speak("Hello Shridhar")
    print(f"Success! Audio length: {len(audio)} bytes")
    # Write to a file to verify it's a real MP3
    with open("test_audio.mp3", "wb") as f:
        f.write(audio)
    print("Saved to test_audio.mp3")

if __name__ == "__main__":
    asyncio.run(test_tts())
