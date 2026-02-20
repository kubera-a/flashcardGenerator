"""
Card Generation Module
---------------------
Uses LLMs to generate flashcards from processed content.
"""

import json
import logging

from config.prompts import GENERATION_PROMPT, VALIDATION_PROMPT
from modules.llm_interface import LLMInterface

logger = logging.getLogger(__name__)


class FlashCard:
    """Represents a single Anki flashcard."""

    def __init__(self, front: str, back: str, tags: list[str] = None):
        self.front = front
        self.back = back
        self.tags = tags or []

    def to_dict(self) -> dict:
        return {"front": self.front, "back": self.back, "tags": self.tags}

    @classmethod
    def from_dict(cls, data: dict) -> "FlashCard":
        return cls(
            front=data.get("front", ""),
            back=data.get("back", ""),
            tags=data.get("tags", []),
        )


class CardGenerator:
    """Generates Anki flashcards from content using LLMs and centralized prompts."""

    def __init__(
        self,
        llm_interface: LLMInterface | None = None,
        llm_provider: str = "openai",
    ):
        self.llm = llm_interface or LLMInterface(provider=llm_provider)

    def generate_cards_from_chunk(
        self, content: str, metadata: dict
    ) -> list[FlashCard]:
        """Generate flashcards from a single content chunk using centralized prompts."""
        logger.info("Generating cards from content chunk")

        system_prompt = GENERATION_PROMPT.system_prompt
        user_prompt = GENERATION_PROMPT.user_prompt_template
        output_format = GENERATION_PROMPT.output_format

        # Append the document content to the prompt
        full_prompt = f"{user_prompt}\n\n## Document Content:\n{content}"

        try:
            response = self.llm.generate_structured_output(
                prompt=full_prompt,
                output_format=output_format,
                system_prompt=system_prompt,
            )

            cards = []
            for card_data in response.get("cards", []):
                card = FlashCard(
                    front=card_data.get("front", ""),
                    back=card_data.get("back", ""),
                    tags=[],
                )
                cards.append(card)

            logger.info(f"Generated {len(cards)} cards from chunk")
            return cards

        except Exception as e:
            logger.error(f"Error generating cards: {e}")
            return []

    def validate_cards(self, cards: list[FlashCard]) -> list[FlashCard]:
        """Validate and improve generated cards using centralized prompts."""
        if not cards:
            return []

        logger.info(f"Validating {len(cards)} cards")

        system_prompt = VALIDATION_PROMPT.system_prompt
        output_format = VALIDATION_PROMPT.output_format

        cards_json = json.dumps([card.to_dict() for card in cards], indent=2)
        user_prompt = VALIDATION_PROMPT.user_prompt_template.format(cards_json=cards_json)

        try:
            response = self.llm.generate_structured_output(
                prompt=user_prompt,
                output_format=output_format,
                system_prompt=system_prompt,
            )

            improved_cards = []
            for card_data in response.get("improved_cards", []):
                card = FlashCard.from_dict(card_data)
                improved_cards.append(card)

            logger.info(f"Validated and improved {len(improved_cards)} cards")
            return improved_cards

        except Exception as e:
            logger.error(f"Error validating cards: {e}")
            return cards
