"""Service for managing flashcard operations."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from backend.db.models import Card, CardRejection, CardStatus
from backend.db.schemas import CardEditRequest, CardRejectRequest
from modules.llm_interface import LLMInterface

logger = logging.getLogger(__name__)


def get_cards_for_session(
    db: Session,
    session_id: int,
    status: str | None = None,
) -> list[Card]:
    """Get all cards for a session, optionally filtered by status."""
    query = db.query(Card).filter(Card.session_id == session_id)
    if status:
        query = query.filter(Card.status == status)
    return query.order_by(Card.chunk_index, Card.id).all()


def get_card(db: Session, card_id: int) -> Card | None:
    """Get a single card by ID."""
    return db.query(Card).filter(Card.id == card_id).first()


def approve_card(db: Session, card_id: int) -> Card:
    """Approve a card."""
    card = get_card(db, card_id)
    if not card:
        raise ValueError(f"Card {card_id} not found")

    card.status = CardStatus.APPROVED.value
    card.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(card)
    return card


def reject_card(db: Session, card_id: int, request: CardRejectRequest) -> Card:
    """Reject a card with a reason."""
    card = get_card(db, card_id)
    if not card:
        raise ValueError(f"Card {card_id} not found")

    # Create rejection record
    rejection = CardRejection(
        card_id=card_id,
        reason=request.reason,
        rejection_type=request.rejection_type.value,
    )
    db.add(rejection)

    card.status = CardStatus.REJECTED.value
    card.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(card)
    return card


def edit_card(db: Session, card_id: int, request: CardEditRequest) -> Card:
    """Edit a card's content."""
    card = get_card(db, card_id)
    if not card:
        raise ValueError(f"Card {card_id} not found")

    # Store original if not already stored
    if not card.original_front:
        card.original_front = card.front
        card.original_back = card.back

    card.front = request.front
    card.back = request.back
    if request.tags is not None:
        card.tags = request.tags
    card.status = CardStatus.EDITED.value
    card.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(card)
    return card


def auto_correct_card(
    db: Session,
    card_id: int,
    llm_provider: str = "openai",
) -> Card:
    """Use LLM to auto-correct a rejected card based on rejection feedback."""
    card = get_card(db, card_id)
    if not card:
        raise ValueError(f"Card {card_id} not found")

    # Get the latest rejection reason
    latest_rejection = (
        db.query(CardRejection)
        .filter(CardRejection.card_id == card_id)
        .order_by(CardRejection.created_at.desc())
        .first()
    )

    if not latest_rejection:
        raise ValueError(f"Card {card_id} has no rejection history")

    # Build the correction prompt
    correction_prompt = f"""
    The following flashcard was rejected by a user. Please improve it based on their feedback.

    Original Card:
    Question: {card.front}
    Answer: {card.back}

    Rejection Type: {latest_rejection.rejection_type}
    User's Feedback: {latest_rejection.reason}

    Please create an improved version of this flashcard that addresses the user's concerns.
    The question should be clear, specific, and unambiguous.
    The answer should be concise but complete.

    Return ONLY valid JSON in this exact format:
    {{"front": "improved question", "back": "improved answer"}}
    """

    system_prompt = """
    You are an expert in creating educational flashcards. Your task is to improve
    a flashcard based on user feedback. Focus on clarity, accuracy, and effectiveness.
    Return only valid JSON with no additional text.
    """

    try:
        llm = LLMInterface(provider=llm_provider)
        response = llm.generate_structured_output(
            prompt=correction_prompt,
            output_format={"front": "string", "back": "string"},
            system_prompt=system_prompt,
        )

        # Store original if not already stored
        if not card.original_front:
            card.original_front = card.front
            card.original_back = card.back

        # Update card with corrected content
        card.front = response.get("front", card.front)
        card.back = response.get("back", card.back)
        card.status = CardStatus.PENDING.value  # Back to pending for re-review
        card.reviewed_at = datetime.utcnow()

        # Mark the rejection as auto-corrected
        latest_rejection.auto_corrected = True

        db.commit()
        db.refresh(card)
        return card

    except Exception as e:
        logger.error(f"Error auto-correcting card {card_id}: {e}")
        raise ValueError(f"Failed to auto-correct card: {e}")


def batch_approve_cards(db: Session, card_ids: list[int]) -> dict:
    """Approve multiple cards at once."""
    processed = 0
    failed = 0

    for card_id in card_ids:
        try:
            approve_card(db, card_id)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to approve card {card_id}: {e}")
            failed += 1

    return {
        "processed": processed,
        "failed": failed,
        "message": f"Approved {processed} cards, {failed} failed",
    }


def batch_reject_cards(
    db: Session,
    card_ids: list[int],
    reason: str,
    rejection_type: str,
) -> dict:
    """Reject multiple cards at once with the same reason."""
    from backend.db.schemas import CardRejectRequest, RejectionType

    processed = 0
    failed = 0

    request = CardRejectRequest(
        reason=reason,
        rejection_type=RejectionType(rejection_type),
    )

    for card_id in card_ids:
        try:
            reject_card(db, card_id, request)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to reject card {card_id}: {e}")
            failed += 1

    return {
        "processed": processed,
        "failed": failed,
        "message": f"Rejected {processed} cards, {failed} failed",
    }
