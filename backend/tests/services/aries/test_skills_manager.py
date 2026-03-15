"""Unit tests for the SkillManager service.

These tests verify the loading of skill registries from disk, skill
retrieval, and system prompt assembly, using mocks to isolate tests
from the actual filesystem.
"""

import json
from unittest.mock import mock_open, patch

import pytest
from app.core.aries.models import SkillDefinition
from app.services.aries.skills.manager import SkillManager


@pytest.fixture
def mock_registry_data():
    return {
        "aries-default": {
            "name": "Default Aries",
            "persona": "A helpful assistant",
            "prompt_extension": "Be concise.",
            "triggers": ["hey aries"],
            "supported_actions": ["UI:NAVIGATE"],
        },
        "ram-charge": {
            "name": "Ram Charge",
            "persona": "An aggressive tester",
            "prompt_extension": "Find all bugs.",
            "triggers": ["ram charge"],
            "supported_actions": ["CODE:DEBUG"],
        },
    }


def test_skill_manager_load_registry_success(mock_registry_data):
    """Verify that the registry is correctly loaded into SkillDefinition models."""
    with patch("os.path.exists", return_value=True):
        with patch(
            "builtins.open", mock_open(read_data=json.dumps(mock_registry_data))
        ):
            manager = SkillManager()
            assert len(manager.skills) == 2
            assert "aries-default" in manager.skills
            assert isinstance(manager.skills["aries-default"], SkillDefinition)
            assert manager.skills["aries-default"].persona == "A helpful assistant"


def test_skill_manager_load_registry_not_found():
    """Verify handling of a missing registry file."""
    with patch("os.path.exists", return_value=False):
        manager = SkillManager()
        assert manager.skills == {}


def test_skill_manager_load_registry_invalid_json():
    """Verify handling of corrupted JSON in the registry."""
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="invalid-json")):
            manager = SkillManager()
            assert manager.skills == {}


def test_skill_manager_get_skill(mock_registry_data):
    """Verify retrieval of specific skills."""
    with patch("os.path.exists", return_value=True):
        with patch(
            "builtins.open", mock_open(read_data=json.dumps(mock_registry_data))
        ):
            manager = SkillManager()
            skill = manager.get_skill("ram-charge")
            assert skill is not None
            assert skill.id == "ram-charge"

            assert manager.get_skill("non-existent") is None


def test_skill_manager_get_system_prompt(mock_registry_data):
    """Verify system prompt assembly with and without code context."""
    with patch("os.path.exists", return_value=True):
        with patch(
            "builtins.open", mock_open(read_data=json.dumps(mock_registry_data))
        ):
            manager = SkillManager()

            # Test valid skill
            prompt = manager.get_system_prompt("aries-default")
            assert "Persona: A helpful assistant" in prompt
            assert "Be concise." in prompt

            # Test with code context
            prompt = manager.get_system_prompt("aries-default", code_context="print(1)")
            assert "Current Code Context:\nprint(1)" in prompt


def test_skill_manager_get_system_prompt_fallbacks(mock_registry_data):
    """Verify fallback logic when requested or default skills are missing."""
    with patch("os.path.exists", return_value=True):
        with patch(
            "builtins.open", mock_open(read_data=json.dumps(mock_registry_data))
        ):
            manager = SkillManager()

            # Fallback to aries-default
            prompt = manager.get_system_prompt("unknown-skill")
            assert "Persona: A helpful assistant" in prompt

    # Hard fallback when even aries-default is missing
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="{}")):
            manager = SkillManager()
            prompt = manager.get_system_prompt("any")
            assert "You are Aries, a helpful coding assistant." == prompt
