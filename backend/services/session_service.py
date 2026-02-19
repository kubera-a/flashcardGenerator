"""Service for managing card generation sessions."""

import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.db.database import SessionLocal
from backend.db.models import (
    Card,
    CardImage,
    CardStatus,
    PromptType,
    SessionStatus,
    SourceType,
)
from backend.db.models import (
    Session as DBSession,
)
from backend.services.pdf_service import (
    get_pdf_info,
)
from backend.services.prompt_service import get_active_prompt, update_prompt_metrics
from config.prompts import (
    BATCH_CONTEXT_TEMPLATE,
    CONTINUE_GENERATION_PROMPT,
    GENERATION_PROMPT,
    MARKDOWN_GENERATION_PROMPT,
)
from config.settings import CARD_IMAGES_DIR
from modules.card_generation import CardGenerator
from modules.llm_interface import LLMInterface
from modules.markdown_processor import MarkdownProcessor
from modules.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)


def create_session(
    db: Session,
    filename: str,
    file_path: str,
    llm_provider: str = "openai",
    source_type: str = SourceType.PDF.value,
) -> DBSession:
    """Create a new card generation session."""
    # Get active generation prompt
    gen_prompt = get_active_prompt(db, PromptType.GENERATION)

    session = DBSession(
        filename=filename,
        file_path=file_path,
        llm_provider=llm_provider,
        source_type=source_type,
        status=SessionStatus.PROCESSING.value,
        prompt_version_id=gen_prompt.id if gen_prompt else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def process_pdf_and_generate_cards(
    session_id: int,
    db: Session | None = None,
) -> None:
    """
    Process a PDF and generate cards for a session.

    Note: This function creates its own database session for use in background tasks.
    The db parameter is deprecated and ignored.
    """
    # Create our own database session for background task
    db = SessionLocal()

    try:
        session = db.query(DBSession).filter(DBSession.id == session_id).first()
        if not session:
            logger.error(f"Session {session_id} not found")
            return

        # Check if we should use native PDF support
        metadata = session.pdf_metadata or {}
        use_native_pdf = metadata.get("use_native_pdf", True)
        selected_pages = metadata.get("selected_pages")

        # Initialize LLM
        llm = LLMInterface(provider=session.llm_provider)

        # Use native PDF support if available and requested
        if use_native_pdf and llm.supports_native_pdf():
            _process_with_native_pdf(db, session, llm, selected_pages)
        else:
            _process_with_text_extraction(db, session, llm, selected_pages)

    except Exception as e:
        logger.error(f"Error processing session {session_id}: {e}", exc_info=True)
        try:
            session = db.query(DBSession).filter(DBSession.id == session_id).first()
            if session:
                session.status = SessionStatus.FAILED.value
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def create_page_batches(
    pages: list[int],
    batch_size: int = 10,
    overlap: int = 1,
) -> list[list[int]]:
    """
    Create page batches with overlap for context continuity.

    Args:
        pages: List of page indices to batch
        batch_size: Number of pages per batch (default 10)
        overlap: Number of overlapping pages between batches (default 1)

    Returns:
        List of page batches
    """
    if len(pages) <= batch_size:
        return [pages]

    batches = []
    stride = batch_size - overlap

    for i in range(0, len(pages), stride):
        batch = pages[i:i + batch_size]
        if batch:
            # Don't create a tiny final batch if it's just overlap pages
            if len(batch) <= overlap and batches:
                # Extend the previous batch instead
                batches[-1] = list(dict.fromkeys(batches[-1] + batch))
            else:
                batches.append(batch)

        # If we've covered all pages, stop
        if i + batch_size >= len(pages):
            break

    return batches


def _process_with_native_pdf(
    db: Session,
    session: DBSession,
    llm: LLMInterface,
    selected_pages: list[int] | None,
) -> None:
    """Process PDF using Claude's native PDF support."""
    logger.info(f"Processing session {session.id} with native PDF support")

    # Get PDF info
    pdf_info = get_pdf_info(session.file_path)
    page_count = pdf_info["page_count"]

    # Determine which pages to process
    if selected_pages is None:
        selected_pages = list(range(page_count))

    # Update session metadata
    session.pdf_metadata = session.pdf_metadata or {}
    session.pdf_metadata.update(pdf_info)
    session.pdf_metadata["selected_pages"] = selected_pages

    # Create batches with 10 pages and 1-page overlap for context continuity
    # Claude has a 100 page limit, but we use smaller batches for better results
    batches = create_page_batches(selected_pages, batch_size=10, overlap=1)
    session.total_chunks = len(batches)
    session.pdf_metadata["batch_strategy"] = "10_pages_1_overlap"
    db.commit()


    # Use centralized prompts from config/prompts.py
    generation_prompt = GENERATION_PROMPT.user_prompt_template
    system_prompt = GENERATION_PROMPT.system_prompt
    output_format = GENERATION_PROMPT.output_format

    # Process each batch
    errors = []
    processed_pages = set()  # Track pages we've already fully processed

    for batch_idx, page_batch in enumerate(batches):
        try:
            # Identify which pages are new vs overlap context
            new_pages = [p for p in page_batch if p not in processed_pages]
            context_pages = [p for p in page_batch if p in processed_pages]

            # Build batch-specific prompt with context awareness
            batch_prompt = generation_prompt
            if context_pages and new_pages:
                batch_prompt += BATCH_CONTEXT_TEMPLATE.format(
                    batch_num=batch_idx + 1,
                    total_batches=len(batches),
                    context_pages=[p + 1 for p in context_pages],
                    new_pages=[p + 1 for p in new_pages],
                )

            # Generate cards from PDF pages
            response = llm.generate_structured_from_pdf(
                pdf_path=session.file_path,
                prompt=batch_prompt,
                output_format=output_format,
                system_prompt=system_prompt,
                page_indices=page_batch,
            )

            # Mark all pages in this batch as processed
            processed_pages.update(page_batch)

            # Save cards to database
            for card_data in response.get("cards", []):
                tags = card_data.get("tags", [])

                # Add metadata-based tags
                if pdf_info.get("title"):
                    tags.append(pdf_info["title"].replace(" ", "_").lower())

                db_card = Card(
                    session_id=session.id,
                    front=card_data.get("front", ""),
                    back=card_data.get("back", ""),
                    tags=tags,
                    status=CardStatus.PENDING.value,
                    chunk_index=batch_idx,
                )
                db.add(db_card)

            session.processed_chunks = batch_idx + 1
            db.commit()

        except Exception as e:
            logger.error(f"Error processing batch {batch_idx}: {e}")
            errors.append(str(e))
            continue

    # Check if any cards were generated
    card_count = db.query(Card).filter(Card.session_id == session.id).count()

    # Update session status based on results
    if card_count == 0 and errors:
        session.status = SessionStatus.FAILED.value
        # Store error info in metadata
        session.pdf_metadata = session.pdf_metadata or {}
        session.pdf_metadata["error"] = errors[0] if len(errors) == 1 else f"{len(errors)} errors occurred"
        logger.error(f"Session {session.id} failed: no cards generated. Errors: {errors}")
    else:
        session.status = SessionStatus.READY.value

    session.completed_at = datetime.utcnow()
    if session.prompt_version_id:
        update_prompt_metrics(
            db,
            session.prompt_version_id,
            cards_generated=card_count,
        )

    db.commit()


def _process_with_text_extraction(
    db: Session,
    session: DBSession,
    llm: LLMInterface,
    selected_pages: list[int] | None,
) -> None:
    """Process PDF using traditional text extraction (fallback for non-Claude providers)."""
    logger.info(f"Processing session {session.id} with text extraction")

    # Process PDF with text extraction
    pdf_processor = PDFProcessor()
    chunks, metadata = pdf_processor.process_pdf(session.file_path)

    # Update session with metadata
    session.pdf_metadata = session.pdf_metadata or {}
    session.pdf_metadata.update(metadata)
    session.total_chunks = len(chunks)
    db.commit()

    # Initialize generator
    generator = CardGenerator(llm_interface=llm)

    # Generate cards for each chunk
    errors = []
    for i, chunk in enumerate(chunks):
        try:
            cards = generator.generate_cards_from_chunk(chunk, metadata)
            validated_cards = generator.validate_cards(cards)

            # Save cards to database
            for card in validated_cards:
                db_card = Card(
                    session_id=session.id,
                    front=card.front,
                    back=card.back,
                    tags=card.tags,
                    status=CardStatus.PENDING.value,
                    chunk_index=i,
                )
                db.add(db_card)

            session.processed_chunks = i + 1
            db.commit()

        except Exception as e:
            logger.error(f"Error processing chunk {i}: {e}")
            errors.append(str(e))
            continue

    # Check if any cards were generated
    card_count = db.query(Card).filter(Card.session_id == session.id).count()

    # Update session status based on results
    if card_count == 0 and errors:
        session.status = SessionStatus.FAILED.value
        session.pdf_metadata = session.pdf_metadata or {}
        session.pdf_metadata["error"] = errors[0] if len(errors) == 1 else f"{len(errors)} errors occurred"
        logger.error(f"Session {session.id} failed: no cards generated. Errors: {errors}")
    else:
        session.status = SessionStatus.READY.value

    session.completed_at = datetime.utcnow()

    # Update prompt metrics
    if session.prompt_version_id:
        update_prompt_metrics(
            db,
            session.prompt_version_id,
            cards_generated=card_count,
        )

    db.commit()


def get_session_stats(db: Session, session_id: int) -> dict:
    """Get card statistics for a session."""
    total = db.query(Card).filter(Card.session_id == session_id).count()
    approved = (
        db.query(Card)
        .filter(Card.session_id == session_id, Card.status == CardStatus.APPROVED.value)
        .count()
    )
    rejected = (
        db.query(Card)
        .filter(Card.session_id == session_id, Card.status == CardStatus.REJECTED.value)
        .count()
    )
    pending = (
        db.query(Card)
        .filter(Card.session_id == session_id, Card.status == CardStatus.PENDING.value)
        .count()
    )

    return {
        "card_count": total,
        "approved_count": approved,
        "rejected_count": rejected,
        "pending_count": pending,
    }


def finalize_session(db: Session, session_id: int) -> DBSession:
    """Finalize a session and trigger prompt evolution analysis."""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise ValueError(f"Session {session_id} not found")

    session.status = SessionStatus.FINALIZED.value
    session.completed_at = datetime.utcnow()

    # Update prompt metrics with final approval/rejection counts
    stats = get_session_stats(db, session_id)
    if session.prompt_version_id:
        update_prompt_metrics(
            db,
            session.prompt_version_id,
            approved=stats["approved_count"],
            rejected=stats["rejected_count"],
        )

    db.commit()
    db.refresh(session)
    return session


def continue_generation(
    session_id: int,
    focus_areas: str | None = None,
    page_indices: list[int] | None = None,
) -> None:
    """
    Continue generating cards for a session, avoiding duplicates of existing cards.

    Args:
        session_id: ID of the session to continue
        focus_areas: Optional guidance on what to focus on
        page_indices: Optional specific pages to re-process
    """
    db = SessionLocal()

    try:
        session = db.query(DBSession).filter(DBSession.id == session_id).first()
        if not session:
            logger.error(f"Session {session_id} not found")
            return

        # Get existing cards (approved and pending) to avoid duplicates
        existing_cards = (
            db.query(Card)
            .filter(
                Card.session_id == session_id,
                Card.status.in_([CardStatus.APPROVED.value, CardStatus.PENDING.value, CardStatus.EDITED.value])
            )
            .all()
        )

        # Format existing cards as context
        existing_cards_context = "\n".join(
            f"- Q: {card.front}\n  A: {card.back}"
            for card in existing_cards[:100]  # Limit to avoid token overflow
        )

        # Get pages to process
        metadata = session.pdf_metadata or {}
        if page_indices is None:
            page_indices = metadata.get("selected_pages")

        if page_indices is None:
            pdf_info = get_pdf_info(session.file_path)
            page_indices = list(range(pdf_info["page_count"]))

        # Initialize LLM
        llm = LLMInterface(provider=session.llm_provider)

        if not llm.supports_native_pdf():
            logger.error("Continue generation requires native PDF support")
            return

        # Update session status
        session.status = SessionStatus.PROCESSING.value
        db.commit()

        # Create batches
        batches = create_page_batches(page_indices, batch_size=10, overlap=1)

        # Build the continuation prompt using centralized template
        focus_section = f"## USER GUIDANCE:\n{focus_areas}" if focus_areas else ""
        continuation_prompt = CONTINUE_GENERATION_PROMPT.user_prompt_template.format(
            existing_cards=existing_cards_context,
            focus_areas=focus_section,
        )
        system_prompt = CONTINUE_GENERATION_PROMPT.system_prompt
        output_format = CONTINUE_GENERATION_PROMPT.output_format

        # Get max chunk index for new cards
        max_chunk = db.query(Card).filter(Card.session_id == session_id).count()

        # Process each batch
        errors = []
        new_card_count = 0

        for batch_idx, page_batch in enumerate(batches):
            try:
                response = llm.generate_structured_from_pdf(
                    pdf_path=session.file_path,
                    prompt=continuation_prompt,
                    output_format=output_format,
                    system_prompt=system_prompt,
                    page_indices=page_batch,
                )

                # Save new cards
                for card_data in response.get("cards", []):
                    tags = card_data.get("tags", [])
                    tags.append("continued_generation")

                    db_card = Card(
                        session_id=session.id,
                        front=card_data.get("front", ""),
                        back=card_data.get("back", ""),
                        tags=tags,
                        status=CardStatus.PENDING.value,
                        chunk_index=max_chunk + batch_idx,
                    )
                    db.add(db_card)
                    new_card_count += 1

                db.commit()

            except Exception as e:
                logger.error(f"Error in continue generation batch {batch_idx}: {e}")
                errors.append(str(e))
                continue

        # Update session status
        session.status = SessionStatus.READY.value
        metadata["continue_generation_count"] = metadata.get("continue_generation_count", 0) + 1
        metadata["last_continue_new_cards"] = new_card_count
        session.pdf_metadata = metadata
        db.commit()

        logger.info(f"Continue generation completed for session {session_id}: {new_card_count} new cards")

    except Exception as e:
        logger.error(f"Error in continue generation for session {session_id}: {e}", exc_info=True)
        try:
            session = db.query(DBSession).filter(DBSession.id == session_id).first()
            if session:
                session.status = SessionStatus.READY.value  # Return to ready, not failed
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def process_markdown_and_generate_cards(
    session_id: int,
    db: Session | None = None,
) -> None:
    """
    Process a markdown document with images and generate cards.

    This function:
    1. Parses the markdown document and extracts image references
    2. Sends the markdown content + images to Claude for multimodal processing
    3. Creates cards with image references in the format [IMAGE: filename.png]
    4. Stores CardImage records linking images to cards

    Note: This function creates its own database session for use in background tasks.
    """
    db = SessionLocal()

    try:
        session = db.query(DBSession).filter(DBSession.id == session_id).first()
        if not session:
            logger.error(f"Session {session_id} not found")
            return

        metadata = session.pdf_metadata or {}

        # Get paths from metadata
        base_dir = Path(metadata.get("base_dir", ""))

        if not base_dir.exists():
            logger.error(f"Markdown base directory not found: {base_dir}")
            session.status = SessionStatus.FAILED.value
            session.pdf_metadata["error"] = "Markdown base directory not found"
            db.commit()
            return

        # Parse the markdown file
        processor = MarkdownProcessor()
        doc = processor.parse_markdown(Path(session.file_path))

        # Initialize LLM (must be Anthropic for image support)
        llm = LLMInterface(provider=session.llm_provider)

        if session.llm_provider != "anthropic":
            logger.error("Markdown with images requires Anthropic provider")
            session.status = SessionStatus.FAILED.value
            session.pdf_metadata["error"] = "Markdown with images requires Anthropic provider"
            db.commit()
            return

        # Get list of existing image paths
        existing_images = [img for img in doc.images if img.exists and img.absolute_path]

        # Update session metadata with image count
        session.total_chunks = 1  # Single batch for markdown
        session.pdf_metadata["image_count"] = len(existing_images)
        db.commit()

        # Build prompt using centralized template
        image_list = "\n".join(
            f"- {img.relative_path}" for img in existing_images
        )
        prompt = MARKDOWN_GENERATION_PROMPT.user_prompt_template.format(
            image_count=len(existing_images),
            image_list=image_list,
            batch_context="",  # No batching for markdown
        )
        system_prompt = MARKDOWN_GENERATION_PROMPT.system_prompt
        output_format = MARKDOWN_GENERATION_PROMPT.output_format

        # Collect image paths for LLM
        image_paths = [img.absolute_path for img in existing_images]

        # Generate cards from markdown with images
        try:
            response = llm.generate_structured_from_markdown(
                markdown_content=doc.content,
                images=image_paths,
                prompt=prompt,
                output_format=output_format,
                system_prompt=system_prompt,
            )
        except Exception as e:
            logger.error(f"Error generating cards from markdown: {e}", exc_info=True)
            session.status = SessionStatus.FAILED.value
            session.pdf_metadata["error"] = str(e)
            db.commit()
            return

        # Create image filename mapping for storage
        image_mapping = processor.get_image_mapping(doc, session.id)

        # Use centralized image storage directory
        image_storage_dir = CARD_IMAGES_DIR

        # Copy images to storage with session-prefixed names
        processor.copy_images_to_storage(doc, image_mapping, image_storage_dir)

        # Save cards to database
        card_count = 0
        for card_data in response.get("cards", []):
            front = card_data.get("front", "")
            back = card_data.get("back", "")
            tags = card_data.get("tags", [])
            card_images = card_data.get("images", [])

            # Add source tag
            if metadata.get("title"):
                tags.append(metadata["title"].replace(" ", "_").lower())

            # Create the card
            db_card = Card(
                session_id=session.id,
                front=front,
                back=back,
                tags=tags,
                status=CardStatus.PENDING.value,
                chunk_index=0,
            )
            db.add(db_card)
            db.flush()  # Get the card ID

            # Create CardImage records for images referenced in this card
            for img_filename in card_images:
                # Find the matching image in our document
                matching_img = None
                for img in existing_images:
                    # Match by filename (with or without path)
                    if img_filename in img.relative_path or Path(img.relative_path).name == img_filename:
                        matching_img = img
                        break

                if matching_img and matching_img.relative_path in image_mapping:
                    stored_name = image_mapping[matching_img.relative_path]
                    file_size = matching_img.absolute_path.stat().st_size if matching_img.absolute_path else 0

                    # Determine media type from extension
                    suffix = matching_img.absolute_path.suffix.lower() if matching_img.absolute_path else ".png"
                    media_types = {
                        ".png": "image/png",
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".gif": "image/gif",
                        ".webp": "image/webp",
                    }
                    media_type = media_types.get(suffix, "image/png")

                    card_image = CardImage(
                        card_id=db_card.id,
                        session_id=session.id,
                        original_filename=img_filename,
                        stored_filename=stored_name,
                        media_type=media_type,
                        file_size=file_size,
                    )
                    db.add(card_image)

            card_count += 1

        session.processed_chunks = 1
        session.status = SessionStatus.READY.value
        session.completed_at = datetime.utcnow()
        session.pdf_metadata["cards_generated"] = card_count

        # Update prompt metrics
        if session.prompt_version_id:
            update_prompt_metrics(
                db,
                session.prompt_version_id,
                cards_generated=card_count,
            )

        db.commit()
        logger.info(f"Markdown processing completed for session {session_id}: {card_count} cards generated")

    except Exception as e:
        logger.error(f"Error processing markdown session {session_id}: {e}", exc_info=True)
        try:
            session = db.query(DBSession).filter(DBSession.id == session_id).first()
            if session:
                session.status = SessionStatus.FAILED.value
                session.pdf_metadata = session.pdf_metadata or {}
                session.pdf_metadata["error"] = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
