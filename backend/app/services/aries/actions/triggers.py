from typing import Optional, Dict, Any


class ActionTrigger:
    @staticmethod
    def parse_action(llm_response: str) -> Optional[Dict[str, Any]]:
        """
        Detects if the LLM response contains a structured action trigger.
        Example: [LOAD_PROBLEM: reverse-linked-list]
        """
        # Simple string-based detection for now.
        # In a production app, we might use JSON Mode or Tool Calling.
        if "[LOAD_PROBLEM:" in llm_response:
            try:
                slug = llm_response.split("[LOAD_PROBLEM:")[1].split("]")[0].strip()
                return {"action": "LOAD_PROBLEM", "payload": {"slug": slug}}
            except:
                pass

        return None


action_trigger = ActionTrigger()
