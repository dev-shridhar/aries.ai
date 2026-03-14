import asyncio
import os
import sys
import base64

# Keep backend in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

async def generate_assets():
    from app.services.aries.pipeline.tts import tts_adapter
    
    phrases = [
        "Hey Shridhar, I'm ears. How can I help you conquer today's challenge?",
        "Aries ready. What are we optimizing today, Shridhar?",
        "Greetings Shridhar! Ready to dive into some algorithms?"
    ]
    
    print("export interface Greeting { text: string; audio: string; }")
    print("export const HARDCODED_GREETINGS: Greeting[] = [")
    for phrase in phrases:
        audio_bytes = await tts_adapter.speak(phrase)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        print(f"  {{ text: {repr(phrase)}, audio: {repr(audio_b64)} }},")
    print("];")

if __name__ == "__main__":
    asyncio.run(generate_assets())
