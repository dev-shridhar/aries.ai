import aiosqlite
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "dsa_agent.db"


class DatabaseManager:
    """
    Class-based interface for database operations.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Initialize the database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    username TEXT,
                    real_name TEXT,
                    avatar TEXT,
                    ranking INTEGER,
                    last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS recent_submissions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    titleSlug TEXT,
                    statusDisplay TEXT,
                    lang TEXT,
                    timestamp TEXT
                )
            """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions (id)
                )
            """
            )
            await db.commit()

    async def save_user_profile(self, profile_data: dict):
        """Save user profile to database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO user_profile (id, username, real_name, avatar, ranking, last_sync)
                VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    profile_data.get("username"),
                    profile_data.get("realName"),
                    profile_data.get("userAvatar"),
                    profile_data.get("ranking"),
                ),
            )
            await db.commit()

    async def get_user_profile(self) -> dict | None:
        """Retrieve user profile from database."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM user_profile WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def save_recent_submissions(self, submissions: list[dict]):
        """Save recent submissions to database."""
        async with aiosqlite.connect(self.db_path) as db:
            for sub in submissions:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO recent_submissions (id, title, titleSlug, statusDisplay, lang, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        sub.get("id"),
                        sub.get("title"),
                        sub.get("titleSlug"),
                        sub.get("statusDisplay"),
                        sub.get("lang"),
                        sub.get("timestamp"),
                    ),
                )
            await db.commit()

    async def get_or_create_session(self, session_id: str) -> str:
        """Fetch a session or create it if it doesn't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id FROM chat_sessions WHERE id = ?", (session_id,)
            ) as cursor:
                if not await cursor.fetchone():
                    await db.execute(
                        "INSERT INTO chat_sessions (id) VALUES (?)", (session_id,)
                    )
                    await db.commit()
        return session_id

    async def save_message(self, session_id: str, role: str, content: str):
        """Save a chat message to the database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO chat_messages (session_id, role, content)
                VALUES (?, ?, ?)
            """,
                (session_id, role, content),
            )
            await db.execute(
                """
                UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """,
                (session_id,),
            )
            await db.commit()

    async def get_chat_history(self, session_id: str, limit: int = 20) -> list[dict]:
        """Retrieve recent chat history for a session."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT role, content FROM chat_messages 
                WHERE session_id = ? 
                ORDER BY timestamp ASC LIMIT ?
            """,
                (session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]


# Singleton instance for simple dependency injection
db_manager = DatabaseManager()
