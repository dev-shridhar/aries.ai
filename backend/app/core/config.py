"""Global configuration and settings management for the DSA Agent.

This module uses Pydantic Settings to manage environment-based configuration
with strict validation. It centralizes all API keys, infrastructure connection
strings, and model parameters.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings and environment variables.

    Attributes:
        DEEPGRAM_API_KEY (str): API key for Speech-to-Text and Text-to-Speech services.
        GROQ_API_KEY (str): API key for the Groq inference engine.
        REDIS_HOST (str): Hostname for the Redis context cache.
        REDIS_PORT (int): Port for the Redis context cache.
        MONGO_URI (str): Connection URI for the MongoDB episodic memory.
        MONGO_DB (str): Database name for interaction logs.
        PROJECT_NAME (str): The name of the application.
        debug (bool): Flag to enable verbose logging and debugging features.
        BRAIN_PROVIDER (str): The LLM provider (e.g., 'groq').
        BRAIN_MODEL (str): The specific LLM model ID.
        EMBEDDING_MODEL (str): The Ollama-compatible model for vector embeddings.
    """

    # --- API SECURITY ---
    DEEPGRAM_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # --- INFRASTRUCTURE: PERSISTENCE & CACHE ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "dsa_agent"

    # --- CORE APP SETTINGS ---
    PROJECT_NAME: str = "aries.ai"
    debug: bool = True

    # --- AGENTIC CORE (BRAIN) ---
    BRAIN_PROVIDER: str = "groq"
    BRAIN_MODEL: str = "llama-3.3-70b-versatile"
    EMBEDDING_MODEL: str = "nomic-embed-text:latest"

    # --- STT CONFIGURATION ---
    STT_PROVIDER: str = "deepgram"  # Options: "groq" or "deepgram"

    # --- TTS CONFIGURATION ---
    TTS_PROVIDER: str = "deepgram"  # Options: "groq" or "deepgram"

    # Pydantic configuration for environment variable loading
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


# Singleton instance of settings to be used across the application
settings = Settings()
