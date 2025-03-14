"""
Pipeline Module
-------------
Coordinates the entire flashcard generation process.
"""

import logging
import time
from pathlib import Path

from tqdm import tqdm

from config.settings import DEFAULT_LLM_PROVIDER
from modules.anki_integration import AnkiExporter
from modules.card_generation import CardGenerator, FlashCard
from modules.llm_interface import LLMInterface
from modules.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)


class Pipeline:
    """Main pipeline for coordinating the flashcard generation process."""

    def __init__(self, llm_provider: str = DEFAULT_LLM_PROVIDER, max_cards: int = 50):
        """
        Initialize the pipeline.

        Args:
            llm_provider: LLM provider to use
            max_cards: Maximum number of cards to generate in total
        """
        self.llm_provider = llm_provider
        self.max_cards = max_cards

        # Initialize components
        self.pdf_processor = PDFProcessor()
        self.llm_interface = LLMInterface(provider=llm_provider)
        self.card_generator = CardGenerator(
            llm_interface=self.llm_interface, llm_provider=llm_provider
        )
        self.anki_exporter = AnkiExporter()

        logger.info(
            f"Initialized pipeline with provider: {llm_provider}, max cards: {max_cards}"
        )

    def _deduplicate_cards(self, cards: list[FlashCard]) -> list[FlashCard]:
        """
        Remove duplicate cards based on front content.

        Args:
            cards: List of FlashCard objects

        Returns:
            Deduplicated list of FlashCard objects
        """
        seen_fronts = set()
        unique_cards = []

        for card in cards:
            # Normalize the front text for comparison (lowercase, strip whitespace)
            normalized_front = card.front.lower().strip()

            if normalized_front not in seen_fronts:
                seen_fronts.add(normalized_front)
                unique_cards.append(card)

        logger.info(f"Deduplicated cards: {len(cards)} → {len(unique_cards)}")
        return unique_cards

    def run(self, pdf_path: str | Path, output_path: str | Path | None = None) -> dict:
        """
        Run the full pipeline to generate flashcards from a PDF.

        Args:
            pdf_path: Path to the PDF file
            output_path: Path for the output file or None to use default

        Returns:
            Dictionary with pipeline results
        """
        start_time = time.time()
        logger.info(f"Starting pipeline for {pdf_path}")

        # Convert path to Path object
        pdf_path = Path(pdf_path)

        # Step 1: Process the PDF
        chunks, metadata = self.pdf_processor.process_pdf(pdf_path)
        logger.info(f"Processed PDF into {len(chunks)} chunks")

        # Step 2: Generate cards from chunks
        all_cards = []
        cards_needed = self.max_cards

        # Use tqdm for a progress bar
        for chunk in tqdm(chunks, desc="Generating cards", unit="chunk"):
            # Skip if we've reached the maximum number of cards
            if cards_needed <= 0:
                break

            # Generate cards from the current chunk
            chunk_cards = self.card_generator.generate_cards_from_chunk(chunk, metadata)

            # Validate and improve the generated cards
            improved_cards = self.card_generator.validate_cards(chunk_cards)

            # Add the cards to our collection
            all_cards.extend(improved_cards[:cards_needed])
            cards_needed -= len(improved_cards)

            # Small delay to avoid rate limits
            time.sleep(0.5)

        # Step 3: Deduplicate cards
        unique_cards = self._deduplicate_cards(all_cards)

        # Step 4: Export cards to Anki format
        if not unique_cards:
            logger.warning("No cards were generated")
            return {
                "success": False,
                "message": "No cards were generated",
                "card_count": 0,
                "output_path": None,
            }

        export_result = self.anki_exporter.export_with_instructions(
            unique_cards, output_path
        )

        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        logger.info(f"Pipeline completed in {elapsed_time:.2f} seconds")

        # Return results
        return {
            "success": True,
            "card_count": export_result["card_count"],
            "output_path": export_result["csv_path"],
            "instructions_path": export_result["instructions_path"],
            "elapsed_time": elapsed_time,
        }
