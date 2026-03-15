# Python Backend Development Workflow (uv + Ruff + Black + isort + Pytest)

This guide explains the daily development workflow for a Python backend
using:

-   uv (package manager)
-   Ruff (linting)
-   Black (code formatting)
-   isort (import sorting)
-   Pytest (testing)

This setup is commonly used in modern Python backend and AI projects.

------------------------------------------------------------------------

# 1. Install Dependencies

## Install runtime dependencies

These are required to run the application.

``` bash
uv sync
```

## Install development dependencies

These include formatting, linting, and testing tools.

``` bash
uv sync --dev
```

------------------------------------------------------------------------

# 2. Linting Code

Linting checks your code for:

-   unused imports
-   undefined variables
-   code style issues
-   potential bugs

Run:

``` bash
uv run ruff check .
```

### Auto-fix lint issues

``` bash
uv run ruff check . --fix
```

This automatically fixes:

-   unused imports
-   unused variables
-   simple formatting issues

------------------------------------------------------------------------

# 3. Sorting Imports

Use isort to organize imports consistently.

``` bash
uv run isort .
```

Example transformation:

Before:

``` python
import sys
import os
from fastapi import FastAPI
```

After:

``` python
import os
import sys

from fastapi import FastAPI
```

------------------------------------------------------------------------

# 4. Formatting Code

Black formats Python code automatically.

Run:

``` bash
uv run black .
```

Black enforces:

-   consistent indentation
-   line length
-   spacing
-   formatting standards

Check formatting without modifying files:

``` bash
uv run black --check .
```

Show formatting differences:

``` bash
uv run black --diff .
```

------------------------------------------------------------------------

# 5. Running Tests

Run tests using pytest:

``` bash
uv run pytest
```

Run with detailed output:

``` bash
uv run pytest -v
```

Run a specific test file:

``` bash
uv run pytest tests/test_file.py
```

Run a specific test function:

``` bash
uv run pytest tests/test_file.py::test_function
```

------------------------------------------------------------------------

# 6. Recommended Daily Workflow

Most developers follow this order:

``` bash
uv run ruff check . --fix
uv run isort .
uv run black .
uv run pytest
```

------------------------------------------------------------------------

# 7. One Command Workflow (Recommended)

You can combine everything:

``` bash
uv run ruff check . --fix && uv run isort . && uv run black . && uv run pytest
```

------------------------------------------------------------------------

# 8. Optional: Create a Makefile

Create a file named `Makefile` in the project root.

    lint:
        uv run ruff check . --fix

    format:
        uv run isort .
        uv run black .

    test:
        uv run pytest

    all: lint format test

Now you can run:

``` bash
make all
```

------------------------------------------------------------------------

# 9. Typical Project Structure

Example backend structure:

    backend/
    │
    ├── app/
    │   ├── api/
    │   ├── services/
    │   ├── core/
    │   └── infrastructure/
    │
    ├── tests/
    │
    ├── pyproject.toml
    └── README.md

------------------------------------------------------------------------

# 10. Summary

Daily development loop:

1.  Write code
2.  Run lint fix
3.  Sort imports
4.  Format code
5.  Run tests

Commands:

``` bash
uv run ruff check . --fix
uv run isort .
uv run black .
uv run pytest
```

This ensures:

-   clean code
-   consistent style
-   fewer bugs
-   reliable tests
