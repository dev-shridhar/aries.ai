# Skill: Debugging Aries

Instructions for diagnosing issues in the voice-to-logic pipeline.

## Triage Order
1. **STT Issues**: Check Deepgram API logs and `stt.py` output. Ensure audio bytes are valid.
2. **Brain Issues**: Check Groq API responsiveness. Verify Tool calls in the LangGraph trace.
3. **Memory Issues**: Check Redis connection and MongoDB state. Use the `Memory Reset` runbook if state is corrupted.

## Debugging Tools
- `tools/scripts/verify_brain_migration.py`: Tests the full Brain retrieval loop.
- `uv pip list`: Check installed packages via uv.
- `uv pip show <package>`: Check specific package version.
- `backend/tests/`: Unit tests for individual components.
