import asyncio
import aiosqlite
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
SQLITE_DB = BASE_DIR / "backend" / "dsa_agent.db"
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "dsa_agent"


async def migrate():
    if not SQLITE_DB.exists():
        logger.error(f"SQLite DB not found at {SQLITE_DB}")
        return

    logger.info("Connecting to databases...")
    mongo_client = AsyncIOMotorClient(MONGO_URI)
    mongo_db = mongo_client[DB_NAME]

    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        sqlite_db.row_factory = aiosqlite.Row

        # 1. Migrate User Profile
        logger.info("Migrating user_profile...")
        async with sqlite_db.execute("SELECT * FROM user_profile") as cursor:
            profiles = await cursor.fetchall()
            for p in profiles:
                p_dict = dict(p)
                p_dict.pop("id", None)  # MongoDB uses _id
                await mongo_db.user_profiles.update_one(
                    {"username": p_dict["username"]}, {"$set": p_dict}, upsert=True
                )

        # 2. Migrate Recent Submissions
        logger.info("Migrating recent_submissions...")
        async with sqlite_db.execute("SELECT * FROM recent_submissions") as cursor:
            submissions = await cursor.fetchall()
            for s in submissions:
                s_dict = dict(s)
                # Translate into our new submissions schema if needed
                await mongo_db.submissions.update_one(
                    {
                        "titleSlug": s_dict["titleSlug"],
                        "timestamp": s_dict["timestamp"],
                    },
                    {"$set": s_dict},
                    upsert=True,
                )

        # 3. Migrate Chat History (into Episodic Memory)
        logger.info("Checking for chat history tables...")
        async with sqlite_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_sessions'"
        ) as cursor:
            if await cursor.fetchone():
                logger.info("Migrating chat history...")
                async with sqlite_db.execute(
                    "SELECT * FROM chat_sessions"
                ) as sess_cursor:
                    sessions = await sess_cursor.fetchall()
                    for sess in sessions:
                        session_id = sess["id"]
                        async with sqlite_db.execute(
                            "SELECT role, content, timestamp FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC",
                            (session_id,),
                        ) as msg_cursor:
                            messages = await msg_cursor.fetchall()
                            events = [dict(m) for m in messages]

                            if events:
                                await mongo_db.episodic_memory.update_one(
                                    {"session_id": session_id},
                                    {
                                        "$set": {
                                            "session_id": session_id,
                                            "events": events,
                                            "interaction_type": "text_chat",
                                            "timestamp": sess["created_at"],
                                        }
                                    },
                                    upsert=True,
                                )
            else:
                logger.info("No legacy chat history tables found. Skipping.")

    logger.info("Migration complete!")
    mongo_client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
