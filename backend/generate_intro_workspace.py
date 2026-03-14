import asyncio
import base64
from app.services.aries.pipeline.tts import tts_adapter

async def generate_hardcoded_intro():
    text = "I am Aries, your coding companion. I can help you solve LeetCode problems, explain algorithms, and search for challenges. How can I help you today?"
    print(f"Generating audio for: {text}")
    audio_bytes = await tts_adapter.speak(text)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    
    with open("intro_audio_b64.txt", "w") as f:
        f.write(audio_b64)
    print("Base64 audio written to backend/intro_audio_b64.txt")

if __name__ == "__main__":
    asyncio.run(generate_hardcoded_intro())
