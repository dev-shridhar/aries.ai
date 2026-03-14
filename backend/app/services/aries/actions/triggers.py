from typing import Any, Dict, Optional


class ActionTrigger:
    @staticmethod
    def parse_action(llm_response: str) -> Optional[Dict[str, Any]]:
        """
        Detects if the LLM response contains a structured action trigger.
        Example: [LOAD_PROBLEM: reverse-linked-list]
        """
        import re

        # Regex for [ACTION: optional_payload]
        # Allowing optional space before colon and after
        pattern = r"\[([A-Z_]+)\s*(?::\s*([^\]]+))?\]"
        match = re.search(pattern, llm_response, re.IGNORECASE)

        if match:
            action = match.group(1).upper()
            payload_str = match.group(2).strip() if match.group(2) else ""

            if action == "LOAD_PROBLEM":
                return {"action": "LOAD_PROBLEM", "payload": {"slug": payload_str}}
            elif action == "SEARCH_PROBLEMS":
                return {"action": "SEARCH_PROBLEMS", "payload": {"query": payload_str}}
            elif action == "RUN_CODE":
                return {"action": "RUN_CODE", "payload": {}}
            elif action == "SUBMIT_CODE":
                return {"action": "SUBMIT_CODE", "payload": {}}
            elif action == "NAVIGATE":
                return {"action": "NAVIGATE", "payload": {"view": payload_str}}
            elif action == "RECORD_FACT":
                parts = payload_str.split("|", 1)
                concept = parts[0].strip() if len(parts) > 0 else "unknown"
                value = parts[1].strip() if len(parts) > 1 else ""
                return {
                    "action": "RECORD_FACT",
                    "payload": {"concept": concept, "value": value},
                }

        return None


action_trigger = ActionTrigger()
