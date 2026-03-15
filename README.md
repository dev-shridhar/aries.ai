# DSA Agent - Root

Modern AI Coding Assistant for DSA Problems.

## System-Wide Flow (SRA Loop)

```mermaid
graph TD
    subgraph Frontend [Sensory Layer - /frontend]
        A[User Voice/Mic] --> B[WebSocket Stream]
        C[Editor Changes] --> D[Redis Sensory Sync]
        E[Problem Context] --> D
    end

    subgraph Backend [Reasoning Layer - /backend]
        B --> F[Brain Adapter - LangChain]
        D --> G[Aries Tools]
        F -->|Think| H[LangGraph State Machine]
        H -->|Tool Call| G
    end

    subgraph Actions [Action Layer - /tools]
        G --> I[MCP Server - LeetCode]
        I --> J[File/Code Execution]
        J --> K[Terminal Output]
    end

    K -->|Log| L[Episodic Memory - MongoDB]
    H -->|Speech| M[TTS Generation]
    M -->|Audio| A
```

## Directory Structure
- `backend/`: FastAPI reasoning engine and memory adapters.
- `frontend/`: React sensory UI and voice capture.
- `tools/`: Automation scripts and prompt templates.
- `docs/`: ADRs, runbooks, and architecture specs.
- `.claude/`: Institutional memory and agent skills.

## Project Standards
Refer to [CLAUDE.md](file:///Users/shridharkulkarni/personal/learning-mcp/dsa-agent/CLAUDE.md) for detailed coding, styling, and documentation standards.
