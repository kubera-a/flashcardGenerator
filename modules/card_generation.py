"""
Card Generation Module
---------------------
Uses LLMs to generate flashcards from processed content.
"""

import logging

from config.settings import MAX_CARDS_PER_CHUNK
from modules.llm_interface import LLMInterface

logger = logging.getLogger(__name__)


class FlashCard:
    """Represents a single Anki flashcard."""

    def __init__(self, front: str, back: str, tags: list[str] = None):
        """
        Initialize a flashcard.

        Args:
            front: The question or front side of the card
            back: The answer or back side of the card
            tags: List of tags for the card
        """
        self.front = front
        self.back = back
        self.tags = tags or []

    def to_dict(self) -> dict:
        """
        Convert the flashcard to a dictionary.

        Returns:
            Dictionary representation of the flashcard
        """
        return {"front": self.front, "back": self.back, "tags": self.tags}

    @classmethod
    def from_dict(cls, data: dict) -> "FlashCard":
        """
        Create a flashcard from a dictionary.

        Args:
            data: Dictionary representation of a flashcard

        Returns:
            FlashCard instance
        """
        return cls(
            front=data.get("front", ""),
            back=data.get("back", ""),
            tags=data.get("tags", []),
        )


class CardGenerator:
    """Generates Anki flashcards from content using LLMs."""

    def __init__(
        self,
        llm_interface: LLMInterface | None = None,
        llm_provider: str = "openai",
        max_cards_per_chunk: int = MAX_CARDS_PER_CHUNK,
    ):
        """
        Initialize the card generator.

        Args:
            llm_interface: LLMInterface instance or None to create a new one
            llm_provider: LLM provider to use if creating a new interface
            max_cards_per_chunk: Maximum number of cards to generate per content chunk
        """
        self.llm = llm_interface or LLMInterface(provider=llm_provider)
        self.max_cards_per_chunk = max_cards_per_chunk

    def _create_generation_prompt(self, content: str, metadata: dict) -> str:
        """
        Create a prompt for flashcard generation.

        Args:
            content: Text content to generate cards from
            metadata: Metadata about the source document

        Returns:
            Formatted prompt string
        """
        prompt = f"""
        I need you to create effective Anki flashcards based on the following content from a technical document about software engineering.
        
        Document Information:
        Title: {metadata.get('title', 'Unknown')}
        Author: {metadata.get('author', 'Unknown')}
        
        Content:
        ```
        {content}
        ```
        
        Create up to {self.max_cards_per_chunk} high-quality flashcards with the following characteristics:
        1. Each card should focus on a single, clear concept
        2. The question (front) should be specific and unambiguous
        3. The answer (back) should be concise but complete
        4. Prioritize important concepts over trivial details
        5. Avoid overly complex or compound questions
        6. Formulate questions that test understanding, not just recall
        7. Use clear, straightforward language
        
        For technical content, create cards that:
        - Focus on core principles and concepts
        - Include key definitions of important terms
        - Cover relationships between concepts
        - Address common misconceptions
        - Include practical applications where relevant
        
        Return the cards as JSON only.
        """
        return prompt

    def _create_system_prompt(self) -> str:
        """
        Create a system prompt for the LLM.

        Returns:
            System prompt string
        """
        return """
        You are an expert in creating educational flashcards for software engineering topics.
        Your task is to generate high-quality Anki flashcards that follow best practices 
        for effective learning and retention.
        
        Always return your response in valid JSON format with no additional text or explanation.
        """

    def generate_cards_from_chunk(
        self, content: str, metadata: dict
    ) -> list[FlashCard]:
        """
        Generate flashcards from a single content chunk.

        Args:
            content: Text content to generate cards from
            metadata: Metadata about the source document

        Returns:
            List of FlashCard objects
        """
        logger.info("Generating cards from content chunk")

        # Define the expected output format
        output_format = {
            "cards": [
                {
                    "front": "Question text goes here",
                    "back": "Answer text goes here",
                    "tags": ["tag1", "tag2"],
                }
            ]
        }

        # Generate the structured output
        user_prompt = self._create_generation_prompt(content, metadata)
        system_prompt = self._create_system_prompt()

        try:
            response = self.llm.generate_structured_output(
                prompt=user_prompt,
                output_format=output_format,
                system_prompt=system_prompt,
            )

            # Convert the response to FlashCard objects
            cards = []
            for card_data in response.get("cards", []):
                # Add default tags from metadata
                tags = card_data.get("tags", [])

                # Add title-based tag if available
                if metadata.get("title"):
                    title_tag = metadata["title"].replace(" ", "_").lower()
                    tags.append(title_tag)

                # Add subject-based tag if available
                if metadata.get("subject"):
                    subject_tag = metadata["subject"].replace(" ", "_").lower()
                    tags.append(subject_tag)

                card = FlashCard(
                    front=card_data.get("front", ""),
                    back=card_data.get("back", ""),
                    tags=tags,
                )
                cards.append(card)

            logger.info(f"Generated {len(cards)} cards from chunk")
            return cards

        except Exception as e:
            logger.error(f"Error generating cards: {e}")
            return []

    def validate_cards(self, cards: list[FlashCard]) -> list[FlashCard]:
        """
        Validate and improve the generated cards using a separate LLM call.

        Args:
            cards: List of generated FlashCard objects

        Returns:
            List of validated and improved FlashCard objects
        """
        if not cards:
            return []

        logger.info(f"Validating {len(cards)} cards")

        # Prepare the validation prompt
        # cards_json = [card.to_dict() for card in cards]
        cards_str = "\n".join(
            [
                f"Card {i+1}:\nQ: {card.front}\nA: {card.back}"
                for i, card in enumerate(cards)
            ]
        )

        validation_prompt = f"""
        Review the following flashcards for quality and effectiveness:
        
        {cards_str}
        
        For each card, evaluate:
        1. Is the question clear and specific?
        2. Is the answer concise but complete?
        3. Does the card focus on an important concept?
        4. Is the card formatted properly?
        
        Improve any cards that don't meet these criteria.
        Return only the improved cards in JSON format.
        """

        validation_system_prompt = """
        You are an expert in educational psychology and spaced repetition learning.
        Your task is to review and improve flashcards for effectiveness.
        
        Return only valid JSON with the improved cards. Do not include any explanations or additional text.
        """

        # Define the expected output format
        output_format = {
            "improved_cards": [
                {
                    "front": "Improved question text",
                    "back": "Improved answer text",
                    "tags": ["tag1", "tag2"],
                }
            ]
        }

        try:
            response = self.llm.generate_structured_output(
                prompt=validation_prompt,
                output_format=output_format,
                system_prompt=validation_system_prompt,
            )

            # Convert the response to FlashCard objects
            improved_cards = []
            for card_data in response.get("improved_cards", []):
                card = FlashCard.from_dict(card_data)
                improved_cards.append(card)

            logger.info(f"Validated and improved {len(improved_cards)} cards")
            return improved_cards

        except Exception as e:
            logger.error(f"Error validating cards: {e}")
            # Return the original cards if validation fails
            return cards
