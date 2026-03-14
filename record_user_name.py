import asyncio
import os
import sys

# Ensure we can import from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

# Satisfy settings
os.environ["DEEPGRAM_API_KEY"] = "fake"
os.environ["GROQ_API_KEY"] = "fake"
os.environ["MONGO_URI"] = "mongodb://localhost:27017"
os.environ["REDIS_URL"] = "redis://localhost:6379"

async def record_name():
    from app.services.aries.memory import memory_service
    from app.infrastructure.aries.mongo_client import aries_mongo
    from app.infrastructure.aries.redis_client import aries_redis
    
    print("Connecting to infrastructure...")
    await aries_redis.connect()
    await aries_mongo.connect()
    
    print("Recording fact: real_name = Shridhar")
    await memory_service.record_user_fact(
        username="anonymous", # Default if not logged in
        concept="real_name",
        value="Shridhar"
    )
    
    await aries_redis.disconnect()
    await aries_mongo.disconnect()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(record_name())
