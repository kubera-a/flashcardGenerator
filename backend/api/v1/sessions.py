"""Session API endpoints."""

import shutil
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Session as DBSession
from backend.db.models import SessionStatus, SourceType
from backend.db.schemas import (
    ContinueGenerationRequest,
    MarkdownPreviewResponse,
    PDFChapter,
    PDFPageThumbnail,
    PDFPreviewResponse,
    SessionResponse,
    SessionStatusResponse,
    SessionWithStats,
    StartGenerationRequest,
)
from backend.services.pdf_service import (
    generate_page_thumbnails,
    get_pages_for_chapters,
    get_pdf_info,
)
from backend.services.prompt_evolution_service import (
    analyze_session_and_generate_suggestion,
)
from backend.services.session_service import (
    continue_generation,
    create_session,
    finalize_session,
    get_session_stats,
    process_markdown_and_generate_cards,
    process_pdf_and_generate_cards,
)
from config.settings import CARD_IMAGES_DIR, EXPORTS_DIR, EXTRACTIONS_DIR, UPLOADS_DIR

router = APIRouter()

# Use centralized paths from config
UPLOAD_DIR = UPLOADS_DIR
MARKDOWN_UPLOAD_DIR = EXTRACTIONS_DIR


@router.post("/", response_model=SessionResponse)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    llm_provider: str = "openai",
    db: Session = Depends(get_db),
):
    """Upload a PDF and start card generation (legacy endpoint)."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Save uploaded file
    file_path = UPLOAD_DIR / f"{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create session
    session = create_session(
        db=db,
        filename=file.filename,
        file_path=str(file_path),
        llm_provider=llm_provider,
    )

    # Start background processing
    background_tasks.add_task(
        process_pdf_and_generate_cards,
        session_id=session.id,
    )

    return session


@router.post("/upload-preview", response_model=PDFPreviewResponse)
async def upload_pdf_preview(
    file: UploadFile = File(...),
    llm_provider: str = "openai",
    generate_thumbnails: bool = Query(True, description="Whether to generate page thumbnails"),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF and get a preview with page thumbnails.
    Does NOT start card generation - use the start-generation endpoint for that.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Save uploaded file
    file_path = UPLOAD_DIR / f"{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create session in pending state
    session = create_session(
        db=db,
        filename=file.filename,
        file_path=str(file_path),
        llm_provider=llm_provider,
    )

    # Update session to pending state (not processing yet)
    session.status = "pending"
    db.commit()

    # Get PDF info
    try:
        pdf_info = get_pdf_info(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read PDF: {str(e)}")

    # Generate thumbnails if requested
    thumbnails = []
    if generate_thumbnails:
        try:
            thumbnail_data = generate_page_thumbnails(file_path)
            thumbnails = [
                PDFPageThumbnail(page_index=t["page_index"], thumbnail=t["thumbnail"])
                for t in thumbnail_data
            ]
        except Exception as e:
            # Log but don't fail - thumbnails are optional
            import logging
            logging.warning(f"Failed to generate thumbnails: {e}")

    # Extract chapter information
    chapters = [
        PDFChapter(
            title=ch["title"],
            start_page=ch["start_page"],
            end_page=ch["end_page"],
            level=ch.get("level", 0),
        )
        for ch in pdf_info.get("chapters", [])
    ]

    return PDFPreviewResponse(
        session_id=session.id,
        filename=file.filename,
        page_count=pdf_info["page_count"],
        file_size=pdf_info["file_size"],
        title=pdf_info.get("title"),
        author=pdf_info.get("author"),
        thumbnails=thumbnails,
        chapters=chapters,
    )


@router.post("/upload-markdown", response_model=MarkdownPreviewResponse)
async def upload_markdown_preview(
    file: UploadFile = File(...),
    llm_provider: str = "anthropic",  # Default to anthropic for image support
    db: Session = Depends(get_db),
):
    """
    Upload a markdown folder (as ZIP) and get a preview.

    The ZIP should contain:
    - A markdown (.md) file
    - An accompanying images folder

    Note: Markdown with images requires Anthropic (Claude) provider for multimodal support.
    """
    import uuid

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are allowed for markdown upload")

    if llm_provider != "anthropic":
        raise HTTPException(
            status_code=400,
            detail="Markdown with images requires Anthropic (Claude) provider for multimodal support"
        )

    # Create unique directory for this upload
    session_uuid = str(uuid.uuid4())
    extract_dir = MARKDOWN_UPLOAD_DIR / session_uuid
    extract_dir.mkdir(parents=True, exist_ok=True)

    # Save ZIP file
    zip_path = extract_dir / file.filename
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Process markdown
    from modules.markdown_processor import MarkdownProcessor

    processor = MarkdownProcessor()
    try:
        doc = processor.process_zip(zip_path, extract_dir)
    except ValueError as e:
        # Clean up on failure
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Failed to process ZIP: {str(e)}")

    # Create session
    session = create_session(
        db=db,
        filename=file.filename,
        file_path=str(doc.source_path),
        llm_provider=llm_provider,
        source_type=SourceType.MARKDOWN.value,
    )

    # Store markdown metadata
    existing_images = [img.relative_path for img in doc.images if img.exists]
    session.pdf_metadata = {
        "source_type": "markdown",
        "title": doc.title,
        "image_count": len(existing_images),
        "images": existing_images,
        "extract_dir": str(extract_dir),
        "base_dir": str(doc.base_dir),
    }
    session.status = "pending"
    db.commit()
    db.refresh(session)

    return MarkdownPreviewResponse(
        session_id=session.id,
        filename=file.filename,
        title=doc.title,
        image_count=len(existing_images),
        content_preview=doc.content[:500] + ("..." if len(doc.content) > 500 else ""),
        images=existing_images,
    )


@router.post("/{session_id}/start-generation", response_model=SessionResponse)
async def start_generation(
    session_id: int,
    request: StartGenerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start card generation for a session with optional page or chapter selection."""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in ["pending", "failed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start generation for session in {session.status} state"
        )

    # Update session status
    session.status = SessionStatus.PROCESSING.value

    # Check if this is a markdown session
    is_markdown = session.source_type == SourceType.MARKDOWN.value

    if is_markdown:
        # Markdown sessions don't use page selection
        db.commit()
        db.refresh(session)

        # Start markdown processing
        background_tasks.add_task(
            process_markdown_and_generate_cards,
            session_id=session.id,
        )
    else:
        # PDF processing with page selection
        selected_pages = request.page_indices

        # If chapters are specified, expand them to page indices
        if request.chapter_indices is not None:
            try:
                selected_pages = get_pages_for_chapters(
                    session.file_path,
                    request.chapter_indices,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        # Store selection in pdf_metadata
        session.pdf_metadata = session.pdf_metadata or {}
        if selected_pages is not None:
            session.pdf_metadata["selected_pages"] = selected_pages
        if request.chapter_indices is not None:
            session.pdf_metadata["selected_chapters"] = request.chapter_indices
        session.pdf_metadata["use_native_pdf"] = request.use_native_pdf

        db.commit()
        db.refresh(session)

        # Start PDF processing
        background_tasks.add_task(
            process_pdf_and_generate_cards,
            session_id=session.id,
        )

    return session


@router.post("/{session_id}/continue-generation", response_model=SessionResponse)
async def continue_generation_endpoint(
    session_id: int,
    request: ContinueGenerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Continue generating cards for a session, avoiding duplicates.

    Use this after reviewing cards to generate additional cards for missed concepts.
    """
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in ["ready", "pending"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot continue generation for session in {session.status} state"
        )

    # Update session status
    session.status = "processing"
    db.commit()
    db.refresh(session)

    # Start background processing
    background_tasks.add_task(
        continue_generation,
        session_id=session.id,
        focus_areas=request.focus_areas,
        page_indices=request.page_indices,
    )

    return session


@router.get("/{session_id}/thumbnails", response_model=list[PDFPageThumbnail])
async def get_session_thumbnails(
    session_id: int,
    page_indices: str | None = Query(None, description="Comma-separated page indices (0-based)"),
    db: Session = Depends(get_db),
):
    """Get page thumbnails for a session's PDF."""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    file_path = Path(session.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")

    # Parse page indices
    indices = None
    if page_indices:
        try:
            indices = [int(i.strip()) for i in page_indices.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid page indices format")

    try:
        thumbnail_data = generate_page_thumbnails(file_path, page_indices=indices)
        return [
            PDFPageThumbnail(page_index=t["page_index"], thumbnail=t["thumbnail"])
            for t in thumbnail_data
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate thumbnails: {str(e)}")


@router.get("/", response_model=list[SessionWithStats])
async def list_sessions(db: Session = Depends(get_db)):
    """List all sessions with statistics."""
    sessions = (
        db.query(DBSession)
        .order_by(DBSession.created_at.desc())
        .all()
    )

    result = []
    for session in sessions:
        stats = get_session_stats(db, session.id)
        result.append(
            SessionWithStats(
                id=session.id,
                filename=session.filename,
                status=session.status,
                source_type=session.source_type,
                total_chunks=session.total_chunks,
                processed_chunks=session.processed_chunks,
                llm_provider=session.llm_provider,
                created_at=session.created_at,
                completed_at=session.completed_at,
                pdf_metadata=session.pdf_metadata,
                **stats,
            )
        )
    return result


@router.get("/{session_id}", response_model=SessionWithStats)
async def get_session(session_id: int, db: Session = Depends(get_db)):
    """Get session details with statistics."""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    stats = get_session_stats(db, session_id)
    return SessionWithStats(
        id=session.id,
        filename=session.filename,
        status=session.status,
        source_type=session.source_type,
        total_chunks=session.total_chunks,
        processed_chunks=session.processed_chunks,
        llm_provider=session.llm_provider,
        created_at=session.created_at,
        completed_at=session.completed_at,
        pdf_metadata=session.pdf_metadata,
        **stats,
    )


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(session_id: int, db: Session = Depends(get_db)):
    """Get session processing status."""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    progress = 0.0
    if session.total_chunks > 0:
        progress = (session.processed_chunks / session.total_chunks) * 100

    return SessionStatusResponse(
        id=session.id,
        status=session.status,
        total_chunks=session.total_chunks,
        processed_chunks=session.processed_chunks,
        progress_percent=progress,
    )


@router.post("/{session_id}/finalize", response_model=SessionWithStats)
async def finalize_session_endpoint(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Finalize a session and trigger prompt evolution analysis."""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == SessionStatus.FINALIZED.value:
        raise HTTPException(status_code=400, detail="Session already finalized")

    # Finalize session
    session = finalize_session(db, session_id)

    # Trigger prompt evolution analysis in background
    background_tasks.add_task(
        analyze_session_and_generate_suggestion,
        session_id=session_id,
        llm_provider=session.llm_provider,
    )

    stats = get_session_stats(db, session_id)
    return SessionWithStats(
        id=session.id,
        filename=session.filename,
        status=session.status,
        source_type=session.source_type,
        total_chunks=session.total_chunks,
        processed_chunks=session.processed_chunks,
        llm_provider=session.llm_provider,
        created_at=session.created_at,
        completed_at=session.completed_at,
        pdf_metadata=session.pdf_metadata,
        **stats,
    )


@router.delete("/{session_id}")
async def delete_session(session_id: int, db: Session = Depends(get_db)):
    """Delete a session and all its cards, including associated files."""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete the uploaded file
    file_path = Path(session.file_path)
    if file_path.exists():
        file_path.unlink()

    # Delete card images for this session (prefixed with session_id_)
    for img_file in CARD_IMAGES_DIR.glob(f"{session_id}_*"):
        img_file.unlink()

    # Delete export files that match this session's source filename
    if session.filename:
        stem = Path(session.filename).stem
        for export_file in EXPORTS_DIR.glob(f"{stem}_*"):
            export_file.unlink()

    # Delete markdown extraction directory for this session
    if session.source_type == SourceType.MARKDOWN.value:
        # file_path points to the .md inside EXTRACTIONS_DIR/<uuid>/...
        # Walk up to find the UUID directory directly under EXTRACTIONS_DIR
        try:
            relative = file_path.relative_to(EXTRACTIONS_DIR)
            session_extract_dir = EXTRACTIONS_DIR / relative.parts[0]
            if session_extract_dir.exists():
                shutil.rmtree(session_extract_dir)
        except ValueError:
            pass  # file_path not under EXTRACTIONS_DIR, skip

    # Delete session (cascades to cards)
    db.delete(session)
    db.commit()

    return {"message": "Session deleted successfully"}
