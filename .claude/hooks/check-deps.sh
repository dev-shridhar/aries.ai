#!/bin/bash
# Hook: Ensure uv is synced
# Path: .claude/hooks/check-deps.sh

echo "Checking dependencies with uv..."
cd backend && ../.venv/bin/python -m uv pip compile pyproject.toml --quiet
if [ $? -eq 0 ]; then
    echo "Dependencies are in sync."
else
    echo "Warning: pyproject.toml has changed. Please run 'uv pip sync'."
fi
