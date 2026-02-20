"""
Anki Integration Module
---------------------
Handles the formatting and export of flashcards for Anki.
"""

import csv
import logging
import os
import re
import shutil
from pathlib import Path

from config.settings import ANKI_CONFIG, OUTPUT_DIR
from modules.card_generation import FlashCard

logger = logging.getLogger(__name__)


class AnkiExporter:
    """Exports flashcards to Anki-compatible formats."""

    def __init__(self, config: dict | None = None):
        """
        Initialize the Anki exporter.

        Args:
            config: Configuration for the exporter (or None to use default)
        """
        self.config = config or ANKI_CONFIG

    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text for export to ensure compatibility.

        Args:
            text: The text to sanitize

        Returns:
            Sanitized text
        """
        # Replace characters that might cause issues in CSV
        text = text.replace('"', '""')  # Double quotes for CSV escaping

        # Handle HTML tags (could extend this for more complex sanitization)
        text = text.replace("<", "&lt;").replace(">", "&gt;")

        return text

    def _format_tags(self, tags: list[str]) -> str:
        """
        Format tags for Anki import.

        Args:
            tags: List of tag strings

        Returns:
            Formatted tag string
        """
        # Combine default tags with card-specific tags
        all_tags = set(self.config.get("default_tags", []) + tags)

        # Clean tags (remove spaces, etc.)
        clean_tags = []
        for tag in all_tags:
            # Replace spaces with underscores and remove special characters
            clean_tag = tag.replace(" ", "_")
            clean_tag = "".join(c for c in clean_tag if c.isalnum() or c in "_-")
            if clean_tag:
                clean_tags.append(clean_tag)

        # Join tags with spaces for Anki format
        return " ".join(clean_tags)

    def export_to_csv(
        self, cards: list[FlashCard], output_path: str | Path | None = None
    ) -> Path:
        """
        Export flashcards to a CSV file for Anki import.

        Args:
            cards: List of FlashCard objects to export
            output_path: Path for the output file or None to use default

        Returns:
            Path to the exported file
        """
        if not cards:
            logger.warning("No cards to export")
            raise ValueError("Cannot export empty card list")

        # Determine the output path
        if output_path is None:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            output_path = OUTPUT_DIR / "anki_cards.csv"
        else:
            output_path = Path(output_path)
            os.makedirs(output_path.parent, exist_ok=True)

        logger.info(f"Exporting {len(cards)} cards to {output_path}")

        # Write cards to CSV
        with open(output_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            # Write header
            writer.writerow(["front", "back", "tags"])

            # Write cards
            for card in cards:
                sanitized_front = self._sanitize_text(card.front)
                sanitized_back = self._sanitize_text(card.back)
                tags = self._format_tags(card.tags)

                writer.writerow([sanitized_front, sanitized_back, tags])

        logger.info(f"Successfully exported {len(cards)} cards to {output_path}")
        return output_path

    def generate_import_instructions(self, output_path: Path) -> str:
        """
        Generate instructions for importing the exported file into Anki.

        Args:
            output_path: Path to the exported file

        Returns:
            String with import instructions
        """
        instructions = f"""
        # Anki Import Instructions

        Follow these steps to import your generated flashcards into Anki:

        1. Open Anki on your computer
        2. Click "Import File" from the main screen
        3. Navigate to and select this file: {output_path}
        4. In the import dialog:
           - Set the "Type" field to "Basic"
           - Ensure "Field mapping" shows "front" mapped to "Front" and "back" mapped to "Back"
           - Check "Allow HTML in fields"
           - Set the deck to "{self.config.get('default_deck', 'Generated')}"
        5. Click "Import" to add the cards to your Anki collection

        Your cards will now be available in the specified deck.
        """

        return instructions

    def export_with_instructions(
        self, cards: list[FlashCard], output_path: str | Path | None = None
    ) -> dict:
        """
        Export cards and generate import instructions.

        Args:
            cards: List of FlashCard objects to export
            output_path: Path for the output file or None to use default

        Returns:
            Dictionary with export results
        """
        # Export cards
        csv_path = self.export_to_csv(cards, output_path)

        # Generate instructions
        instructions = self.generate_import_instructions(csv_path)

        # Write instructions to file
        instructions_path = csv_path.with_suffix(".txt")
        with open(instructions_path, "w", encoding="utf-8") as file:
            file.write(instructions)

        return {
            "csv_path": str(csv_path),
            "instructions_path": str(instructions_path),
            "card_count": len(cards),
        }

    def _convert_image_refs_to_html(self, text: str) -> str:
        """
        Convert [IMAGE: filename.png] references to HTML <img> tags.

        Args:
            text: Text containing image references

        Returns:
            Text with image references converted to HTML img tags
        """
        # Pattern matches [IMAGE: filename.ext] with optional spaces
        pattern = r'\[IMAGE:\s*([^\]]+)\]'

        def replace_image_ref(match):
            filename = match.group(1).strip()
            # Return HTML img tag that Anki can display
            return f'<img src="{filename}">'

        return re.sub(pattern, replace_image_ref, text)

    def _sanitize_text_with_html(self, text: str) -> str:
        """
        Sanitize text for export while preserving HTML img tags.

        Args:
            text: The text to sanitize

        Returns:
            Sanitized text with HTML preserved
        """
        # First convert image references to HTML
        text = self._convert_image_refs_to_html(text)

        # Don't escape HTML since we want to preserve img tags
        # Just handle CSV escaping (double quotes)
        text = text.replace('"', '""')

        return text

    def export_to_folder(
        self,
        cards: list[dict],
        card_images: list[dict],
        image_storage_dir: Path,
        export_dir: Path,
    ) -> tuple[Path, int]:
        """
        Export flashcards with associated media to a flat folder.

        The folder contains:
        - cards.csv: The flashcard data with HTML img tags
        - Image files copied directly (flat, no subfolder)

        Args:
            cards: List of card dicts with front, back, tags
            card_images: List of CardImage dicts with stored_filename, original_filename
            image_storage_dir: Directory where stored images are located
            export_dir: Directory to write the export into

        Returns:
            Tuple of (export_dir path, number of images copied)
        """
        if not cards:
            logger.warning("No cards to export")
            raise ValueError("Cannot export empty card list")

        # Create the export directory (clear if it already exists)
        if export_dir.exists():
            shutil.rmtree(export_dir)
        export_dir.mkdir(parents=True)

        logger.info(f"Exporting {len(cards)} cards with {len(card_images)} images to {export_dir}")

        # Create a mapping from original filenames to stored filenames
        image_filename_map = {}
        for img in card_images:
            original = img.get("original_filename", "")
            stored = img.get("stored_filename", "")
            if original and stored:
                image_filename_map[original] = stored
                # Also map just the basename (LLM may omit directory prefix)
                basename = Path(original).name
                if basename not in image_filename_map:
                    image_filename_map[basename] = stored
                # Also map the stored filename to itself for direct references
                image_filename_map[stored] = stored

        # Copy images directly into the export folder
        copied_images = set()
        for img in card_images:
            stored_filename = img.get("stored_filename", "")
            if stored_filename:
                src_path = image_storage_dir / stored_filename
                if src_path.exists():
                    dst_path = export_dir / stored_filename
                    shutil.copy2(src_path, dst_path)
                    copied_images.add(stored_filename)
                    logger.debug(f"Copied image: {stored_filename}")

        logger.info(f"Copied {len(copied_images)} images to export folder")

        # Write CSV file
        csv_path = export_dir / "cards.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["front", "back", "tags"])

            for card in cards:
                front = card.get("front", "")
                back = card.get("back", "")
                tags = card.get("tags", [])

                # Convert image references to HTML, mapping to stored filenames
                def replace_with_stored(match):
                    original_name = match.group(1).strip()
                    stored_name = image_filename_map.get(original_name, original_name)
                    return f'<img src="{stored_name}">'

                pattern = r'\[IMAGE:\s*([^\]]+)\]'
                back = re.sub(pattern, replace_with_stored, back)
                front = re.sub(pattern, replace_with_stored, front)

                tag_str = self._format_tags(tags)
                writer.writerow([front, back, tag_str])

        logger.info(f"Successfully exported {len(cards)} cards and {len(copied_images)} images to {export_dir}")
        return export_dir, len(copied_images)
