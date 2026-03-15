# Aries: Premium Voice-Enabled DSA Agent

Aries is a state-of-the-art AI agent designed to assist users with Data Structures and Algorithms (DSA) through a multi-modal, voice-first interface. It leverages a modern agentic stack to provide contextual, proactive, and memory-aware tutoring.

## Architecture Overview

Aries follows a **Sensory-Motor Pipeline** architecture, orchestrated by **LangGraph** for robust reasoning and tool-driven interaction.

### Cognitive Tiers
1.  **Sensory / Perception**: Deepgram STT (Speech-to-Text) transcribes user intent. UI state (code, problem metadata) is synced via Redis.
2.  **Reasoning / Think**: LangGraph coordinates the high-level logic, routing between LLM reasoning ('agent') and tool executions ('tools').
3.  **Memory / Cognition**:
    *   **Hot (Redis)**: Short-term context, rolling conversation window.
    *   **Semantic (ChromaDB)**: RAG-based memory for facts, logic summaries, and user personality.
    *   **Episodic (MongoDB)**: Long-term interaction logs and historical code activity.
4.  **Motor / Output**: Deepgram TTS (Text-to-Speech) converts AI reasoning into natural voice response.

## System Flow

```mermaid
graph TD
    User((User)) -->|Voice/Audio| STT[STT Adapter]
    STT -->|Transcript| Service[Aries Service]
    
    subgraph Reasoning Loop (LangGraph)
        Service --> Agent[Agent Node]
        Agent -->|Tool Calls| Tools[Tool Executor]
        Tools -->|Results| Agent
        Agent -->|Final Response| Service
    end
    
    subgraph Memory Stack
        Service <--> Redis[(Redis: Sensory State)]
        Service <--> Chroma[(ChromaDB: Semantic Memory)]
        Service <--> Mongo[(MongoDB: Episodic Logs)]
    end
    
    Service -->|Text| TTS[TTS Adapter]
    TTS -->|Voice| User
```

## Core Components

- **[AriesService](file:///Users/shridharkulkarni/personal/learning-mcp/dsa-agent/backend/app/services/aries/service.py)**: The main orchestrator of the end-to-end pipeline.
- **[MemoryService](file:///Users/shridharkulkarni/personal/learning-mcp/dsa-agent/backend/app/services/aries/memory.py)**: Coordinator for the multi-tier memory stack.
- **[AriesGraph](file:///Users/shridharkulkarni/personal/learning-mcp/dsa-agent/backend/app/services/aries/pipeline/graph.py)**: The LangGraph definition for reasoning and routing.
- **[BrainAdapter](file:///Users/shridharkulkarni/personal/learning-mcp/dsa-agent/backend/app/services/aries/pipeline/brain.py)**: abstractions for LLM interaction (Groq/Ollama).
- **[MCPToolFactory](file:///Users/shridharkulkarni/personal/learning-mcp/dsa-agent/backend/app/services/aries/pipeline/mcp_tools.py)**: Dynamic tool discovery via Model Context Protocol.

## Engineering Standards

- **Google-Style Docstrings**: All public methods and classes are documented for clarity.
- **Type Safety**: Strict Python type annotations across all layers.
- **Vertical Slicing**: Clear separation of concerns within the `aries` domain.
- **High Performance**: Optimized Redis caching and async MongoDB interactions.
