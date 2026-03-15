# Aries Backend - Reasoning Layer

The core intelligence behind the DSA Agent.

## Aries Brain Pipeline

```mermaid
sequenceDiagram
    participant UI as Frontend Sensory
    participant SA as STT Adapter
    participant BA as Brain Adapter (LangGraph)
    participant RP as Redis (Sensory/History)
    participant MC as MCP Tools
    participant TA as TTS Adapter

    UI->>SA: Audio Bytes
    SA->>BA: Transcript
    BA->>RP: Query History (Tool)
    RP-->>BA: Recent Turns
    BA->>RP: Query Editor State (Tool)
    RP-->>BA: Code/Problem Metadata
    BA->>MC: Execute Action (Tool)
    MC-->>BA: Execution Results
    BA->>TA: Response Text
    TA-->>UI: Audio Stream
```

## Standards
- **Formatter**: `black`
- **Import Sort**: `ruff`
- **Docstrings**: Google Style
- **Package Manager**: `uv`

## Core Modules
- `app/services/aries/pipeline`: The LangChain/LangGraph implementation.
- `app/infrastructure`: Database clients (Redis, Mongo, Chroma).
- `app/domain`: Core domain models and logic.
