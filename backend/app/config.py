from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEEPGRAM_API_KEY: str
    GROQ_API_KEY: str
    REDIS_URL: str = "redis://localhost:6379"
    BRAIN_MODEL: str = "llama-3.3-70b-versatile"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
