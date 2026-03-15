# Aries Architecture Overview

Aries is a voice-powered coding assistant designed to help developers solve DSA problems on LeetCode.

## Core Hierarchy
- **Brain**: LangChain + LangGraph orchestrator (Groq/Llama 3.3).
- **Sensory**: Real-time code and problem state from the UI via Redis.
- **Episodic Memory**: MongoDB storage for session logs and archived interactions.
- **Semantic Memory**: ChromaDB vector store for RAG (Retrieval Augmented Generation).

## Communication Flow
1. **Voice Input**: WebSocket -> Deepgram (STT).
2. **Reasoning**: Aries Brain (LangGraph) decides if tools are needed.
3. **Action**: Executes Python code or queries Memory Palace.
4. **Voice Output**: ElevenLabs/Local TTS -> Frontend.

## Design Patterns
- **Provider Agnostic**: Easily swap Groq for OpenAI.
- **Zero-Stuffing**: Prompts are kept lean; context is pulled on-demand via Tools.
- **Vertical Slices**: Code is grouped by functionality (Aries, MCP, Compiler).
