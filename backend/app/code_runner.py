import asyncio
import os
import tempfile
import sys


async def run_python(code: str, stdin: str = "", timeout: float = 5) -> dict:
    imports = "from typing import *\nfrom collections import *\nfrom heapq import *\nfrom bisect import *\nimport math\n\n"
    full = imports + code

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(full)
        path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin.encode() if stdin else None), timeout
        )
        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "exit_code": proc.returncode or 0,
        }
    finally:
        os.unlink(path)
