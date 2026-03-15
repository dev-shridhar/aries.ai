"""Unit tests for the CompilerService.

These tests verify the high-level orchestration of Python code execution
and example evaluation, using mocks to isolate the domain logic from
low-level infrastructure processes.
"""

from unittest.mock import AsyncMock, patch

import pytest
from app.services.compiler.service import CompilerService


@pytest.mark.asyncio
async def test_run_python_standard_output():
    """Verify that standard Python code execution returns expected stdout."""
    mock_result = {"stdout": "hello world\n", "stderr": "", "exit_code": 0}

    with patch(
        "app.services.compiler.service.compiler_infra.run_raw_python",
        new_callable=AsyncMock,
    ) as mock_run:
        mock_run.return_value = mock_result
        code = "print('hello world')"
        result = await CompilerService.run_python(code)
        assert result["stdout"].strip() == "hello world"
        assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_run_python_execution_failure():
    """Verify that failing Python code returns the correct exit status."""
    mock_result = {"stdout": "", "stderr": "Error", "exit_code": 1}

    with patch(
        "app.services.compiler.service.compiler_infra.run_raw_python",
        new_callable=AsyncMock,
    ) as mock_run:
        mock_run.return_value = mock_result
        result = await CompilerService.run_python("invalid syntax")
        assert result["exit_code"] == 1
        assert "Error" in result["stderr"]


@pytest.mark.asyncio
async def test_run_examples_logic_success():
    """Verify the example runner correctly parses success results."""
    mock_infra_json = (
        '[{"input": "1\\n2", "output": "3", "expected": "3", "passed": true}]'
    )
    mock_result = (mock_infra_json, "")

    with patch(
        "app.services.compiler.service.compiler_infra.run_driver_script",
        new_callable=AsyncMock,
    ) as mock_run:
        mock_run.return_value = mock_result
        results, err = await CompilerService.run_examples(
            code="class Solution: ...",
            raw_examples="1\n2",
            expected_outputs=["3"],
            public_cases_count=1,
        )
        assert len(results) == 1
        assert results[0]["passed"] is True
        assert results[0]["verified"] is False


@pytest.mark.asyncio
async def test_run_examples_json_recovery():
    """Verify recovery via regex when output contains non-JSON text."""
    dirty_output = 'Some debug logs\n[{"input": "1", "passed": true}]\nMore logs'
    with patch(
        "app.services.compiler.service.compiler_infra.run_driver_script",
        return_value=(dirty_output, ""),
    ):
        results, _ = await CompilerService.run_examples("...", "1", ["1"], 1)
        assert len(results) == 1
        assert results[0]["passed"] is True


@pytest.mark.asyncio
async def test_run_examples_parse_failure():
    """Verify error object when output is completely unparseable."""
    with patch(
        "app.services.compiler.service.compiler_infra.run_driver_script",
        return_value=("Garbage", ""),
    ):
        results, _ = await CompilerService.run_examples("...", "1", ["1"], 1)
        assert len(results) == 1
        assert "Failed to parse" in results[0]["error"]


@pytest.mark.asyncio
async def test_run_examples_fatal_error():
    """Verify exception isolation when infra fails."""
    with patch(
        "app.services.compiler.service.compiler_infra.run_driver_script",
        side_effect=Exception("Timeout"),
    ):
        with pytest.raises(Exception) as exc:
            await CompilerService.run_examples("...", "1", ["1"], 1)
        assert "run_examples failed" in str(exc.value)
