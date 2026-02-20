"""Service for managing card generation sessions."""

import base64
import logging
import re
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
    PDF_GENERATION_PROMPT,
)
from config.settings import CARD_IMAGES_DIR, CHUNK_SIZE, sanitize_filename
from modules.llm_interface import LLMInterface
from modules.markdown_processor import MarkdownProcessor
from modules.pdf_image_extractor import (
    extract_images_from_pdf,
    get_images_for_pages,
    save_pdf_images,
)
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

    # Extract embedded images from the PDF
    deck_tag = sanitize_filename(session.display_name or session.filename)
    all_images = extract_images_from_pdf(session.file_path, selected_pages)
    image_mapping: dict[str, str] = {}
    has_images = len(all_images) > 0

    if has_images:
        image_mapping = save_pdf_images(all_images, CARD_IMAGES_DIR, deck_tag)
        session.pdf_metadata["extracted_image_count"] = len(all_images)
        db.commit()
        logger.info(f"Extracted {len(all_images)} images from PDF for session {session.id}")

    # Use centralized prompts from config/prompts.py
    # If images were extracted, use the PDF image-aware prompt; otherwise standard
    base_prompt_template = PDF_GENERATION_PROMPT if has_images else GENERATION_PROMPT
    system_prompt = base_prompt_template.system_prompt
    output_format = base_prompt_template.output_format

    # Process each batch
    errors = []
    processed_pages = set()  # Track pages we've already fully processed

    for batch_idx, page_batch in enumerate(batches):
        try:
            # Identify which pages are new vs overlap context
            new_pages = [p for p in page_batch if p not in processed_pages]
            context_pages = [p for p in page_batch if p in processed_pages]

            # Build batch-specific prompt
            encoded_batch_images = None
            if has_images:
                # Get images for this batch's pages and build per-page image list
                batch_images = get_images_for_pages(all_images, page_batch)
                if batch_images:
                    # Group images by position within this batch's subset PDF
                    page_to_position = {p: i + 1 for i, p in enumerate(page_batch)}
                    page_groups: dict[int, list[str]] = {}
                    for img in batch_images:
                        pos = page_to_position.get(img.page_num, 0)
                        page_groups.setdefault(pos, []).append(img.filename)
                    image_list = "\n".join(
                        f"- Page {pos} of this batch: {', '.join(fnames)}"
                        for pos, fnames in sorted(page_groups.items())
                    )

                    # Encode images as base64 to send alongside the PDF
                    ext_to_media = {
                        "png": "image/png",
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "gif": "image/gif",
                        "webp": "image/webp",
                    }
                    encoded_batch_images = []
                    for img in batch_images:
                        media_type = ext_to_media.get(img.ext, "image/png")
                        b64_data = base64.standard_b64encode(img.image_bytes).decode("utf-8")
                        encoded_batch_images.append((b64_data, media_type))
                else:
                    image_list = "(no images on these pages)"

                batch_prompt = base_prompt_template.user_prompt_template.format(
                    image_list=image_list,
                )
            else:
                batch_prompt = base_prompt_template.user_prompt_template

            if context_pages and new_pages:
                batch_prompt += BATCH_CONTEXT_TEMPLATE.format(
                    batch_num=batch_idx + 1,
                    total_batches=len(batches),
                    context_count=len(context_pages),
                )

            # Generate cards from PDF pages (with extracted images if available)
            response = llm.generate_structured_from_pdf(
                pdf_path=session.file_path,
                prompt=batch_prompt,
                output_format=output_format,
                system_prompt=system_prompt,
                page_indices=page_batch,
                images=encoded_batch_images,
            )

            # Mark all pages in this batch as processed
            processed_pages.update(page_batch)

            # Save cards to database
            for card_data in response.get("cards", []):
                db_card = Card(
                    session_id=session.id,
                    front=card_data.get("front", ""),
                    back=card_data.get("back", ""),
                    tags=[deck_tag],
                    status=CardStatus.PENDING.value,
                    chunk_index=batch_idx,
                )
                db.add(db_card)

                # Create CardImage records for any referenced images
                if has_images:
                    db.flush()  # Get db_card.id
                    for img_filename in card_data.get("images", []):
                        if img_filename in image_mapping:
                            stored_name = image_mapping[img_filename]
                            stored_path = CARD_IMAGES_DIR / stored_name
                            file_size = stored_path.stat().st_size if stored_path.exists() else 0

                            ext_to_media = {
                                "png": "image/png",
                                "jpg": "image/jpeg",
                                "jpeg": "image/jpeg",
                                "gif": "image/gif",
                                "webp": "image/webp",
                            }
                            img_ext = img_filename.rsplit(".", 1)[-1].lower()
                            media_type = ext_to_media.get(img_ext, "image/png")

                            card_image = CardImage(
                                card_id=db_card.id,
                                session_id=session.id,
                                original_filename=img_filename,
                                stored_filename=stored_name,
                                media_type=media_type,
                                file_size=file_size,
                            )
                            db.add(card_image)

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

    # Use centralized prompts (same as native PDF path)
    generation_prompt = GENERATION_PROMPT.user_prompt_template
    system_prompt = GENERATION_PROMPT.system_prompt
    output_format = GENERATION_PROMPT.output_format

    # Generate cards for each chunk
    errors = []
    for i, chunk in enumerate(chunks):
        try:
            full_prompt = f"{generation_prompt}\n\n## Document Content:\n{chunk}"

            response = llm.generate_structured_output(
                prompt=full_prompt,
                output_format=output_format,
                system_prompt=system_prompt,
            )

            # Save cards to database
            deck_tag = sanitize_filename(session.display_name or session.filename)
            for card_data in response.get("cards", []):
                db_card = Card(
                    session_id=session.id,
                    front=card_data.get("front", ""),
                    back=card_data.get("back", ""),
                    tags=[deck_tag],
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
                deck_tag = sanitize_filename(session.display_name or session.filename)
                for card_data in response.get("cards", []):
                    db_card = Card(
                        session_id=session.id,
                        front=card_data.get("front", ""),
                        back=card_data.get("back", ""),
                        tags=[deck_tag],
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


def chunk_markdown(content: str, images: list, chunk_size: int = CHUNK_SIZE) -> list[dict]:
    """
    Split markdown content into chunks, tracking which images belong to each chunk.

    Splits on heading boundaries (## or #) when possible, falling back to
    paragraph boundaries. Each chunk includes only the images referenced within it.

    Args:
        content: Full markdown text
        images: List of MarkdownImage objects
        chunk_size: Max characters per chunk

    Returns:
        List of dicts with 'content' (str) and 'images' (list) keys
    """

    IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")  # noqa: N806

    # Split on headings (keep heading with its section)
    sections = re.split(r"(?=^#{1,2}\s)", content, flags=re.MULTILINE)
    sections = [s for s in sections if s.strip()]

    chunks = []
    current_chunk = ""

    for section in sections:
        if len(current_chunk) + len(section) <= chunk_size:
            current_chunk += section
        else:
            if current_chunk.strip():
                chunks.append(current_chunk)
            # If a single section exceeds chunk_size, split by paragraphs
            if len(section) > chunk_size:
                paragraphs = section.split("\n\n")
                current_chunk = ""
                for para in paragraphs:
                    if len(current_chunk) + len(para) + 2 <= chunk_size:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk.strip():
                            chunks.append(current_chunk)
                        current_chunk = para + "\n\n"
            else:
                current_chunk = section

    if current_chunk.strip():
        chunks.append(current_chunk)

    # Build image lookup by relative path
    image_lookup = {}
    for img in images:
        if img.exists and img.absolute_path:
            image_lookup[img.relative_path] = img

    # Associate images with their chunks
    result = []
    for chunk_text in chunks:
        chunk_images = []
        for match in IMAGE_PATTERN.finditer(chunk_text):
            import urllib.parse
            rel_path = urllib.parse.unquote(match.group(2))
            if rel_path in image_lookup:
                chunk_images.append(image_lookup[rel_path])
        result.append({"content": chunk_text, "images": chunk_images})

    return result


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

        # Chunk the markdown content
        chunks = chunk_markdown(doc.content, doc.images)

        # Update session metadata
        session.total_chunks = len(chunks)
        session.pdf_metadata["image_count"] = len(existing_images)
        db.commit()

        system_prompt = MARKDOWN_GENERATION_PROMPT.system_prompt
        output_format = MARKDOWN_GENERATION_PROMPT.output_format

        # Create image filename mapping and copy images to storage upfront
        deck_tag = sanitize_filename(session.display_name or session.filename)
        image_mapping = processor.get_image_mapping(doc, deck_tag)
        image_storage_dir = CARD_IMAGES_DIR
        processor.copy_images_to_storage(doc, image_mapping, image_storage_dir)

        # Process each chunk
        card_count = 0
        errors = []

        for chunk_idx, chunk_data in enumerate(chunks):
            try:
                chunk_images = chunk_data["images"]
                image_paths = [img.absolute_path for img in chunk_images]

                # Build prompt for this chunk
                image_list = "\n".join(
                    f"- {img.relative_path}" for img in chunk_images
                )
                prompt = MARKDOWN_GENERATION_PROMPT.user_prompt_template.format(
                    image_list=image_list if image_list else "(no images in this section)",
                )
                if len(chunks) > 1:
                    prompt += (
                        f"\n\n## BATCH CONTEXT:\n"
                        f"- This is chunk {chunk_idx + 1} of {len(chunks)}\n"
                        f"- Focus on generating cards for THIS section only\n"
                    )

                response = llm.generate_structured_from_markdown(
                    markdown_content=chunk_data["content"],
                    images=image_paths,
                    prompt=prompt,
                    output_format=output_format,
                    system_prompt=system_prompt,
                )

                # Save cards to database
                for card_data in response.get("cards", []):
                    front = card_data.get("front", "")
                    back = card_data.get("back", "")
                    card_images_list = card_data.get("images", [])

                    db_card = Card(
                        session_id=session.id,
                        front=front,
                        back=back,
                        tags=[deck_tag],
                        status=CardStatus.PENDING.value,
                        chunk_index=chunk_idx,
                    )
                    db.add(db_card)
                    db.flush()

                    # Create CardImage records for images referenced in this card
                    for img_filename in card_images_list:
                        matching_img = None
                        for img in existing_images:
                            if img_filename in img.relative_path or Path(img.relative_path).name == img_filename:
                                matching_img = img
                                break

                        if matching_img and matching_img.relative_path in image_mapping:
                            stored_name = image_mapping[matching_img.relative_path]
                            file_size = matching_img.absolute_path.stat().st_size if matching_img.absolute_path else 0

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

                session.processed_chunks = chunk_idx + 1
                db.commit()

            except Exception as e:
                logger.error(f"Error processing markdown chunk {chunk_idx}: {e}", exc_info=True)
                errors.append(str(e))
                continue

        # Update session status
        if card_count == 0 and errors:
            session.status = SessionStatus.FAILED.value
            session.pdf_metadata["error"] = errors[0] if len(errors) == 1 else f"{len(errors)} errors occurred"
        else:
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
        logger.info(f"Markdown processing completed for session {session_id}: {card_count} cards from {len(chunks)} chunks")

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
