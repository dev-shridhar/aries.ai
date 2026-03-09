import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat.router import router as chat_router
from app.api.compiler.router import router as compiler_router
from app.api.mcp.router import router as mcp_router, preload_problems
from app.api.voice.router import router as voice_router
from app.core.database.manager import db_manager
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await db_manager.init_db()
    logger.info("Pre-loading problems...")
    await preload_problems()
    yield
    # Shutdown (if needed)


app = FastAPI(title="DSA Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(mcp_router, prefix="/api", tags=["mcp"])
app.include_router(compiler_router, prefix="/api", tags=["compiler"])
app.include_router(voice_router, prefix="/api", tags=["voice"])
