# Aries.ai - AI DSA Tutor

Aries is an advanced AI-powered voice agent designed to help software engineers master Data Structures and Algorithms (DSA) through interactive coding sessions.

## 🦊 Features

- **Expressive Voice Agent**: Dynamic mascot with state-based animations (Listening, Thinking, Speaking).
- **Intelligent Context**: Problem-aware reasoning that understands your current code and the task at hand.
- **Low Latency Interaction**: Optimized pipeline using Llama 3.3 70B for near-instant responses.
- **Memory Palace**: Personalized memory that remembers facts about the user across sessions.

## 🛠️ Tech Stack

- **Frontend**: React, TypeScript, CSS (Vanilla), Vite.
- **Backend**: Python (FastAPI), MongoDB, Redis.
- **AI/ML**: Groq (Llama 3.3 70B), Deepgram (STT), OpenAI/Custom (Embeddings).

---

## 🚀 Getting Started

### 1. Prerequisites
- [uv](https://github.com/astral-sh/uv) (for ultra-fast Python package management)
- [Node.js](https://nodejs.org/) (for the frontend)
- [Docker](https://www.docker.com/) (to run MongoDB and Redis)

### 2. Infrastructure Setup
Spin up the required databases using Docker:
```bash
docker run -d --name aries-mongo -p 27017:27017 mongo
docker run -d --name aries-redis -p 6379:6379 redis
```

### 3. Backend Setup
1. Navigate to the backend directory: `cd backend`
2. Create and activate a virtual environment:
   ```bash
   uv venv
   source .venv/bin/activate  # On macOS/Linux
   ```
3. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   uv pip install black isort  # Dev dependencies
   ```
4. Configure environment:
   Create a `.env` file in `backend/` with:
   ```env
   GROQ_API_KEY=your_key
   DEEPGRAM_API_KEY=your_key
   REDIS_URL=redis://localhost:6379
   MONGODB_URL=mongodb://localhost:27017
   ```
5. Run the server:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

### 4. Frontend Setup
1. Navigate to the frontend directory: `cd frontend`
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```

---

## 🧹 Maintenance Scripts

- **Format Code**: `cd backend && uv run black .`
- **Sort Imports**: `cd backend && uv run isort .`
- **Clean Junk**: `find . -name "*.pyc" -delete`

---

## 📄 Documentation

- **Task Progress**: See `brain/<conversation-id>/task.md` for recent feature work.
- **Mascot Animations**: Controlled via `AudioVisualizer.css` states (`.listening`, `.thinking`, `.speaking`).
