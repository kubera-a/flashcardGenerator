"""
Unit Tests
---------
Tests for the Anki Flashcard Generator.
"""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from modules.anki_integration import AnkiExporter
from modules.card_generation import FlashCard
from modules.pdf_processor import PDFProcessor


class TestPDFProcessor:
    """Tests for the PDF processor module."""

    @patch("PyPDF2.PdfReader")
    def test_extract_metadata(self, mock_reader):
        # Setup mock
        mock_instance = MagicMock()
        mock_instance.metadata = {
            "/Title": "Test Document",
            "/Author": "Test Author",
            "/Subject": "Test Subject",
            "/CreationDate": "D:20220101000000",
        }
        mock_instance.pages = [MagicMock(), MagicMock()]  # Mock two pages
        mock_reader.return_value = mock_instance

        # Create test file path
        test_path = Path("test_document.pdf")

        # Mock open function
        with patch("builtins.open", mock_open()) as mock_file:
            processor = PDFProcessor()
            metadata = processor.extract_metadata(test_path)

            # Verify results
            assert metadata["title"] == "Test Document"
            assert metadata["author"] == "Test Author"
            assert metadata["subject"] == "Test Subject"
            assert metadata["page_count"] == 2

    def test_clean_text(self):
        # Test input text with various artifacts
        test_text = """1
        
        This is a header
        
        This is the main content of the document.
        It spans multiple lines and has some formatting issues like hy-
        phenation.
        
        2
        
        Another header
        
        The document continues here with more content.
        """

        processor = PDFProcessor()
        cleaned_text = processor.clean_text(test_text)

        # Check that page numbers are removed
        assert "1" not in cleaned_text
        assert "2" not in cleaned_text

        # Check that hyphenation is fixed
        assert "hyphenation" in cleaned_text

        # Check that short headers are removed
        assert "This is a header" not in cleaned_text
        assert "Another header" not in cleaned_text

        # Check that main content is preserved
        assert "This is the main content of the document." in cleaned_text
        assert "The document continues here with more content." in cleaned_text

    def test_segment_content(self):
        # Create a long piece of text
        paragraphs = ["Paragraph " + str(i) * 100 for i in range(1, 11)]
        long_text = "\n\n".join(paragraphs)

        # Set a chunk size that should split the text
        processor = PDFProcessor(chunk_size=500)
        chunks = processor.segment_content(long_text)

        # Verify that the text was split into multiple chunks
        assert len(chunks) > 1

        # Verify that no chunk exceeds the maximum size
        for chunk in chunks:
            assert len(chunk) <= 500


class TestFlashCard:
    """Tests for the FlashCard class."""

    def test_to_dict(self):
        # Create a test card
        card = FlashCard(
            front="What is Python?",
            back="Python is a programming language.",
            tags=["python", "programming"],
        )

        # Convert to dictionary
        card_dict = card.to_dict()

        # Verify the dictionary
        assert card_dict["front"] == "What is Python?"
        assert card_dict["back"] == "Python is a programming language."
        assert "python" in card_dict["tags"]
        assert "programming" in card_dict["tags"]

    def test_from_dict(self):
        # Create a test dictionary
        card_dict = {
            "front": "What is TDD?",
            "back": "Test-Driven Development is a software development approach.",
            "tags": ["tdd", "software engineering"],
        }

        # Create card from dictionary
        card = FlashCard.from_dict(card_dict)

        # Verify the card
        assert card.front == "What is TDD?"
        assert (
            card.back == "Test-Driven Development is a software development approach."
        )
        assert "tdd" in card.tags
        assert "software engineering" in card.tags


class TestAnkiExporter:
    """Tests for the Anki exporter module."""

    def test_sanitize_text(self):
        # Create an exporter
        exporter = AnkiExporter()

        # Test text with special characters
        test_text = 'Text with "quotes" and <html> tags'
        sanitized = exporter._sanitize_text(test_text)
