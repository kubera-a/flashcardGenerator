"""
Markdown Processor Module
------------------------
Handles parsing markdown files and extracting image references.
"""

import logging
import re
import shutil
import urllib.parse
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MarkdownImage:
    """Represents an image reference in markdown."""

    alt_text: str
    relative_path: str
    absolute_path: Path | None = None
    exists: bool = False


@dataclass
class MarkdownDocument:
    """Represents a parsed markdown document with images."""

    content: str
    title: str | None
    images: list[MarkdownImage] = field(default_factory=list)
    source_path: Path | None = None
    base_dir: Path | None = None


class MarkdownProcessor:
    """Processes markdown files and extracts image references."""

    # Regex pattern for markdown image syntax: ![alt](path)
    IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    def __init__(self):
        pass

    def parse_markdown(self, md_path: Path) -> MarkdownDocument:
        """
        Parse a markdown file and extract image references.

        Args:
            md_path: Path to the markdown file

        Returns:
            MarkdownDocument with content and image references
        """
        content = md_path.read_text(encoding="utf-8")
        base_dir = md_path.parent

        # Extract title from first H1
        title = self._extract_title(content)

        # Find all image references
        images = self._extract_images(content, base_dir)

        logger.info(
            f"Parsed markdown: {md_path.name}, title='{title}', "
            f"images={len(images)} ({sum(1 for i in images if i.exists)} exist)"
        )

        return MarkdownDocument(
            content=content,
            title=title,
            images=images,
            source_path=md_path,
            base_dir=base_dir,
        )

    def _extract_title(self, content: str) -> str | None:
        """Extract title from first H1 heading."""
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else None

    def _extract_images(self, content: str, base_dir: Path) -> list[MarkdownImage]:
        """Extract all image references from markdown content."""
        images = []
        seen_paths = set()

        for match in self.IMAGE_PATTERN.finditer(content):
            alt_text = match.group(1)
            relative_path = urllib.parse.unquote(match.group(2))

            # Skip duplicates
            if relative_path in seen_paths:
                continue
            seen_paths.add(relative_path)

            # Resolve absolute path
            absolute_path = base_dir / relative_path
            exists = absolute_path.exists() if absolute_path else False

            images.append(
                MarkdownImage(
                    alt_text=alt_text,
                    relative_path=relative_path,
                    absolute_path=absolute_path,
                    exists=exists,
                )
            )

        return images

    def process_zip(self, zip_path: Path, extract_dir: Path) -> MarkdownDocument:
        """
        Extract and process a markdown ZIP archive.

        Args:
            zip_path: Path to the ZIP file
            extract_dir: Directory to extract contents to

        Returns:
            MarkdownDocument from the primary markdown file

        Raises:
            ValueError: If no markdown file is found in the ZIP
        """
        logger.info(f"Processing ZIP: {zip_path} -> {extract_dir}")

        # Extract ZIP
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Log contents for debugging
            contents = zf.namelist()
            logger.info(f"ZIP contains {len(contents)} files: {contents[:10]}...")
            zf.extractall(extract_dir)

        # Check for nested ZIP files (common in Notion exports) and extract them
        nested_zips = list(extract_dir.rglob("*.zip"))
        for nested_zip in nested_zips:
            logger.info(f"Found nested ZIP: {nested_zip}, extracting...")
            nested_extract_dir = nested_zip.parent / nested_zip.stem
            nested_extract_dir.mkdir(exist_ok=True)
            try:
                with zipfile.ZipFile(nested_zip, "r") as nzf:
                    nzf.extractall(nested_extract_dir)
                logger.info(f"Extracted nested ZIP to: {nested_extract_dir}")
            except zipfile.BadZipFile:
                logger.warning(f"Could not extract nested ZIP: {nested_zip}")

        # Find markdown files - check multiple extensions
        md_files = []
        for pattern in ["*.md", "*.markdown", "*.mdown", "*.mkd"]:
            md_files.extend(extract_dir.rglob(pattern))

        # Log what we found
        all_files = list(extract_dir.rglob("*"))
        logger.info(f"Extracted {len(all_files)} items, found {len(md_files)} markdown files")

        if not md_files:
            # Log all file extensions found to help debug
            extensions = set(f.suffix.lower() for f in all_files if f.is_file())
            logger.error(f"No markdown files found. File extensions in ZIP: {extensions}")
            raise ValueError(
                f"No markdown file found in ZIP. Found extensions: {extensions}. "
                "Please ensure your ZIP contains a .md file."
            )

        # Use the largest markdown file as primary (usually the main content)
        main_md = max(md_files, key=lambda p: p.stat().st_size)
        logger.info(f"Found primary markdown: {main_md}")

        return self.parse_markdown(main_md)

    def get_image_mapping(
        self, doc: MarkdownDocument, session_id: int
    ) -> dict[str, str]:
        """
        Create a mapping from original image paths to session-prefixed filenames.

        Args:
            doc: Parsed markdown document
            session_id: Session ID to prefix filenames with

        Returns:
            Dict mapping relative_path -> stored_filename
        """
        mapping = {}
        for img in doc.images:
            if img.exists and img.absolute_path:
                # Sanitize filename: replace spaces, keep extension
                safe_name = img.absolute_path.name.replace(" ", "_")
                stored_name = f"{session_id}_{safe_name}"
                mapping[img.relative_path] = stored_name
        return mapping

    def copy_images_to_storage(
        self,
        doc: MarkdownDocument,
        image_mapping: dict[str, str],
        storage_dir: Path,
    ) -> list[Path]:
        """
        Copy images to a storage directory with session-prefixed names.

        Args:
            doc: Parsed markdown document
            image_mapping: Mapping from relative paths to stored filenames
            storage_dir: Directory to copy images to

        Returns:
            List of paths to copied images
        """
        storage_dir.mkdir(parents=True, exist_ok=True)
        copied = []

        for img in doc.images:
            if img.exists and img.absolute_path and img.relative_path in image_mapping:
                dest = storage_dir / image_mapping[img.relative_path]
                shutil.copy2(img.absolute_path, dest)
                copied.append(dest)
                logger.debug(f"Copied image: {img.absolute_path} -> {dest}")

        logger.info(f"Copied {len(copied)} images to {storage_dir}")
        return copied
