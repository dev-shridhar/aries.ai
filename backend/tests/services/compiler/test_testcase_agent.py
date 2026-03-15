"""Unit tests for the TestCaseAgent service.

These tests verify the generation of hidden test cases using mocks for
the Groq client, ensuring robust handling of LLM responses and errors.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.services.compiler.testcase_agent import generate_hidden_testcases


@pytest.mark.asyncio
async def test_generate_hidden_testcases_success():
    """Verify successful test case generation and parsing."""
    mock_testcases = [
        {"input": "5", "expected_output": "25"},
        {"input": "0", "expected_output": "0"},
    ]
    mock_response_content = json.dumps({"testcases": mock_testcases})

    # Mock settings to ensure API Key is set
    with patch.object(settings, "GROQ_API_KEY", "fake-key"):
        # Mock the Groq client
        with patch("app.services.compiler.testcase_agent.Groq") as mock_groq_class:
            mock_client = MagicMock()
            mock_groq_class.return_value = mock_client

            # Setup the nested mock for client.chat.completions.create
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = mock_response_content
            mock_client.chat.completions.create.return_value = mock_response

            result = await generate_hidden_testcases("Square", "Return n*n", "n >= 0")

            assert result == mock_testcases
            mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_hidden_testcases_missing_api_key():
    """Verify that generation is skipped if API key is missing."""
    with patch.object(settings, "GROQ_API_KEY", ""):
        result = await generate_hidden_testcases("Square", "Return n*n", "n >= 0")
        assert result == []


@pytest.mark.asyncio
async def test_generate_hidden_testcases_empty_response():
    """Verify handling of empty LLM response."""
    with patch.object(settings, "GROQ_API_KEY", "fake-key"):
        with patch("app.services.compiler.testcase_agent.Groq") as mock_groq_class:
            mock_client = MagicMock()
            mock_groq_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = ""
            mock_client.chat.completions.create.return_value = mock_response

            result = await generate_hidden_testcases("Square", "...", "...")
            assert result == []


@pytest.mark.asyncio
async def test_generate_hidden_testcases_json_with_markdown():
    """Verify that markdown code blocks in JSON response are handled."""
    mock_testcases = [{"input": "1", "expected_output": "1"}]
    # Simulate LLM wrapping JSON in markdown blocks
    mock_response_content = (
        "```json\n" + json.dumps({"testcases": mock_testcases}) + "\n```"
    )

    with patch.object(settings, "GROQ_API_KEY", "fake-key"):
        with patch("app.services.compiler.testcase_agent.Groq") as mock_groq_class:
            mock_client = MagicMock()
            mock_groq_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = mock_response_content
            mock_client.chat.completions.create.return_value = mock_response

            result = await generate_hidden_testcases("Square", "...", "...")
            assert result == mock_testcases


@pytest.mark.asyncio
async def test_generate_hidden_testcases_exception():
    """Verify that exceptions return an empty list gracefully."""
    with patch.object(settings, "GROQ_API_KEY", "fake-key"):
        with patch("app.services.compiler.testcase_agent.Groq") as mock_groq_class:
            mock_client = MagicMock()
            mock_groq_class.return_value = mock_client

            mock_client.chat.completions.create.side_effect = Exception("API Down")

            result = await generate_hidden_testcases("Square", "...", "...")
            assert result == []
