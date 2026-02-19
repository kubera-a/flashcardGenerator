"""Export API endpoints."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Card, CardImage, CardStatus
from backend.db.models import Session as DBSession
from backend.db.schemas import ExportRequest, ExportResponse, ExportWithMediaResponse
from config.settings import CARD_IMAGES_DIR, EXPORTS_DIR
from modules.anki_integration import AnkiExporter
from modules.card_generation import FlashCard

router = APIRouter()

# Use centralized path from config
IMAGE_STORAGE_DIR = CARD_IMAGES_DIR


@router.post("/session/{session_id}", response_model=ExportResponse)
async def export_session_cards(
    session_id: int,
    request: ExportRequest = ExportRequest(),
    db: Session = Depends(get_db),
):
    """Export approved cards from a session to Anki CSV format."""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get approved cards (and edited cards which are also approved)
    approved_cards = (
        db.query(Card)
        .filter(
            Card.session_id == session_id,
            Card.status.in_([CardStatus.APPROVED.value, CardStatus.EDITED.value]),
        )
        .all()
    )

    if not approved_cards:
        raise HTTPException(status_code=400, detail="No approved cards to export")

    # Convert to FlashCard objects
    flashcards = [
        FlashCard(
            front=card.front,
            back=card.back,
            tags=card.tags if request.include_tags else [],
        )
        for card in approved_cards
    ]

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = Path(session.filename).stem
    filename = f"{base_name}_{timestamp}.csv"
    output_path = EXPORTS_DIR / filename

    # Export using AnkiExporter
    exporter = AnkiExporter(
        config={"default_deck": request.deck_name or "Generated::Flashcards", "default_tags": []}
    )
    exporter.export_to_csv(flashcards, str(output_path))

    return ExportResponse(
        filename=filename,
        card_count=len(flashcards),
        download_url=f"/exports/{filename}",
    )


@router.get("/download/{filename}")
async def download_export(filename: str):
    """Download an exported CSV file."""
    file_path = EXPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="text/csv",
    )


@router.get("/list")
async def list_exports():
    """List all available export files."""
    exports = []
    for file_path in EXPORTS_DIR.glob("*.csv"):
        exports.append({
            "filename": file_path.name,
            "size": file_path.stat().st_size,
            "created_at": datetime.fromtimestamp(file_path.stat().st_ctime),
            "download_url": f"/exports/{file_path.name}",
        })

    return {"exports": sorted(exports, key=lambda x: x["created_at"], reverse=True)}


@router.post("/session/{session_id}/with-media", response_model=ExportWithMediaResponse)
async def export_session_with_media(
    session_id: int,
    request: ExportRequest = ExportRequest(),
    db: Session = Depends(get_db),
):
    """
    Export approved cards with media as a ZIP file.

    For markdown sessions with images, this exports:
    - cards.csv with HTML img tags
    - media/ folder containing all referenced images

    For PDF sessions without images, falls back to regular CSV export wrapped in a ZIP.
    """
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get approved cards (and edited cards which are also approved)
    approved_cards = (
        db.query(Card)
        .filter(
            Card.session_id == session_id,
            Card.status.in_([CardStatus.APPROVED.value, CardStatus.EDITED.value]),
        )
        .all()
    )

    if not approved_cards:
        raise HTTPException(status_code=400, detail="No approved cards to export")

    # Get card IDs
    card_ids = [card.id for card in approved_cards]

    # Get all images for these cards
    card_images = (
        db.query(CardImage)
        .filter(CardImage.card_id.in_(card_ids))
        .all()
    )

    # Convert to dicts for the exporter
    cards_data = [
        {
            "front": card.front,
            "back": card.back,
            "tags": card.tags if request.include_tags else [],
        }
        for card in approved_cards
    ]

    images_data = [
        {
            "original_filename": img.original_filename,
            "stored_filename": img.stored_filename,
        }
        for img in card_images
    ]

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = Path(session.filename).stem
    filename = f"{base_name}_{timestamp}_with_media.zip"
    output_path = EXPORTS_DIR / filename

    # Export using AnkiExporter
    exporter = AnkiExporter(
        config={"default_deck": request.deck_name or "Generated::Flashcards", "default_tags": []}
    )

    exporter.export_to_zip_with_media(
        cards=cards_data,
        card_images=images_data,
        image_storage_dir=IMAGE_STORAGE_DIR,
        output_path=output_path,
        deck_name=request.deck_name,
    )

    return ExportWithMediaResponse(
        filename=filename,
        card_count=len(approved_cards),
        image_count=len(card_images),
        download_url=f"/api/v1/export/download/{filename}",
    )


@router.get("/download-zip/{filename}")
async def download_zip_export(filename: str):
    """Download an exported ZIP file."""
    file_path = EXPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/zip",
    )
