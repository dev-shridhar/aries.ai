import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Keys
    DEEPGRAM_API_KEY: str
    GROQ_API_KEY: str

    # Infrastructure
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "dsa_agent"

    # App Settings
    PROJECT_NAME: str = "aries.ai"
    debug: bool = True

    # Brain Settings
    BRAIN_PROVIDER: str = "groq"
    BRAIN_MODEL: str = "llama-3.3-70b-versatile"
    EMBEDDING_MODEL: str = "nomic-embed-text:latest"

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
