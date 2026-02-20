"""Export API endpoints."""

import logging
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Card, CardImage, CardStatus
from backend.db.models import Session as DBSession
from backend.db.schemas import (
    AnkiConnectExportRequest,
    AnkiConnectExportResponse,
    AnkiConnectStatusResponse,
    ExportRequest,
    ExportResponse,
    ExportWithMediaResponse,
)
from config.settings import (
    ANKI_CONNECT_URL,
    CARD_IMAGES_DIR,
    EXPORTS_DIR,
    sanitize_filename,
)
from modules.anki_connect import AnkiConnectClient, AnkiConnectError
from modules.anki_integration import AnkiExporter
from modules.card_generation import FlashCard

logger = logging.getLogger(__name__)

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

    # Get all non-rejected cards
    export_cards = (
        db.query(Card)
        .filter(
            Card.session_id == session_id,
            Card.status != CardStatus.REJECTED.value,
        )
        .all()
    )

    if not export_cards:
        raise HTTPException(status_code=400, detail="No cards to export")

    # Convert to FlashCard objects
    flashcards = [
        FlashCard(
            front=card.front,
            back=card.back,
            tags=card.tags if request.include_tags else [],
        )
        for card in export_cards
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
    Export approved cards with media to a folder on disk.

    Creates data/exports/<deck_tag>/ containing:
    - cards.csv with HTML img tags
    - Image files copied flat (no subfolder)
    """
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all non-rejected cards
    export_cards = (
        db.query(Card)
        .filter(
            Card.session_id == session_id,
            Card.status != CardStatus.REJECTED.value,
        )
        .all()
    )

    if not export_cards:
        raise HTTPException(status_code=400, detail="No cards to export")

    # Get card IDs
    card_ids = [card.id for card in export_cards]

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
        for card in export_cards
    ]

    images_data = [
        {
            "original_filename": img.original_filename,
            "stored_filename": img.stored_filename,
        }
        for img in card_images
    ]

    # Use deck_tag as folder name
    deck_tag = sanitize_filename(session.display_name or session.filename)
    export_dir = EXPORTS_DIR / deck_tag

    # Export using AnkiExporter
    exporter = AnkiExporter(
        config={"default_deck": request.deck_name or "Generated::Flashcards", "default_tags": []}
    )

    _, image_count = exporter.export_to_folder(
        cards=cards_data,
        card_images=images_data,
        image_storage_dir=IMAGE_STORAGE_DIR,
        export_dir=export_dir,
    )

    return ExportWithMediaResponse(
        folder_name=deck_tag,
        card_count=len(export_cards),
        image_count=image_count,
    )


# --- AnkiConnect endpoints ---


@router.get("/anki-connect/status", response_model=AnkiConnectStatusResponse)
async def anki_connect_status():
    """Check if AnkiConnect is reachable and list available decks."""
    client = AnkiConnectClient(url=ANKI_CONNECT_URL)
    available, version = await client.is_available()

    decks = []
    if available:
        try:
            decks = await client.get_decks()
        except AnkiConnectError:
            pass

    return AnkiConnectStatusResponse(
        available=available,
        version=version,
        decks=decks,
    )


@router.post(
    "/session/{session_id}/anki-connect",
    response_model=AnkiConnectExportResponse,
)
async def export_to_anki_connect(
    session_id: int,
    request: AnkiConnectExportRequest = AnkiConnectExportRequest(),
    db: Session = Depends(get_db),
):
    """Export cards directly to Anki via AnkiConnect."""
    client = AnkiConnectClient(url=ANKI_CONNECT_URL)

    # Check AnkiConnect is reachable
    available, _ = await client.is_available()
    if not available:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to AnkiConnect. Is Anki running with AnkiConnect installed (addon #2055492159)?",
        )

    # Get session
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Determine deck name
    deck_name = request.deck_name or (
        session.display_name or Path(session.filename).stem
    ).replace(" ", "_")

    # Get all non-rejected cards
    export_cards = (
        db.query(Card)
        .filter(
            Card.session_id == session_id,
            Card.status != CardStatus.REJECTED.value,
        )
        .all()
    )

    if not export_cards:
        raise HTTPException(status_code=400, detail="No cards to export")

    # Get all images for these cards
    card_ids = [card.id for card in export_cards]
    card_images = (
        db.query(CardImage).filter(CardImage.card_id.in_(card_ids)).all()
    )

    # Build image filename map (original -> stored, same logic as AnkiExporter)
    image_filename_map = {}
    for img in card_images:
        original = img.original_filename or ""
        stored = img.stored_filename or ""
        if original and stored:
            image_filename_map[original] = stored
            basename = Path(original).name
            if basename not in image_filename_map:
                image_filename_map[basename] = stored
            image_filename_map[stored] = stored

    # 1. Create deck
    errors = []
    try:
        await client.create_deck(deck_name)
    except AnkiConnectError as e:
        raise HTTPException(status_code=502, detail=f"Failed to create deck: {e}")

    # 2. Store media files
    images_sent = 0
    for img in card_images:
        stored = img.stored_filename
        if not stored:
            continue
        src_path = IMAGE_STORAGE_DIR / stored
        if not src_path.exists():
            errors.append(f"Image file not found: {stored}")
            continue
        try:
            await client.store_media_from_path(stored, src_path)
            images_sent += 1
        except AnkiConnectError as e:
            errors.append(f"Failed to store image {stored}: {e}")

    # 3. Build and send notes
    image_pattern = re.compile(r'\[IMAGE:\s*([^\]]+)\]')

    def replace_image_refs(text: str) -> str:
        def _replace(match):
            original_name = match.group(1).strip()
            stored_name = image_filename_map.get(original_name, original_name)
            return f'<img src="{stored_name}">'
        return image_pattern.sub(_replace, text)

    notes = []
    for card in export_cards:
        front = replace_image_refs(card.front)
        back = replace_image_refs(card.back)
        tags = card.tags if request.include_tags else []

        notes.append({
            "deckName": deck_name,
            "modelName": "Basic",
            "fields": {"Front": front, "Back": back},
            "tags": tags,
            "options": {"allowDuplicate": False},
        })

    try:
        results = await client.add_notes(notes)
    except AnkiConnectError as e:
        raise HTTPException(status_code=502, detail=f"Failed to add notes: {e}")

    cards_sent = sum(1 for r in results if r is not None)
    cards_failed = sum(1 for r in results if r is None)
    if cards_failed > 0:
        errors.append(
            f"{cards_failed} card(s) failed to add (likely duplicates)"
        )

    logger.info(
        f"AnkiConnect export: {cards_sent} sent, {cards_failed} failed, "
        f"{images_sent} images, deck={deck_name}"
    )

    return AnkiConnectExportResponse(
        success=cards_failed == 0 and len(errors) == 0,
        cards_sent=cards_sent,
        cards_failed=cards_failed,
        images_sent=images_sent,
        deck_name=deck_name,
        errors=errors,
    )
