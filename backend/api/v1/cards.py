"""Card API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Session as DBSession
from backend.db.schemas import (
    BatchApproveRequest,
    BatchOperationResponse,
    BatchRejectRequest,
    CardEditRequest,
    CardRejectRequest,
    CardResponse,
    CardWithRejections,
)
from backend.services.card_service import (
    approve_card,
    auto_correct_card,
    batch_approve_cards,
    batch_reject_cards,
    edit_card,
    get_card,
    get_cards_for_session,
    reject_card,
)

router = APIRouter()


@router.get("/session/{session_id}", response_model=list[CardResponse])
async def get_session_cards(
    session_id: int,
    status: str | None = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """Get all cards for a session."""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    cards = get_cards_for_session(db, session_id, status)
    return cards


@router.get("/{card_id}", response_model=CardWithRejections)
async def get_card_detail(card_id: int, db: Session = Depends(get_db)):
    """Get a single card with rejection history."""
    card = get_card(db, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    return CardWithRejections(
        id=card.id,
        session_id=card.session_id,
        front=card.front,
        back=card.back,
        tags=card.tags,
        status=card.status,
        original_front=card.original_front,
        original_back=card.original_back,
        chunk_index=card.chunk_index,
        created_at=card.created_at,
        reviewed_at=card.reviewed_at,
        rejections=[
            {
                "id": r.id,
                "card_id": r.card_id,
                "reason": r.reason,
                "rejection_type": r.rejection_type,
                "auto_corrected": r.auto_corrected,
                "created_at": r.created_at,
            }
            for r in card.rejections
        ],
    )


@router.patch("/{card_id}/approve", response_model=CardResponse)
async def approve_card_endpoint(card_id: int, db: Session = Depends(get_db)):
    """Approve a card."""
    try:
        card = approve_card(db, card_id)
        return card
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{card_id}/reject", response_model=CardResponse)
async def reject_card_endpoint(
    card_id: int,
    request: CardRejectRequest,
    db: Session = Depends(get_db),
):
    """Reject a card with a reason."""
    try:
        card = reject_card(db, card_id, request)
        return card
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{card_id}/edit", response_model=CardResponse)
async def edit_card_endpoint(
    card_id: int,
    request: CardEditRequest,
    db: Session = Depends(get_db),
):
    """Edit a card's content."""
    try:
        card = edit_card(db, card_id, request)
        return card
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{card_id}/auto-correct", response_model=CardResponse)
async def auto_correct_card_endpoint(
    card_id: int,
    db: Session = Depends(get_db),
):
    """Auto-correct a rejected card using LLM."""
    card = get_card(db, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Get LLM provider from session
    session = db.query(DBSession).filter(DBSession.id == card.session_id).first()
    llm_provider = session.llm_provider if session else "openai"

    try:
        card = auto_correct_card(db, card_id, llm_provider)
        return card
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch/approve", response_model=BatchOperationResponse)
async def batch_approve_endpoint(
    request: BatchApproveRequest,
    db: Session = Depends(get_db),
):
    """Approve multiple cards at once."""
    result = batch_approve_cards(db, request.card_ids)
    return BatchOperationResponse(**result)


@router.post("/batch/reject", response_model=BatchOperationResponse)
async def batch_reject_endpoint(
    request: BatchRejectRequest,
    db: Session = Depends(get_db),
):
    """Reject multiple cards at once."""
    result = batch_reject_cards(
        db,
        request.card_ids,
        request.reason,
        request.rejection_type.value,
    )
    return BatchOperationResponse(**result)
