# Skill: Testing DDD

Instructions for implementing the 3-tier testing strategy.

## 1. Unit Testing (Domain/Logic)
- **Goal**: Test individual functions and classes in isolation.
- **Rule**: Never touch the network or database. Mock everything else.
- **Location**: `tests/<slice>/unit/`
- **Tool**: `pytest` + `pytest-mock`.

## 2. Integration Testing (Adapters)
- **Goal**: Test the connection between our code and external APIs/DBs.
- **Rule**: Test the `Adapter` classes (e.g., `STTAdapter`, `MemoryService`).
- **Location**: `tests/<slice>/integration/`

## 3. System Testing (E2E)
- **Goal**: Test the full Sensory-Reasoning-Action loop.
- **Rule**: Run the complete vertical slice logic.
- **Location**: `tests/verify_<feature>.py`
