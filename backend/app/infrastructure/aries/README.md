# Aries Infrastructure Layer

The `infrastructure` sub-package provides the foundational data access layers and adapter clients for various persistence and caching technologies.

## Multi-Tier Memory Interplay

Aries uses a tiered storage strategy to balance speed (Sensory), context (Short-term), and longevity (Episodic/Semantic).

```mermaid
graph TD
    A[Aries Service] -->|Hot State| Redis[(Redis)]
    A -->|Turn Logging| Mongo[(MongoDB)]
    A -->|RAG Queries| Chroma[(ChromaDB)]
    
    subgraph Storage Roles
        Redis --- |"Sensory Context (1hr TTL)"| R_Role[Editor Code, History Window]
        Mongo --- |"Episodic Logs (Permanent)"| M_Role[Interaction Clips, Code Activity]
        Chroma --- |"Semantic Facts (Permanent)"| C_Role[User Persona, Problem DNA]
    end
```

## Core Adapters

- **[redis_client.py](file:///Users/shridharkulkarni/personal/learning-mcp/dsa-agent/backend/app/infrastructure/aries/redis_client.py)**: Async client for Redis. Handles state synchronization and rolling conversation history.
- **[mongo_client.py](file:///Users/shridharkulkarni/personal/learning-mcp/dsa-agent/backend/app/infrastructure/aries/mongo_client.py)**: Async client for MongoDB via Motor. Manages interaction episodes and historical code sessions.
- **[chroma_client.py](file:///Users/shridharkulkarni/personal/learning-mcp/dsa-agent/backend/app/infrastructure/aries/chroma_client.py)**: Manager for ChromaDB. Handles vectorization (via Ollama) and semantic similarity search.
