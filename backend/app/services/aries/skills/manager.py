import json
import logging
import os

from app.core.aries.models import SkillDefinition

logger = logging.getLogger(__name__)


class SkillManager:
    """Registry and orchestrator for Aries AI 'Skills' or personas.

    Skills define the persona, system prompt extensions, and domain-specific
    logic for the Aries agent. This manager loads these definitions from a
    static registry and provides methods for prompt assembly.

    Attributes:
        registry_path (str): File path to the JSON skill registry.
        skills (Dict[str, SkillDefinition]): Cached map of skill IDs to definitions.
    """

    def __init__(self):
        """Initializes the SkillManager and loads the registry from disk."""
        self.registry_path = os.path.join(os.path.dirname(__file__), "registry.json")
        self.skills: dict[str, SkillDefinition] = {}
        self.load_registry()

    def load_registry(self) -> None:
        """Parses the registry.json file into SkillDefinition models.

        Uses the Pydantic SkillDefinition model to ensure schema validation
        for all registered skill personas.
        """
        try:
            if not os.path.exists(self.registry_path):
                logger.warning(
                    f"SKILLS: Registry file not found at {self.registry_path}"
                )
                return

            with open(self.registry_path) as f:
                data = json.load(f)
                for skill_id, details in data.items():
                    self.skills[skill_id] = SkillDefinition(id=skill_id, **details)
            logger.info(f"SKILLS: Loaded {len(self.skills)} skills from registry.")
        except Exception as e:
            logger.error(f"SKILLS: Failed to load skill registry: {e}")

    def get_skill(self, skill_id: str) -> SkillDefinition | None:
        """Retrieves a specific skill definition by its unique ID.

        Args:
            skill_id (str): The identifier (e.g., 'aries-default', 'ram-charge').

        Returns:
            Optional[SkillDefinition]: The skill model if registered, else None.
        """
        return self.skills.get(skill_id)

    def get_system_prompt(self, skill_id: str, code_context: str = "") -> str:
        """Assembles a full system prompt based on the selected skill persona.

        Args:
            skill_id (str): The target skill ID.
            code_context (str): Optional code snippet to inject into the persona's mind.

        Returns:
            str: The formatted system prompt ready for LLM consumption.
        """
        skill = self.get_skill(skill_id) or self.skills.get("aries-default")
        if not skill:
            # Fallback if even default is missing
            return "You are Aries, a helpful coding assistant."

        base_prompt = (
            f"Persona: {skill.persona}\n\nStrict Rules:\n{skill.prompt_extension}"
        )
        if code_context:
            base_prompt += f"\n\nCurrent Code Context:\n{code_context}"
        return base_prompt


# Global singleton instance for skill management across the Aries service.
skill_manager = SkillManager()
