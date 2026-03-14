import logging
from typing import Dict, List, Optional

import httpx
from groq import AsyncGroq

from app.core.config import settings

logger = logging.getLogger(__name__)


class BrainAdapter:
    def __init__(self):
        self.groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.ollama_base_url = "http://localhost:11434/api/chat"

    async def generate_response(
        self,
        text: str,
        system_prompt: str,
        history: Optional[List[Dict]] = None,
        provider: str = "groq",
        model: str = "llama-3.1-8b-instant",
    ) -> str:
        """
        Generates a text response using the specified provider.
        """
        logger.info(f"BRAIN: Active Provider={provider}, Model={model}")
        if provider == "groq":
            return await self._groq_inference(text, system_prompt, history, model)
        elif provider == "ollama":
            return await self._ollama_inference(text, system_prompt, history, model)
        else:
            raise ValueError(f"Unknown brain provider: {provider}")

    async def generate_response_stream(
        self,
        text: str,
        system_prompt: str,
        history: Optional[List[Dict]] = None,
        provider: str = "groq",
        model: str = "llama-3.1-8b-instant",
    ):
        """
        Generates a streaming text response using the specified provider.
        """
        if provider == "groq":
            async for chunk in self._groq_inference_stream(
                text, system_prompt, history, model
            ):
                yield chunk
        elif provider == "ollama":
            async for chunk in self._ollama_inference_stream(
                text, system_prompt, history, model
            ):
                yield chunk
        else:
            raise ValueError(f"Unknown brain provider: {provider}")

    async def _groq_inference_stream(
        self, text: str, system_prompt: str, history: Optional[List[Dict]], model: str
    ):
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": text})

            logger.info(f"GROQ: Starting stream for model {model}...")
            stream = await self.groq_client.chat.completions.create(
                messages=messages,
                model=model,
                stream=True,
            )
            logger.info("GROQ: Stream created successfully. Waiting for chunks...")
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    logger.debug(f"GROQ Chunk: '{content}'")
                    yield content
            logger.info("GROQ: Stream completed.")
        except Exception as e:
            logger.error(f"Groq Streaming Inference Failed: {str(e)}")
            yield "I'm having trouble streaming through Groq."

    async def _ollama_inference_stream(
        self,
        text: str,
        system_prompt: str,
        history: Optional[List[Dict]],
        model: str = "qwen3.5:9b",
    ):
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": text})

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "http://localhost:11434/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": True,
                    },
                    timeout=60.0,
                ) as response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                        if data.get("done"):
                            break
        except Exception as e:
            logger.error(f"Ollama Streaming Error: {e}")
            yield "My local streaming brain is offline."

    async def _groq_inference(
        self, text: str, system_prompt: str, history: Optional[List[Dict]], model: str
    ) -> str:
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": text})

            logger.info(
                f"GROQ: Requesting completion for model {model} (timeout=15s)..."
            )
            # Log first message content (system prompt) for health check but truncated
            logger.debug(f"GROQ: System Prompt (truncated): {system_prompt[:200]}...")

            completion = await self.groq_client.chat.completions.create(
                messages=messages,
                model=model,
                timeout=15.0,
            )
            content = completion.choices[0].message.content
            logger.info(f"GROQ: Received response ({len(content)} chars).")
            return content
        except Exception as e:
            logger.error(f"GROQ: Inference Failed: {str(e)}")
            # Log the full messages list only on error to avoid log bloat
            logger.error(f"GROQ: Failed Messages Payload: {messages}")
            return "I'm having trouble thinking through Groq right now."

    async def get_embedding(
        self, text: str, model: str = "nomic-embed-text:latest"
    ) -> List[float]:
        """
        Generates a vector embedding using local Ollama.
        Falls back to a zero-vector on failure to prevent pipeline snags.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://localhost:11434/api/embeddings",
                    json={"model": model, "prompt": text},
                    timeout=1.0,  # Shorter timeout for faster fallback
                )
                resp.raise_for_status()
                data = resp.json()
                return data["embedding"]
        except Exception as e:
            logger.warning(
                f"Ollama Embedding Offline (using zero-vector fallback): {e}"
            )
            # Return a standard Nomic-sized zero vector to keep the DB logic happy
            return [0.0] * 768

    async def _ollama_inference(
        self,
        text: str,
        system_prompt: str,
        history: Optional[List[Dict]],
        model: str = "qwen3.5:9b",
    ) -> str:
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": text})

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                    },
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama Error: {e}")
            return "My local brain is currently offline."


brain_adapter = BrainAdapter()
