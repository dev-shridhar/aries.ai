import pytest
from app.code_runner import run_python


@pytest.mark.asyncio
async def test_run_python_success():
    result = await run_python("print('hello')")
    assert result["stdout"].strip() == "hello"
    assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_run_python_error():
    result = await run_python("1/0")
    assert "ZeroDivisionError" in result["stderr"]
    assert result["exit_code"] != 0
