"""Unit tests for the CompilerInfrastructure executor.

These tests verify the low-level mechanics of Python code execution,
including subprocess management, timeouts, and error handling,
using mocks to avoid actual OS process creation.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from app.infrastructure.compiler.executor import compiler_infra


@pytest.mark.asyncio
async def test_run_raw_python_success():
    """Verify successful execution of raw Python code."""
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"hello\n", b"")
    mock_process.returncode = 0

    with patch(
        "asyncio.create_subprocess_exec", return_value=mock_process
    ) as mock_exec:
        result = await compiler_infra.run_raw_python("print('hello')")

        assert result["stdout"] == "hello\n"
        assert result["stderr"] == ""
        assert result["exit_code"] == 0
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_run_raw_python_timeout():
    """Verify handling of execution timeouts."""
    mock_process = AsyncMock()
    # Simulate timeout by having communicate raise TimeoutError when wrapped in wait_for
    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await compiler_infra.run_raw_python("print('blocking')")

            assert result["exit_code"] == -1
            assert "timed out" in result["stderr"]


@pytest.mark.asyncio
async def test_run_raw_python_exception():
    """Verify that generic exceptions are wrapped in RuntimeError."""
    with patch("tempfile.NamedTemporaryFile", side_effect=Exception("Disk Full")):
        with pytest.raises(RuntimeError) as excinfo:
            await compiler_infra.run_raw_python("print('fail')")
        assert "INFRA: Execution failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_run_driver_script_success():
    """Verify successful execution of a driver script."""
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b'{"testcases": []}', b"")
    mock_process.returncode = 0

    with patch(
        "asyncio.create_subprocess_exec", return_value=mock_process
    ) as mock_exec:
        stdout, stderr = await compiler_infra.run_driver_script("print('driver')")

        assert stdout == '{"testcases": []}'
        assert stderr == ""
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_run_driver_script_timeout():
    """Verify timeout handling for driver scripts."""
    mock_process = AsyncMock()
    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            stdout, stderr = await compiler_infra.run_driver_script("...")
            assert stdout == "[]"
            assert "timed out" in stderr


@pytest.mark.asyncio
async def test_run_driver_script_exception():
    """Verify exception handling for driver scripts."""
    with patch("tempfile.NamedTemporaryFile", side_effect=Exception("Crash")):
        with pytest.raises(RuntimeError) as excinfo:
            await compiler_infra.run_driver_script("...")
        assert "INFRA: Driver execution failed" in str(excinfo.value)
