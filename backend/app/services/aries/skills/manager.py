import json
import os
from typing import Dict, Optional

from app.core.aries.models import SkillDefinition


class SkillManager:
    def __init__(self):
        self.registry_path = os.path.join(os.path.dirname(__file__), "registry.json")
        self.skills: Dict[str, SkillDefinition] = {}
        self.load_registry()

    def load_registry(self):
        try:
            with open(self.registry_path, "r") as f:
                data = json.load(f)
                for skill_id, details in data.items():
                    self.skills[skill_id] = SkillDefinition(id=skill_id, **details)
        except Exception as e:
            print(f"Failed to load skill registry: {e}")

    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        return self.skills.get(skill_id)

    def get_system_prompt(self, skill_id: str, code_context: str = "") -> str:
        skill = self.get_skill(skill_id) or self.skills.get("aries-default")
        base_prompt = (
            f"Persona: {skill.persona}\n\nStrict Rules:\n{skill.prompt_extension}"
        )
        if code_context:
            base_prompt += f"\n\nCurrent Code Context:\n{code_context}"
        return base_prompt


skill_manager = SkillManager()
