"""Service for managing prompt versions and evolution."""

from sqlalchemy.orm import Session

from backend.db.database import SessionLocal
from backend.db.models import PromptType, PromptVersion
from config.prompts import GENERATION_PROMPT, VALIDATION_PROMPT


def seed_initial_prompts() -> None:
    """Seed the database with initial prompts from config/prompts.py if not present."""
    db = SessionLocal()
    try:
        # Check if prompts already exist
        existing = db.query(PromptVersion).first()
        if existing:
            return

        # Seed generation prompt (SuperMemo's 20 Rules based)
        gen_prompt = PromptVersion(
            prompt_type=PromptType.GENERATION.value,
            system_prompt=GENERATION_PROMPT.system_prompt,
            user_prompt_template=GENERATION_PROMPT.user_prompt_template,
            version=1,
            is_active=True,
        )
        db.add(gen_prompt)

        # Seed validation prompt
        val_prompt = PromptVersion(
            prompt_type=PromptType.VALIDATION.value,
            system_prompt=VALIDATION_PROMPT.system_prompt,
            user_prompt_template=VALIDATION_PROMPT.user_prompt_template,
            version=1,
            is_active=True,
        )
        db.add(val_prompt)

        db.commit()
    finally:
        db.close()


def get_active_prompt(db: Session, prompt_type: PromptType) -> PromptVersion | None:
    """Get the currently active prompt for a given type."""
    return (
        db.query(PromptVersion)
        .filter(
            PromptVersion.prompt_type == prompt_type.value,
            PromptVersion.is_active.is_(True),
        )
        .first()
    )


def get_active_prompts(db: Session) -> dict:
    """Get both active generation and validation prompts."""
    return {
        "generation": get_active_prompt(db, PromptType.GENERATION),
        "validation": get_active_prompt(db, PromptType.VALIDATION),
    }


def update_prompt_metrics(
    db: Session,
    prompt_version_id: int,
    cards_generated: int = 0,
    approved: int = 0,
    rejected: int = 0,
) -> None:
    """Update performance metrics for a prompt version."""
    prompt = db.query(PromptVersion).filter(PromptVersion.id == prompt_version_id).first()
    if prompt:
        prompt.total_cards_generated += cards_generated
        prompt.approved_cards += approved
        prompt.rejected_cards += rejected
        total = prompt.approved_cards + prompt.rejected_cards
        if total > 0:
            prompt.approval_rate = prompt.approved_cards / total
        db.commit()
