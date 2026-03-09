import pytest
from app.services.compiler.service import CompilerService


@pytest.mark.asyncio
async def test_run_python_basic():
    """Test basic Python code execution via CompilerService."""
    code = "print('hello world')"
    result = await CompilerService.run_python(code)
    assert result["stdout"].strip() == "hello world"
    assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_run_python_timeout():
    """Test that long-running code is timed out."""
    code = "import time\ntime.sleep(10)"
    with pytest.raises(Exception) as excinfo:
        await CompilerService.run_python(code)
    assert "timed out" in str(excinfo.value)


@pytest.mark.asyncio
async def test_run_examples():
    """Test the example runner logic with a dummy solution."""
    code = """
class Solution:
    def add(self, a: int, b: int) -> int:
        return a + b
"""
    raw_examples = "1\n2\n10\n20"
    expected_outputs = ["3", "30"]
    results, err = await CompilerService.run_examples(
        code=code,
        raw_examples=raw_examples,
        expected_outputs=expected_outputs,
        public_cases_count=2,
    )
    assert len(results) == 2
    assert results[0]["passed"] is True
    assert results[1]["passed"] is True
    assert results[0]["output"] == "3"
