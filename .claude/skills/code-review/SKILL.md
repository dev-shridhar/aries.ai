# Skill: Code Review

Instructions for reviewing Aries Python code.

## Focus Areas
1. **Formatting**: Ensure Python code is `black` formatted and imports are sorted (`isort`/`ruff`).
2. **Documentation**: Verify Google-style docstrings are present. Check for `README.md` flowcharts in new modules.
3. **Pydantic Models**: Ensure all API models use Pydantic v2 and have proper validation.
4. **Async Consistency**: Verify that no blocking I/O is used in `async` functions.
3. **Dependency Injection**: Check that services (like `AriesService`) are properly injected or instantiated via singleton adapters.
4. **Error Handling**: Every major action (Brain call, DB query) must have a `try-except` block with logging.

## Workflow
1. Run `backend/.venv/bin/pytest` to ensure existing tests pass.
2. Check for type hints on all function arguments and return values.
3. Verify that `CLAUDE.md` standards are followed.
