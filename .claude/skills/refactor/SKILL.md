# Skill: Refactoring Voice Pipeline

Instructions for refactoring Aries voice services while maintaining low latency.

## Context
Aries relies on a delicate balance between STT, Brain (LLM), and TTS. Any change to the pipeline must be benchmarked.

## Rules
1. **Always use streaming**: Use `generate_response_stream` for all voice responses.
2. **Sub-second latency**: If a change adds >100ms, it must be justified.
3. **Zero-Stuffing**: Do not add context to the prompt if it can be fetched via a tool.

## Workflow
1. Identify the pipeline node to change.
2. Implement change using LangChain/LangGraph.
3. Run `backend/.venv/bin/python backend/tests/verify_langchain_migration.py`.
4. Check logs for "TOTAL PIPELINE TIME".
