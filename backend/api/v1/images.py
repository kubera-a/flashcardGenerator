"""Image serving API endpoints."""

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import CardImage
from backend.db.models import Session as DBSession
from config.settings import CARD_IMAGES_DIR

router = APIRouter()

# Use centralized path from config
IMAGE_STORAGE_DIR = CARD_IMAGES_DIR


@router.get("/{session_id}/{filename}")
async def get_image(
    session_id: int,
    filename: str,
    db: Session = Depends(get_db),
):
    """
    Serve an image file from a session's card images.

    The filename should be the stored filename (session_id prefixed).
    """
    # Verify session exists
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check image storage directory
    image_path = IMAGE_STORAGE_DIR / filename
    if not image_path.exists():
        # Also check for the image in the session's extract directory (for preview)
        metadata = session.pdf_metadata or {}
        base_dir = metadata.get("base_dir")

        if base_dir:
            # Try to find the image in the original location
            alt_path = Path(base_dir) / filename
            if alt_path.exists():
                image_path = alt_path
            else:
                # Try without session prefix
                original_name = filename.replace(f"{session_id}_", "")
                alt_path = Path(base_dir) / original_name
                if alt_path.exists():
                    image_path = alt_path

    if not image_path.exists():
        # Fallback: look up CardImage by matching filename patterns
        card_image = db.query(CardImage).filter(
            CardImage.session_id == session_id,
            CardImage.stored_filename == filename,
        ).first()

        if not card_image:
            # Strip {digits}_ prefix and match the base name
            base_match = re.match(r'^\d+_(.+)$', filename)
            if base_match:
                base_name = base_match.group(1)
                card_image = db.query(CardImage).filter(
                    CardImage.session_id == session_id,
                    CardImage.stored_filename.like(f'%_{base_name}'),
                ).first()

        if card_image:
            image_path = IMAGE_STORAGE_DIR / card_image.stored_filename

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    # Determine media type
    suffix = image_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=image_path,
        media_type=media_type,
        filename=filename,
    )


@router.get("/{session_id}/original/{filename:path}")
async def get_original_image(
    session_id: int,
    filename: str,
    db: Session = Depends(get_db),
):
    """
    Serve an image file using its original filename/path from the markdown.

    This endpoint is useful for previewing images during card review,
    where the card references images by their original name.
    """
    # Verify session exists
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    metadata = session.pdf_metadata or {}
    base_dir = metadata.get("base_dir")

    if not base_dir:
        raise HTTPException(status_code=404, detail="Session has no image directory")

    # Look for image in the base directory
    image_path = Path(base_dir) / filename
    if not image_path.exists():
        # Try just the filename in case path is different
        image_path = Path(base_dir) / Path(filename).name
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")

    # Determine media type
    suffix = image_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=image_path,
        media_type=media_type,
        filename=Path(filename).name,
    )
