import aiosqlite
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "dsa_agent.db"

async def init_db():
    """Initialize the database schema."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY DEFAULT 1,
                username TEXT,
                real_name TEXT,
                avatar TEXT,
                ranking INTEGER,
                last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS recent_submissions (
                id TEXT PRIMARY KEY,
                title TEXT,
                titleSlug TEXT,
                statusDisplay TEXT,
                lang TEXT,
                timestamp TEXT
            )
        """)
        await db.commit()

async def save_user_profile(profile_data):
    """Save user profile to database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO user_profile (id, username, real_name, avatar, ranking, last_sync)
            VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            profile_data.get("username"),
            profile_data.get("realName"),
            profile_data.get("userAvatar"),
            profile_data.get("ranking")
        ))
        await db.commit()

async def get_user_profile():
    """Retrieve user profile from database."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_profile WHERE id = 1") as cursor:
            return await cursor.fetchone()

async def save_recent_submissions(submissions):
    """Save recent submissions to database."""
    async with aiosqlite.connect(DB_PATH) as db:
        for sub in submissions:
            await db.execute("""
                INSERT OR REPLACE INTO recent_submissions (id, title, titleSlug, statusDisplay, lang, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sub.get("id"),
                sub.get("title"),
                sub.get("titleSlug"),
                sub.get("statusDisplay"),
                sub.get("lang"),
                sub.get("timestamp")
            ))
        await db.commit()

async def get_recent_submissions(limit=10):
    """Retrieve recent submissions from database."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM recent_submissions ORDER BY timestamp DESC LIMIT ?", (limit,)) as cursor:
            return await cursor.fetchall()
