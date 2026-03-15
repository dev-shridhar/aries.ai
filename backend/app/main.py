"""Main entry point for the DSA Agent FastAPI application.

This module orchestrates the initialization of the web server, middleware
configuration, and the mounting of feature-slice routers. It also manages
the lifecycle of core infrastructure components (Redis, MongoDB) through
the FastAPI lifespan context manager.
"""

import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.api.aries.router import router as voice_router
from app.api.compiler.router import router as compiler_router
from app.api.mcp.router import preload_problems
from app.api.mcp.router import router as mcp_router
from app.api.user.router import router as user_router
from app.core.config import settings
from app.infrastructure.aries.mongo_client import aries_mongo
from app.infrastructure.aries.redis_client import aries_redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure global logging with premium formatting
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages the startup and shutdown lifecycle of the application.

    This context manager ensures that database connections are pooled
    efficiently and that any warm-up tasks (like pre-loading problems)
    are completed before the server starts accepting traffic.

    Args:
        app (FastAPI): The application instance.
    """
    # --- STARTUP PHASE ---
    logger.info("MAIN: Initializing Aries Core Infrastructure...")
    try:
        await aries_redis.connect()
        await aries_mongo.connect()
        logger.info("MAIN: Successfully connected to persistence layers.")
    except Exception as e:
        logger.error(f"MAIN: Failed to initialize infrastructure: {e}")

    logger.info("MAIN: Pre-loading problem metadata into memory...")
    await preload_problems()

    yield

    # --- SHUTDOWN PHASE ---
    logger.info("MAIN: Gracefully shutting down infrastructure...")
    await aries_redis.disconnect()
    await aries_mongo.disconnect()
    logger.info("MAIN: Terminated all infrastructure sessions.")


# Initialize the primary FastAPI application
app = FastAPI(
    title="Aries DSA Agent API",
    description="Multi-modal AI agent for Data Structures and Algorithms tutoring.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Vertical Slice Routers
# Each router represents a distinct domain feature set
app.include_router(mcp_router, prefix="/api", tags=["MCP Tools"])
app.include_router(compiler_router, prefix="/api", tags=["Code Execution"])
app.include_router(voice_router, prefix="/api/aries", tags=["Aries Brain"])
app.include_router(user_router, prefix="/api", tags=["User Profiles"])
