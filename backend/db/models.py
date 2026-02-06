"""SQLAlchemy ORM models for the flashcard generator."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class CardStatus(str, PyEnum):
    """Status of a flashcard in the review workflow."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class SessionStatus(str, PyEnum):
    """Status of a card generation session."""
    PENDING = "pending"  # Uploaded but not started
    PROCESSING = "processing"
    READY = "ready"
    REVIEWING = "reviewing"
    FINALIZED = "finalized"
    FAILED = "failed"


class SourceType(str, PyEnum):
    """Type of source document."""
    PDF = "pdf"
    MARKDOWN = "markdown"


class PromptType(str, PyEnum):
    """Type of prompt (generation or validation)."""
    GENERATION = "generation"
    VALIDATION = "validation"


class Session(Base):
    """Represents a PDF/markdown upload and card generation session."""
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(
        String(50), default=SourceType.PDF.value
    )
    pdf_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default=SessionStatus.PROCESSING.value
    )
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    processed_chunks: Mapped[int] = mapped_column(Integer, default=0)
    llm_provider: Mapped[str] = mapped_column(String(50), default="openai")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Foreign key to prompt version used for this session
    prompt_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("prompt_versions.id"), nullable=True
    )

    # Relationships
    cards: Mapped[list["Card"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    prompt_version: Mapped[Optional["PromptVersion"]] = relationship()


class Card(Base):
    """Represents a single flashcard."""
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default=CardStatus.PENDING.value)
    original_front: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_back: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    session: Mapped["Session"] = relationship(back_populates="cards")
    rejections: Mapped[list["CardRejection"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )
    images: Mapped[list["CardImage"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )


class CardImage(Base):
    """Represents an image associated with a flashcard."""
    __tablename__ = "card_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    original_filename: Mapped[str] = mapped_column(String(500))
    stored_filename: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(100), default="image/png")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    card: Mapped["Card"] = relationship(back_populates="images")


class CardRejection(Base):
    """Records a rejection event for a card with the user's reasoning."""
    __tablename__ = "card_rejections"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    reason: Mapped[str] = mapped_column(Text)
    rejection_type: Mapped[str] = mapped_column(String(50))
    auto_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    card: Mapped["Card"] = relationship(back_populates="rejections")


class PromptVersion(Base):
    """Stores versions of prompts used for card generation/validation."""
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_type: Mapped[str] = mapped_column(String(50))
    system_prompt: Mapped[str] = mapped_column(Text)
    user_prompt_template: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("prompt_versions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Performance metrics
    total_cards_generated: Mapped[int] = mapped_column(Integer, default=0)
    approved_cards: Mapped[int] = mapped_column(Integer, default=0)
    rejected_cards: Mapped[int] = mapped_column(Integer, default=0)
    approval_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    suggestions: Mapped[list["PromptSuggestion"]] = relationship(
        back_populates="prompt_version"
    )


class PromptSuggestion(Base):
    """Stores LLM-generated suggestions for prompt improvements."""
    __tablename__ = "prompt_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_version_id: Mapped[int] = mapped_column(ForeignKey("prompt_versions.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    suggested_system_prompt: Mapped[str] = mapped_column(Text)
    suggested_user_prompt_template: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    rejection_patterns: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    prompt_version: Mapped["PromptVersion"] = relationship(back_populates="suggestions")
