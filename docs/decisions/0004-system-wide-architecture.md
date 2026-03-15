# ADR 0004: System-Wide Architecture (Sensory-Reasoning-Action)

## Context
Aries is a complex agentic system in a multi-directory repo. We need a unified architecture that explains how the `frontend` and `backend` interact as a single unit.

## Decision: S-R-A Loop
We are adopting the **Sensory-Reasoning-Action (SRA)** loop as the mental model for the whole repo.

### 1. Sensory Layer (`/frontend`)
- **Tech**: React + Vite + WebSocket.
- **Responsibility**: Observes the user. Captures voice (Mic), code changes (Editor), and problem metadata (Dom/API).
- **Standards**: Functional components, Hooks for state, styled with Vanilla CSS (Premium Aesthetics).

### 2. Reasoning Layer (`/backend`)
- **Tech**: FastAPI + LangChain + LangGraph.
- **Responsibility**: The "Aries Brain". Processes sensory input, decides intent, and plans actions.
- **Standards**: DDD, Vertical Slices, Pydantic v2.

### 3. Action Layer (`/tools` & `/backend`)
- **Tech**: MCP (Model Context Protocol).
- **Responsibility**: Executes the plan. Interacts with the filesystem, LeetCode, or terminal.
- **Standards**: Model-agnostic tools defined as `StructuredTool`s.

## Consequences
- Every feature should have a representation in both S, R, and A layers.
- Cross-layer communication should be standardized via the Aries WebSocket protocol.
