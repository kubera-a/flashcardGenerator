"""Service for analyzing feedback and evolving prompts."""

import json
import logging
from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from backend.db.database import SessionLocal
from backend.db.models import (
    Card,
    CardRejection,
    CardStatus,
    PromptSuggestion,
    PromptType,
    PromptVersion,
)
from backend.db.models import (
    Session as DBSession,
)
from backend.services.prompt_service import get_active_prompt
from modules.llm_interface import LLMInterface

logger = logging.getLogger(__name__)


def analyze_session_and_generate_suggestion(
    session_id: int,
    llm_provider: str = "openai",
    db: Session | None = None,
) -> PromptSuggestion | None:
    """
    Analyze all cards from a session and generate prompt improvement suggestions.
    Called after a session is finalized.

    Note: This function creates its own database session for use in background tasks.
    The db parameter is deprecated and ignored.
    """
    # Create our own database session for background task
    db = SessionLocal()

    try:
        session = db.query(DBSession).filter(DBSession.id == session_id).first()
        if not session:
            logger.error(f"Session {session_id} not found")
            return None

        # Get all cards and rejections for this session
        cards = db.query(Card).filter(Card.session_id == session_id).all()
        if not cards:
            logger.info(f"No cards found for session {session_id}")
            return None

        # Categorize cards
        approved_cards = [c for c in cards if c.status == CardStatus.APPROVED.value]
        rejected_cards = [c for c in cards if c.status == CardStatus.REJECTED.value]
        edited_cards = [c for c in cards if c.status == CardStatus.EDITED.value]

        # If no rejections, no need to suggest improvements
        if not rejected_cards and not edited_cards:
            logger.info(f"No rejected or edited cards for session {session_id}")
            return None

        # Analyze rejection patterns
        rejection_patterns = _analyze_rejection_patterns(db, rejected_cards)

        # Get current active prompt
        gen_prompt = get_active_prompt(db, PromptType.GENERATION)
        if not gen_prompt:
            logger.error("No active generation prompt found")
            return None

        # Generate suggestion using LLM
        suggestion_data = _generate_prompt_improvement(
            llm_provider=llm_provider,
            current_prompt=gen_prompt,
            rejection_patterns=rejection_patterns,
            approved_examples=approved_cards[:5],
            rejected_examples=rejected_cards[:5],
            edited_examples=edited_cards[:5],
        )

        if not suggestion_data:
            return None

        # Create suggestion record
        suggestion = PromptSuggestion(
            prompt_version_id=gen_prompt.id,
            session_id=session_id,
            suggested_system_prompt=suggestion_data["suggested_system_prompt"],
            suggested_user_prompt_template=suggestion_data["suggested_user_prompt_template"],
            reasoning=suggestion_data["reasoning"],
            rejection_patterns=rejection_patterns,
            status="pending",
        )
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)

        return suggestion

    except Exception as e:
        logger.error(f"Error analyzing session {session_id}: {e}", exc_info=True)
        return None
    finally:
        db.close()


def _analyze_rejection_patterns(db: Session, rejected_cards: list[Card]) -> dict:
    """Analyze patterns in rejection reasons."""
    if not rejected_cards:
        return {}

    card_ids = [c.id for c in rejected_cards]
    rejections = (
        db.query(CardRejection)
        .filter(CardRejection.card_id.in_(card_ids))
        .all()
    )

    # Count rejection types
    type_counts = Counter(r.rejection_type for r in rejections)

    # Group reasons by type
    reasons_by_type = {}
    for r in rejections:
        if r.rejection_type not in reasons_by_type:
            reasons_by_type[r.rejection_type] = []
        reasons_by_type[r.rejection_type].append(r.reason)

    return {
        "total_rejections": len(rejections),
        "type_distribution": dict(type_counts),
        "sample_reasons": {k: v[:3] for k, v in reasons_by_type.items()},
    }


def _generate_prompt_improvement(
    llm_provider: str,
    current_prompt: PromptVersion,
    rejection_patterns: dict,
    approved_examples: list[Card],
    rejected_examples: list[Card],
    edited_examples: list[Card],
) -> dict | None:
    """Use LLM to generate prompt improvement suggestions."""
    # Format examples
    approved_str = "\n".join(
        f"Q: {c.front}\nA: {c.back}"
        for c in approved_examples
    ) if approved_examples else "None"

    rejected_str = "\n".join(
        f"Q: {c.front}\nA: {c.back}"
        for c in rejected_examples
    ) if rejected_examples else "None"

    edited_str = "\n".join(
        f"Original Q: {c.original_front or c.front}\n"
        f"Original A: {c.original_back or c.back}\n"
        f"Edited Q: {c.front}\n"
        f"Edited A: {c.back}"
        for c in edited_examples
    ) if edited_examples else "None"

    analysis_prompt = f"""
    Analyze the following flashcard generation results and suggest improvements to the generation prompt.

    ## Current System Prompt:
    {current_prompt.system_prompt}

    ## Current User Prompt Template:
    {current_prompt.user_prompt_template}

    ## Rejection Patterns Found:
    {json.dumps(rejection_patterns, indent=2)}

    ## Examples of APPROVED cards (good quality):
    {approved_str}

    ## Examples of REJECTED cards (poor quality):
    {rejected_str}

    ## Examples of EDITED cards (showing what users corrected):
    {edited_str}

    Based on this analysis, provide:
    1. Specific issues identified with the current prompts
    2. An improved system prompt that addresses these issues
    3. An improved user prompt template that addresses these issues

    Return ONLY valid JSON with these exact keys:
    {{
        "reasoning": "explanation of issues found and changes made",
        "suggested_system_prompt": "the improved system prompt",
        "suggested_user_prompt_template": "the improved user prompt template"
    }}
    """

    system_prompt = """
    You are an expert in prompt engineering and educational content design.
    Analyze the flashcard generation results and suggest concrete improvements
    to the prompts used for generation. Focus on patterns in rejections and
    how cards were edited to understand what users want.
    Return only valid JSON.
    """

    try:
        llm = LLMInterface(provider=llm_provider)
        response = llm.generate_structured_output(
            prompt=analysis_prompt,
            output_format={
                "reasoning": "string",
                "suggested_system_prompt": "string",
                "suggested_user_prompt_template": "string",
            },
            system_prompt=system_prompt,
        )
        return response

    except Exception as e:
        logger.error(f"Error generating prompt improvement: {e}")
        return None


def approve_suggestion(db: Session, suggestion_id: int) -> PromptVersion:
    """Approve a suggestion and create a new prompt version."""
    suggestion = (
        db.query(PromptSuggestion)
        .filter(PromptSuggestion.id == suggestion_id)
        .first()
    )
    if not suggestion:
        raise ValueError(f"Suggestion {suggestion_id} not found")

    # Get current active prompt to determine version number
    current = (
        db.query(PromptVersion)
        .filter(PromptVersion.id == suggestion.prompt_version_id)
        .first()
    )
    if not current:
        raise ValueError("Parent prompt version not found")

    # Get highest version number for this prompt type
    max_version = (
        db.query(PromptVersion)
        .filter(PromptVersion.prompt_type == current.prompt_type)
        .order_by(PromptVersion.version.desc())
        .first()
    )
    new_version = (max_version.version + 1) if max_version else 1

    # Deactivate all prompts of this type
    db.query(PromptVersion).filter(
        PromptVersion.prompt_type == current.prompt_type
    ).update({"is_active": False})

    # Create new prompt version
    new_prompt = PromptVersion(
        prompt_type=current.prompt_type,
        system_prompt=suggestion.suggested_system_prompt,
        user_prompt_template=suggestion.suggested_user_prompt_template,
        version=new_version,
        is_active=True,
        parent_version_id=current.id,
    )
    db.add(new_prompt)

    # Update suggestion status
    suggestion.status = "approved"
    suggestion.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(new_prompt)
    return new_prompt


def reject_suggestion(db: Session, suggestion_id: int) -> PromptSuggestion:
    """Reject a suggestion."""
    suggestion = (
        db.query(PromptSuggestion)
        .filter(PromptSuggestion.id == suggestion_id)
        .first()
    )
    if not suggestion:
        raise ValueError(f"Suggestion {suggestion_id} not found")

    suggestion.status = "rejected"
    suggestion.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(suggestion)
    return suggestion


def get_pending_suggestions(db: Session) -> list[PromptSuggestion]:
    """Get all pending prompt suggestions."""
    return (
        db.query(PromptSuggestion)
        .filter(PromptSuggestion.status == "pending")
        .order_by(PromptSuggestion.created_at.desc())
        .all()
    )


def get_prompt_history(db: Session, prompt_type: str | None = None) -> list[PromptVersion]:
    """Get prompt version history."""
    query = db.query(PromptVersion)
    if prompt_type:
        query = query.filter(PromptVersion.prompt_type == prompt_type)
    return query.order_by(PromptVersion.version.desc()).all()
