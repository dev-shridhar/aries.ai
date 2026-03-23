import httpx
import logging

logger = logging.getLogger(__name__)

class SharedHttpClient:
    """A singleton-like wrapper for httpx.AsyncClient to reuse connections."""
    _client: httpx.AsyncClient | None = None

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        """Retrieves or initializes the shared async client."""
        if cls._client is None or cls._client.is_closed:
            logger.info("INFRA: Initializing shared HTTP client pool.")
            cls._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return cls._client

    @classmethod
    async def close(cls):
        """Closes the shared client session."""
        if cls._client and not cls._client.is_closed:
            await cls._client.aclose()
            logger.info("INFRA: Shared HTTP client pool closed.")

shared_http_client = SharedHttpClient()
