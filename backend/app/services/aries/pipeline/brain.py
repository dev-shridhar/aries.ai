import os
import httpx
from groq import AsyncGroq
from typing import Optional, List, Dict


class BrainAdapter:
    def __init__(self):
        self.groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.ollama_base_url = "http://localhost:11434/api/chat"

    async def generate_response(
        self,
        text: str,
        system_prompt: str,
        history: Optional[List[Dict]] = None,
        provider: str = "groq",
        model: str = "llama3-8b-8192",
    ) -> str:
        """
        Generates a text response using the specified provider.
        """
        if provider == "groq":
            return await self._groq_inference(text, system_prompt, history, model)
        elif provider == "ollama":
            return await self._ollama_inference(text, system_prompt, history, model)
        else:
            raise ValueError(f"Unknown brain provider: {provider}")

    async def _groq_inference(
        self, text: str, system_prompt: str, history: Optional[List[Dict]], model: str
    ) -> str:
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": text})

            completion = await self.groq_client.chat.completions.create(
                messages=messages,
                model=model,
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Groq Error: {e}")
            return "I'm having trouble thinking through Groq right now."

    async def _ollama_inference(
        self, text: str, system_prompt: str, history: Optional[List[Dict]], model: str
    ) -> str:
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": text})

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.ollama_base_url,
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["message"]["content"]
        except Exception as e:
            print(f"Ollama Error: {e}")
            return "My local brain is currently offline."


brain_adapter = BrainAdapter()
