import asyncio
import json
import os
import tempfile
import re
from typing import Any


class CompilerInfrastructure:
    @staticmethod
    async def run_raw_python(code: str, stdin: str = "") -> dict[str, Any]:
        """Low-level subprocess execution of Python code."""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                full_code = (
                    "from typing import *\nfrom collections import *\nfrom heapq import *\nfrom bisect import *\nimport math\n\n"
                    + code
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
                os.unlink(path)
        except Exception as e:
            raise RuntimeError(f"Infrastructure execution failed: {str(e)}")

    @staticmethod
    async def run_driver_script(driver_code: str) -> tuple[str, str]:
        """Executes a generated driver script and returns stdout/stderr."""
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
                os.unlink(path)
        except Exception as e:
            raise RuntimeError(f"Driver execution failed: {str(e)}")


compiler_infra = CompilerInfrastructure()
