"""Prompt management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import PromptVersion
from backend.db.schemas import (
    CurrentPromptsResponse,
    PromptSuggestionResponse,
    PromptVersionResponse,
)
from backend.services.prompt_evolution_service import (
    approve_suggestion,
    get_pending_suggestions,
    get_prompt_history,
    reject_suggestion,
)
from backend.services.prompt_service import get_active_prompts

router = APIRouter()


@router.get("/current", response_model=CurrentPromptsResponse)
async def get_current_prompts(db: Session = Depends(get_db)):
    """Get currently active prompts for generation and validation."""
    prompts = get_active_prompts(db)
    return CurrentPromptsResponse(
        generation=prompts.get("generation"),
        validation=prompts.get("validation"),
    )


@router.get("/history", response_model=list[PromptVersionResponse])
async def get_prompts_history(
    prompt_type: str | None = None,
    db: Session = Depends(get_db),
):
    """Get prompt version history."""
    history = get_prompt_history(db, prompt_type)
    return history


@router.get("/suggestions", response_model=list[PromptSuggestionResponse])
async def get_suggestions(db: Session = Depends(get_db)):
    """Get all pending prompt suggestions."""
    suggestions = get_pending_suggestions(db)
    return suggestions


@router.get("/suggestions/{suggestion_id}", response_model=PromptSuggestionResponse)
async def get_suggestion(suggestion_id: int, db: Session = Depends(get_db)):
    """Get a specific suggestion."""
    from backend.db.models import PromptSuggestion

    suggestion = (
        db.query(PromptSuggestion)
        .filter(PromptSuggestion.id == suggestion_id)
        .first()
    )
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return suggestion


@router.post("/suggestions/{suggestion_id}/approve", response_model=PromptVersionResponse)
async def approve_suggestion_endpoint(
    suggestion_id: int,
    db: Session = Depends(get_db),
):
    """Approve a suggestion and create a new prompt version."""
    try:
        new_version = approve_suggestion(db, suggestion_id)
        return new_version
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/suggestions/{suggestion_id}/reject", response_model=PromptSuggestionResponse)
async def reject_suggestion_endpoint(
    suggestion_id: int,
    db: Session = Depends(get_db),
):
    """Reject a suggestion."""
    try:
        suggestion = reject_suggestion(db, suggestion_id)
        return suggestion
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/analytics")
async def get_prompt_analytics(db: Session = Depends(get_db)):
    """Get prompt performance analytics."""
    prompts = db.query(PromptVersion).order_by(PromptVersion.version.desc()).all()

    analytics = []
    for prompt in prompts:
        analytics.append({
            "id": prompt.id,
            "prompt_type": prompt.prompt_type,
            "version": prompt.version,
            "is_active": prompt.is_active,
            "total_cards_generated": prompt.total_cards_generated,
            "approved_cards": prompt.approved_cards,
            "rejected_cards": prompt.rejected_cards,
            "approval_rate": prompt.approval_rate,
            "created_at": prompt.created_at,
        })

    return {"prompts": analytics}
