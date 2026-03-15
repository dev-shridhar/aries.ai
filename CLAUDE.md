# Aries DSA Agent - Project Memory & Standards

This file serves as the definitive engineering guide for the `dsa-agent` repository. It defines the architectural patterns, coding standards, and workflows required to maintain premium quality across both backend and frontend.

## 🛠 Tech Stack & Environment
- **Backend**: Python 3.11+, `uv`, FastAPI, LangChain, LangGraph, Groq (Llama 3.3).
- **Frontend**: Vite, React (TypeScript), Vanilla CSS, WebSockets.
- **Persistence**: Redis (Short-term context), MongoDB (Episodic history), ChromaDB (Semantic facts).
- **Linting**: `black` (formatting), `ruff` (linting/imports), `mypy` (strict types).

## 🏛 Project-Wide Architecture (DDD + Vertical Slices)
The codebase follows Domain-Driven Design (DDD) organized into **Vertical Slices**. Each feature is encapsulated within its own slice, containing specific API, Service (Domain), and Infrastructure (Adapter) layers.

### Feature Slices
1.  **Aries Brain (`app/services/aries`)**: The core AI reasoning, perception (STT), and motor output (TTS) logic.
2.  **Compiler Sandbox (`app/services/compiler`)**: Secure code execution, test-case evaluation, and sandbox management.
3.  **User Profile (`app/services/user`)**: User identity management, LeetCode profile synchronization, and preference persistence.
4.  **MCP Integration (`app/services/mcp`)**: Dynamic tool discovery and binding via the Model Context Protocol.

### Directory Design Pattern
- `app/api/<feature>`: FastAPI routers, request/response schemas (Pydantic models).
- `app/services/<feature>`: Core domain business logic and feature orchestrators.
- `app/infrastructure/<feature>`: Data access objects (DAOs), external API clients, and SDK adapters.
- `app/core/`: Cross-cutting concerns (global config, shared base classes, security).
- `tests/<feature>`: Mirror of `app/` structure for isolated unit and integration tests.

## 💎 Premium Standards
1.  **Documentation**:
    *   **Flowcharts**: Every major directory MUST possess a `README.md` with a Mermaid flowchart.
    *   **Docstrings**: All classes and public functions MUST use **Google-style** docstrings.
2.  **Type Safety**: Strict type annotations are mandatory for all Python and TypeScript code.
3.  **Dependency Integrity**: Use `uv` strictly. Never use `pip` or global environments.
4.  **Clean Code**: Focus on SOLID principles. Keep domain services pure; move I/O to infrastructure.

## 🧪 Testing Guidelines
- **Unit Testing**: Target 90%+ coverage for domain logic. Replace/scrap any tests that do not adhere to these standards.
- **Mocking**: Use `unittest.mock.AsyncMock` for all async I/O dependencies.
- **Execution**: `backend/.venv/bin/pytest backend/tests/<feature>`.

## 🚀 Development Workflow
1. **Quality Loop**: Always run the combined quality check before submitting code:
   `uv run ruff check . --fix && uv run isort . && uv run black . && uv run pytest`
2. **Refactor**: Align existing code with these standards before adding new features.
3. **Document**: Update the folder-level `README.md` and flowcharts after any architectural change.
4. **Detailed Guide**: Refer to [dev-workflow.md](file:///Users/shridharkulkarni/personal/learning-mcp/dsa-agent/docs/dev-workflow.md) for a comprehensive breakdown of the Python development process.
