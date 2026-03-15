"""Low-level infrastructure for Python code execution.

This module provides the core mechanism for spawning sandboxed subprocesses
to execute arbitrary Python code. It handles temporary file management,
input/output streaming, and execution timeouts.
"""

import asyncio
import os
import tempfile
from typing import Any


class CompilerInfrastructure:
    """Handles the low-level mechanics of Python subprocess execution."""

    @staticmethod
    async def run_raw_python(code: str, stdin: str = "") -> dict[str, Any]:
        """Low-level subprocess execution of Python code.

        Wraps the user code with common imports and executes it in a
        sandboxed subprocess.

        Args:
            code (str): The raw Python code to execute.
            stdin (str, optional): Standard input to provide to the script.

        Returns:
            dict[str, Any]: A dictionary containing stdout, stderr, and exit_code.

        Raises:
            RuntimeError: If the subprocess execution fails fundamentally.
        """
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                # Inject common competitive programming imports
                full_code = (
                    "from typing import *\n"
                    "from collections import *\n"
                    "from heapq import *\n"
                    "from bisect import *\n"
                    "import math\n\n" + code
                )
                f.write(full_code)
                path = f.name

            try:
                proc = await asyncio.create_subprocess_exec(
                    "python3",
                    path,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=stdin.encode() if stdin else None),
                    timeout=5.0,
                )

                return {
                    "stdout": stdout.decode(),
                    "stderr": stderr.decode(),
                    "exit_code": proc.returncode or 0,
                }
            finally:
                # Ensure clean-up of temporary execution files
                if os.path.exists(path):
                    os.unlink(path)
        except asyncio.TimeoutError:
            return {
                "stdout": "",
                "stderr": "Execution timed out (5.0s limit).",
                "exit_code": -1,
            }
        except Exception as e:
            raise RuntimeError(f"INFRA: Execution failed: {str(e)}")

    @staticmethod
    async def run_driver_script(driver_code: str) -> tuple[str, str]:
        """Executes a generated driver script and returns outputs.

        This is used for sophisticated test-case evaluation where a
        driver script (Solution class + runner) is generated.

        Args:
            driver_code (str): The full Python script containing the driver logic.

        Returns:
            Tuple[str, str]: A tuple of (stdout, stderr).

        Raises:
            RuntimeError: If the driver execution fails.
        """
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(driver_code)
                path = f.name

            try:
                proc = await asyncio.create_subprocess_exec(
                    "python3",
                    path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=10.0
                )

                return stdout.decode().strip(), stderr.decode().strip()
            finally:
                if os.path.exists(path):
                    os.unlink(path)
        except asyncio.TimeoutError:
            return "[]", "Execution timed out (10.0s limit)."
        except Exception as e:
            raise RuntimeError(f"INFRA: Driver execution failed: {str(e)}")


# Singleton instance for global access
compiler_infra = CompilerInfrastructure()
