import json
import logging
from collections.abc import AsyncGenerator

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.core.config import settings

logger = logging.getLogger(__name__)


class BrainAdapter:
    """Adapter for interacting with Large Language Models using LangChain.

    This class serves as the abstraction layer for LLM providers. It primarily
    uses Groq (Llama 3.3) for high-speed agentic reasoning but maintains a local
    fallback to Ollama for privacy-focused or offline tasks.

    Attributes:
        groq_llm (ChatGroq): The primary LangChain-compatible LLM instance.
        ollama_base_url (str): Local endpoint for Ollama inference.
    """

    def __init__(self):
        """Initializes the BrainAdapter with configured provider settings."""
        self.groq_llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model=settings.BRAIN_MODEL,
            temperature=0.1,
        )
        self.ollama_base_url = "http://localhost:11434/api"

    def _convert_history(self, history: list[dict[str, str]]) -> list[BaseMessage]:
        """Converts raw dictionary history to LangChain BaseMessage objects.

        Args:
            history (List[Dict[str, str]]): List of messages with 'role' and 'content'.

        Returns:
            List[BaseMessage]: List of conversation message objects.
        """
        messages = []
        for turn in history:
            role = turn.get("role")
            content = turn.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role in ("assistant", "aries"):
                messages.append(AIMessage(content=content))
            elif role == "system":
                messages.append(SystemMessage(content=content))
        return messages

    async def generate_response(
        self,
        text: str,
        system_prompt: str,
        history: list[dict[str, str]] | None = None,
        provider: str = "groq",
        model: str | None = None,
    ) -> str:
        """Generates a complete text response from the selected LLM provider.

        Args:
            text (str): User's input sequence or query.
            system_prompt (str): Persona or behavioral guidance for the LLM.
            history (Optional[List[Dict[str, str]]]): Previous conversation turns.
            provider (str): Inference provider. Defaults to 'groq'.
            model (Optional[str]): Model name override. Defaults to BRAIN_MODEL.

        Returns:
            str: The generated text response.
        """
        model = model or settings.BRAIN_MODEL
        logger.info(f"BRAIN: Generating single response via {provider}/{model}")

        messages = [SystemMessage(content=system_prompt)]
        if history:
            messages.extend(self._convert_history(history))
        messages.append(HumanMessage(content=text))

        try:
            if provider == "groq":
                response = await self.groq_llm.ainvoke(messages)  # type: ignore
                return response.content  # type: ignore
            else:
                return await self._ollama_inference(text, system_prompt, history, model)
        except Exception as e:
            logger.error(f"BRAIN_ERROR: Groq inference failed: {str(e)}")
            # If it's a 400 error, the message often contains the reason
            return "I'm having trouble thinking clearly. Please try again."

    async def generate_response_stream(
        self,
        text: str,
        system_prompt: str,
        history: list[dict[str, str]] | None = None,
        provider: str = "groq",
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Generates a streaming text response for lower perceived latency.

        Args:
            text (str): User's input sequence or query.
            system_prompt (str): Persona or behavioral guidance for the LLM.
            history (Optional[List[Dict[str, str]]]): Previous conversation turns.
            provider (str): Inference provider. Defaults to 'groq'.
            model (Optional[str]): Model name override. Defaults to BRAIN_MODEL.

        Yields:
            str: Incremental text chunks from the LLM.
        """
        model = model or settings.BRAIN_MODEL

        messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
        if history:
            messages.extend(self._convert_history(history))
        messages.append(HumanMessage(content=text))  # type: ignore

        try:
            if provider == "groq":
                async for chunk in self.groq_llm.astream(messages):  # type: ignore
                    if chunk.content:  # type: ignore
                        yield chunk.content  # type: ignore
            else:
                async for chunk in self._ollama_inference_stream(
                    text, system_prompt, history, model
                ):
                    yield chunk
        except Exception as e:
            logger.error(f"BRAIN_ERROR: Inference failed during streaming: {e}")
            yield "I ran into a bit of a snag while thinking. Let me try again."

    async def get_embedding(
        self, text: str, model: str = "nomic-embed-text:latest"
    ) -> list[float]:
        """Generates high-dimensional vector embeddings via local Ollama.

        Args:
            text (str): Input text to vectorize.
            model (str): Embedding model name. Defaults to 'nomic-embed-text:latest'.

        Returns:
            List[float]: A list of floats representing the text in vector space.
                Returns a zero-vector on failure.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.ollama_base_url}/embeddings",
                    json={"model": model, "prompt": text},
                    timeout=5.0,
                )
                resp.raise_for_status()
                return resp.json()["embedding"]
        except Exception as e:
            logger.warning(
                f"BRAIN_EMBEDDING: Local embedding offline, returning zero-vector: {e}"
            )
            return [0.0] * 768

    async def _ollama_inference(
        self, text: str, system_prompt: str, history: list[dict] | None, model: str
    ) -> str:
        """Performs raw HTTP inference against a local Ollama server."""
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": text})

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.ollama_base_url}/chat",
                json={"model": model, "messages": messages, "stream": False},
                timeout=30.0,
            )
            return resp.json()["message"]["content"]

    async def _ollama_inference_stream(
        self, text: str, system_prompt: str, history: list[dict] | None, model: str
    ) -> AsyncGenerator[str, None]:
        """Performs raw streaming HTTP inference against a local Ollama server."""
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": text})

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.ollama_base_url}/chat",
                json={"model": model, "messages": messages, "stream": True},
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if "message" in data:
                            yield data["message"]["content"]


# Global instance of the BrainAdapter for use across the Aries service.
brain_adapter = BrainAdapter()
