import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.aries.router import router as voice_router
from app.api.compiler.router import router as compiler_router
from app.api.mcp.router import preload_problems
from app.api.mcp.router import router as mcp_router
from app.api.user.router import router as user_router
from app.core.config import settings
from app.infrastructure.aries.mongo_client import aries_mongo
from app.infrastructure.aries.redis_client import aries_redis

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Aries Infrastructure...")
    await aries_redis.connect()
    await aries_mongo.connect()

    logger.info("Pre-loading problems...")
    await preload_problems()
    yield
    # Shutdown
    logger.info("Shutting down Aries Infrastructure...")
    await aries_redis.disconnect()
    await aries_mongo.disconnect()


app = FastAPI(title="DSA Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mcp_router, prefix="/api", tags=["mcp"])
app.include_router(compiler_router, prefix="/api", tags=["compiler"])
app.include_router(voice_router, prefix="/api/aries", tags=["voice"])
app.include_router(user_router, prefix="/api", tags=["user"])
