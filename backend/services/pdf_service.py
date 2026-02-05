"""Service for PDF processing and preview."""

import base64
import io
import logging
from pathlib import Path

from pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


def get_pdf_info(file_path: str | Path) -> dict:
    """
    Get information about a PDF file.

    Args:
        file_path: Path to the PDF file

    Returns:
        Dictionary with PDF metadata including page count
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    reader = PdfReader(str(file_path))
    num_pages = len(reader.pages)

    # Extract metadata
    metadata = reader.metadata or {}

    # Extract chapters/outline
    chapters = extract_chapters(reader)

    return {
        "page_count": num_pages,
        "title": metadata.get("/Title", ""),
        "author": metadata.get("/Author", ""),
        "subject": metadata.get("/Subject", ""),
        "file_size": file_path.stat().st_size,
        "chapters": chapters,
    }


def extract_chapters(reader: PdfReader) -> list[dict]:
    """
    Extract chapter/section information from PDF outline (bookmarks).

    Args:
        reader: PyPDF2 PdfReader instance

    Returns:
        List of chapter dictionaries with title, start_page, and end_page
    """
    chapters = []

    try:
        outline = reader.outline
        if not outline:
            return chapters

        # Flatten the outline and extract page numbers
        flat_items = _flatten_outline(outline, reader)

        # Calculate end pages based on next chapter start
        for i, item in enumerate(flat_items):
            chapter = {
                "title": item["title"],
                "start_page": item["page"],
                "level": item["level"],
            }

            # End page is the page before the next chapter starts, or last page
            if i + 1 < len(flat_items):
                chapter["end_page"] = flat_items[i + 1]["page"] - 1
            else:
                chapter["end_page"] = len(reader.pages) - 1

            # Ensure end_page is at least start_page
            if chapter["end_page"] < chapter["start_page"]:
                chapter["end_page"] = chapter["start_page"]

            chapters.append(chapter)

    except Exception as e:
        logger.warning(f"Failed to extract chapters: {e}")

    return chapters


def _flatten_outline(outline: list, reader: PdfReader, level: int = 0) -> list[dict]:
    """
    Flatten nested PDF outline into a list of items with page numbers.

    Args:
        outline: PDF outline (can be nested)
        reader: PyPDF2 PdfReader instance
        level: Current nesting level

    Returns:
        Flat list of outline items with title, page, and level
    """
    items = []

    for item in outline:
        if isinstance(item, list):
            # Nested outline - recurse
            items.extend(_flatten_outline(item, reader, level + 1))
        else:
            try:
                # Get destination page number
                if hasattr(item, "page") and item.page is not None:
                    page_num = reader.get_destination_page_number(item)
                    items.append({
                        "title": item.title,
                        "page": page_num,
                        "level": level,
                    })
            except Exception as e:
                logger.debug(f"Could not resolve outline item: {e}")
                continue

    return items


def get_pages_for_chapters(
    file_path: str | Path,
    chapter_indices: list[int],
) -> list[int]:
    """
    Get all page indices for the selected chapters.

    Args:
        file_path: Path to the PDF file
        chapter_indices: List of chapter indices to include

    Returns:
        List of 0-based page indices covering all selected chapters
    """
    pdf_info = get_pdf_info(file_path)
    chapters = pdf_info.get("chapters", [])

    if not chapters:
        raise ValueError("PDF has no chapter information")

    page_indices = set()
    for idx in chapter_indices:
        if 0 <= idx < len(chapters):
            chapter = chapters[idx]
            for page in range(chapter["start_page"], chapter["end_page"] + 1):
                page_indices.add(page)

    return sorted(page_indices)


def generate_page_thumbnails(
    file_path: str | Path,
    page_indices: list[int] | None = None,
    thumbnail_width: int = 200,
) -> list[dict]:
    """
    Generate thumbnail images for PDF pages.

    Args:
        file_path: Path to the PDF file
        page_indices: List of 0-based page indices to generate thumbnails for.
                     If None, generates for all pages.
        thumbnail_width: Width of thumbnails in pixels

    Returns:
        List of dictionaries with page index and base64-encoded thumbnail
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    # Get page count first
    reader = PdfReader(str(file_path))
    num_pages = len(reader.pages)

    # Determine which pages to process
    if page_indices is None:
        page_indices = list(range(num_pages))
    else:
        # Validate page indices
        page_indices = [i for i in page_indices if 0 <= i < num_pages]

    thumbnails = []

    try:
        # Convert pages to images
        # Note: first_page and last_page are 1-indexed in pdf2image
        for page_idx in page_indices:
            images = convert_from_path(
                str(file_path),
                first_page=page_idx + 1,
                last_page=page_idx + 1,
                size=(thumbnail_width, None),
            )

            if images:
                # Convert to base64
                img_buffer = io.BytesIO()
                images[0].save(img_buffer, format="PNG")
                img_base64 = base64.b64encode(img_buffer.getvalue()).decode("utf-8")

                thumbnails.append({
                    "page_index": page_idx,
                    "thumbnail": f"data:image/png;base64,{img_base64}",
                })

    except Exception as e:
        logger.warning(f"Failed to generate thumbnails: {e}")
        # Return empty thumbnails but don't fail completely
        for page_idx in page_indices:
            thumbnails.append({
                "page_index": page_idx,
                "thumbnail": None,
            })

    return thumbnails


def extract_pages(
    file_path: str | Path,
    page_indices: list[int],
    output_path: str | Path | None = None,
) -> bytes | str:
    """
    Extract specific pages from a PDF file.

    Args:
        file_path: Path to the source PDF file
        page_indices: List of 0-based page indices to extract
        output_path: Optional path to save the extracted pages.
                    If None, returns the PDF as bytes.

    Returns:
        Path to the output file if output_path is provided,
        otherwise the PDF content as bytes.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    reader = PdfReader(str(file_path))
    writer = PdfWriter()

    # Add selected pages
    for page_idx in sorted(page_indices):
        if 0 <= page_idx < len(reader.pages):
            writer.add_page(reader.pages[page_idx])

    if output_path:
        output_path = Path(output_path)
        with open(output_path, "wb") as f:
            writer.write(f)
        return str(output_path)
    else:
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()


def encode_pdf_to_base64(file_path: str | Path) -> str:
    """
    Encode a PDF file to base64.

    Args:
        file_path: Path to the PDF file

    Returns:
        Base64-encoded string of the PDF content
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    with open(file_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def encode_pdf_pages_to_base64(
    file_path: str | Path,
    page_indices: list[int],
) -> str:
    """
    Extract specific pages from a PDF and encode to base64.

    Args:
        file_path: Path to the PDF file
        page_indices: List of 0-based page indices to include

    Returns:
        Base64-encoded string of the extracted pages
    """
    pdf_bytes = extract_pages(file_path, page_indices, output_path=None)
    return base64.standard_b64encode(pdf_bytes).decode("utf-8")
