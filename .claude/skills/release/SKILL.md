# Skill: Releasing Aries

Instructions for deploying and releasing updates.

## Checklist
1. **Version Bump**: Update version in `pyproject.toml`.
2. **Test Suite**: Pass 100% of tests via `backend/.venv/bin/pytest`.
3. **Documentation**: Ensure all new ADRs (Architectural Decision Records) are in `docs/decisions/`.
4. **Environment**: Verify `.env.example` is up to date.

## Deployment
- Currently managed via CI/CD pipelines (GitHub Actions).
- Ensure Redis and MongoDB migrations are handled before code deployment.
