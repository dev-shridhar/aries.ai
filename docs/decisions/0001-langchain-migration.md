This plan outlines the re-architecture of the Aries reasoning engine using LangChain and LangGraph. It adheres to the project's core standards (DDD, Vertical Slices, and uv/.venv) as documented in `CLAUDE.md`.

## Proposed Changes

### 0. Project Architecture & Standards
- **Standards**: All new code must follow **DDD** (Domain-Driven Design) and **Vertical Slice** patterns.
- **Environment**: Environment management is strictly handled via **uv** and local **.venv**.
- **Context**: Rely on `CLAUDE.md` at the workspace root for persistent project memory.

### 1. Core Reasoning (On-Demand Retrieval)
- **Adapter**: Replace the "Big Prompt" pattern with a **Tool-Based Retrieval** pattern.
- **Pattern**: Aries starts with a minimal persona prompt. If it needs user facts, code context, or problem details, it explicitly calls a `search_memory` tool.
- **Model**: `ChatGroq` (Llama 3.3 70B) handles tool-calling logic.

### 2. Standardized Memory (Multi-Tier)
- **Active Session (Redis)**: 
  - Continue using **Redis** for the "Sensory" and "Short-term" memory.
  - **Zero-Stuffing Policy**: Conversation history is NOT automatically added to the LLM prompt.
  - **Access via Tool**: Aries is given a `get_recent_history` tool to fetch any number of previous turns from Redis when context is needed.
- **Memory Palace (ChromaDB)**:
  - Role: **Semantic Memory** (Vector Search).
  - Use ChromaDB to store user facts and problem embeddings.
  - **Replaces**: The vector-search functionality currently in MongoDB for faster local RAG.
- **Episodic Logger (MongoDB)**:
  - Role: Long-term archival of full conversation "episodes" (non-vectorized).

### 3. Agentic Flow (LangGraph)
- **State**: `AgentState` manages the active context window.
- **Nodes**:
  - `think`: Initial reasoning and tool selection.
  - `retrieve`: Specialized tool node for ChromaDB/Redis/Mongo queries.
  - `execute`: Direct MCP connection for LeetCode actions.
- **Routing**: LLM decides if it has enough info. If not, it loops to `retrieve` before finalizing speech.

### 4. Direct MCP Tool Integration
- **Dynamic Discovery**: Aries will connect directly to the LeetCode MCP server during the `think` phase.
- **Native Execution**: Use LangChain's native support for MCP tools to avoid manual boilerplate functions.
- **Observability**: Every MCP call and result will be tracked as a state transition in LangGraph.

## Verification Plan

### Automated Tests
- `pytest backend/tests/langchain`: Direct testing of the new chains and graphs.
- Latency benchmarks comparing existing `BrainAdapter` vs. new `LangChainAdapter`.

### Manual Verification
- Verify voice loop stability in the `langchain-brain` branch UI.
- Confirm "Memory Palace" retrieval works correctly under the new abstraction.
