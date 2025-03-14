"""
PDF Processing Module
--------------------
Handles extraction and preprocessing of text from PDF documents.
"""

import logging
from pathlib import Path

import PyPDF2
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams

from config.settings import CHUNK_SIZE

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Processes PDF documents for content extraction and preparation."""

    def __init__(self, chunk_size: int = CHUNK_SIZE):
        """
        Initialize the PDF processor.

        Args:
            chunk_size: Maximum size of content chunks for processing
        """
        self.chunk_size = chunk_size

    def extract_text_pdfminer(self, pdf_path: Path) -> str:
        """
        Extract text using PDFMiner for better text extraction quality.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text as a string
        """
        try:
            laparams = LAParams(
                line_margin=0.5,
                char_margin=2.0,
                word_margin=0.1,
            )
            return extract_text(str(pdf_path), laparams=laparams)
        except Exception as e:
            logger.error(f"Error extracting text with PDFMiner: {e}")
            return ""

    def extract_text_pypdf(self, pdf_path: Path) -> str:
        """
        Extract text using PyPDF2 as a fallback method.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text as a string
        """
        try:
            text = ""
            with open(pdf_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text with PyPDF2: {e}")
            return ""

    def extract_metadata(self, pdf_path: Path) -> dict:
        """
        Extract metadata from the PDF document.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary containing metadata
        """
        metadata = {
            "title": None,
            "author": None,
            "subject": None,
            "creation_date": None,
            "page_count": 0,
        }

        try:
            with open(pdf_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                info = reader.metadata
                if info:
                    metadata["title"] = info.get("/Title", None)
                    metadata["author"] = info.get("/Author", None)
                    metadata["subject"] = info.get("/Subject", None)
                    metadata["creation_date"] = info.get("/CreationDate", None)
                metadata["page_count"] = len(reader.pages)
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")

        return metadata

    def clean_text(self, text: str) -> str:
        """
        Clean the extracted text by removing artifacts and standardizing formatting.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove page numbers (simple heuristic)
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            # Skip lines that are just numbers (likely page numbers)
            if line.strip().isdigit():
                continue

            # Skip header/footer candidates (short lines at the top/bottom of pages)
            if len(line.strip()) < 10 and line.strip():
                continue

            cleaned_lines.append(line)

        cleaned_text = "\n".join(cleaned_lines)

        # Remove excessive whitespace
        cleaned_text = " ".join(cleaned_text.split())

        # Fix common PDF extraction issues
        cleaned_text = cleaned_text.replace("- ", "")  # Remove hyphenation

        return cleaned_text

    def segment_content(self, text: str) -> list[str]:
        """
        Divide content into logical chunks for processing.

        Args:
            text: Cleaned text content

        Returns:
            List of content chunks
        """
        # Simple chunking strategy based on fixed size
        # A more sophisticated approach would consider semantic boundaries

        if not text:
            return []

        chunks = []
        current_chunk = ""

        paragraphs = text.split("\n\n")

        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= self.chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def process_pdf(self, pdf_path: Path) -> tuple[list[str], dict]:
        """
        Process a PDF document fully and prepare it for content analysis.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Tuple of (content_chunks, metadata)
        """
        logger.info(f"Processing PDF: {pdf_path}")

        # First try with PDFMiner for better quality
        text = self.extract_text_pdfminer(pdf_path)

        # Fall back to PyPDF2 if needed
        if not text:
            logger.info("Falling back to PyPDF2 for text extraction")
            text = self.extract_text_pypdf(pdf_path)

        # Extract metadata
        metadata = self.extract_metadata(pdf_path)

        # Clean the text
        cleaned_text = self.clean_text(text)

        # Segment into chunks
        chunks = self.segment_content(cleaned_text)

        logger.info(f"Extracted {len(chunks)} content chunks from PDF")

        return chunks, metadata
