"""Extract embedded images from PDF files using PyMuPDF."""

import logging
from dataclasses import dataclass
from pathlib import Path

import fitz

logger = logging.getLogger(__name__)


@dataclass
class PDFImage:
    """An image extracted from a PDF page."""

    page_num: int  # 0-based page index
    img_index: int  # Index within the page
    filename: str  # e.g. "page3_img0.png"
    image_bytes: bytes
    ext: str  # "png", "jpeg", etc.
    width: int
    height: int


def extract_images_from_pdf(
    pdf_path: str | Path,
    page_indices: list[int] | None = None,
    min_size: int = 50,
) -> list[PDFImage]:
    """
    Extract embedded images from a PDF file.

    Args:
        pdf_path: Path to the PDF file.
        page_indices: 0-based page indices to extract from. None = all pages.
        min_size: Minimum width/height in pixels. Images smaller than this
                  on both dimensions are skipped (decorative icons/bullets).

    Returns:
        List of PDFImage objects.
    """
    images: list[PDFImage] = []
    doc = fitz.open(str(pdf_path))

    try:
        pages_to_process = page_indices if page_indices is not None else range(len(doc))

        for page_num in pages_to_process:
            if page_num >= len(doc):
                continue

            page = doc[page_num]
            page_images = page.get_images(full=True)
            img_index = 0

            for img_info in page_images:
                xref = img_info[0]
                try:
                    extracted = doc.extract_image(xref)
                except Exception:
                    logger.debug(f"Could not extract image xref={xref} on page {page_num}")
                    continue

                if not extracted or not extracted.get("image"):
                    continue

                width = extracted.get("width", 0)
                height = extracted.get("height", 0)

                # Skip tiny images (decorative icons, bullets, etc.)
                if width < min_size and height < min_size:
                    continue

                ext = extracted.get("ext", "png")
                # Normalize jpeg extension
                if ext == "jpeg":
                    ext = "jpg"

                # 1-based page number for human readability
                filename = f"page{page_num + 1}_img{img_index}.{ext}"

                images.append(
                    PDFImage(
                        page_num=page_num,
                        img_index=img_index,
                        filename=filename,
                        image_bytes=extracted["image"],
                        ext=ext,
                        width=width,
                        height=height,
                    )
                )
                img_index += 1

        logger.info(f"Extracted {len(images)} images from {pdf_path}")
    finally:
        doc.close()

    return images


def save_pdf_images(
    images: list[PDFImage],
    storage_dir: Path,
    deck_prefix: str,
) -> dict[str, str]:
    """
    Save extracted PDF images to the card images storage directory.

    Args:
        images: List of PDFImage objects to save.
        storage_dir: Directory to save images into (CARD_IMAGES_DIR).
        deck_prefix: Deck name prefix for stored filenames.

    Returns:
        Mapping of {original_filename: stored_filename}.
    """
    storage_dir.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}

    for img in images:
        stored_name = f"{deck_prefix}_{img.filename}"
        out_path = storage_dir / stored_name
        out_path.write_bytes(img.image_bytes)
        mapping[img.filename] = stored_name
        logger.debug(f"Saved PDF image: {stored_name} ({img.width}x{img.height})")

    logger.info(f"Saved {len(mapping)} PDF images with prefix '{deck_prefix}'")
    return mapping


def get_images_for_pages(
    all_images: list[PDFImage],
    page_indices: list[int],
) -> list[PDFImage]:
    """
    Filter image list to only those on the given pages.

    Args:
        all_images: Full list of extracted images.
        page_indices: 0-based page indices to filter by.

    Returns:
        Filtered list of PDFImage objects.
    """
    page_set = set(page_indices)
    return [img for img in all_images if img.page_num in page_set]
