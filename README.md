# aries.ai

Voice-based DSA tutor. Talk through LeetCode problems with an AI agent.

**stack**: Python + FastAPI · React + Vite · Redis · Groq · Deepgram

## quick start

```bash
docker run -d --name aries-redis -p 6379:6379 redis

cd backend
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env  # add your keys
uv run uvicorn app.main:app --reload

# in another terminal
cd frontend
npm install && npm run dev
```
