"""Unit tests for the ActionTrigger service.

These tests verify the parsing of structured action triggers from LLM
responses, ensuring that action types and payloads are correctly
extracted and formatted.
"""

from app.services.aries.actions.triggers import action_trigger


def test_parse_action_load_problem():
    """Verify parsing of LOAD_PROBLEM action."""
    res = action_trigger.parse_action("I will [LOAD_PROBLEM: two-sum] for you.")
    assert res == {"action": "LOAD_PROBLEM", "payload": {"slug": "two-sum"}}

    # Case insensitivity
    res = action_trigger.parse_action("[load_problem: add-two-numbers]")
    assert res == {"action": "LOAD_PROBLEM", "payload": {"slug": "add-two-numbers"}}


def test_parse_action_search_problems():
    """Verify parsing of SEARCH_PROBLEMS action."""
    res = action_trigger.parse_action("Let's look for [SEARCH_PROBLEMS: array]")
    assert res == {"action": "SEARCH_PROBLEMS", "payload": {"query": "array"}}


def test_parse_action_run_submit():
    """Verify parsing of RUN_CODE and SUBMIT_CODE actions."""
    assert action_trigger.parse_action("[RUN_CODE]") == {
        "action": "RUN_CODE",
        "payload": {},
    }
    assert action_trigger.parse_action("[SUBMIT_CODE]") == {
        "action": "SUBMIT_CODE",
        "payload": {},
    }


def test_parse_action_navigate():
    """Verify parsing of NAVIGATE action."""
    res = action_trigger.parse_action("[NAVIGATE: problems]")
    assert res == {"action": "NAVIGATE", "payload": {"view": "problems"}}


def test_parse_action_record_fact():
    """Verify parsing of RECORD_FACT action with parts."""
    # Full fact
    res = action_trigger.parse_action("[RECORD_FACT: recursion | basics]")
    assert res == {
        "action": "RECORD_FACT",
        "payload": {"concept": "recursion", "value": "basics"},
    }

    # Missing value part
    res = action_trigger.parse_action("[RECORD_FACT: python]")
    assert res == {
        "action": "RECORD_FACT",
        "payload": {"concept": "python", "value": ""},
    }


def test_parse_action_no_match():
    """Verify return of None for responses without triggers."""
    assert action_trigger.parse_action("No action here") is None
    assert action_trigger.parse_action("[INVALID_ACTION: test]") is None


def test_parse_action_regex_robustness():
    """Verify that the regex handles varying whitespace."""
    res = action_trigger.parse_action("[  LOAD_PROBLEM  :   test-slug  ]")
    assert res == {"action": "LOAD_PROBLEM", "payload": {"slug": "test-slug"}}
