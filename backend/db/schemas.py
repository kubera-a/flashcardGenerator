"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class CardStatus(str, Enum):
    """Status of a flashcard in the review workflow."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class RejectionType(str, Enum):
    """Types of reasons for rejecting a card."""
    UNCLEAR = "unclear"
    INCORRECT = "incorrect"
    TOO_COMPLEX = "too_complex"
    DUPLICATE = "duplicate"
    OTHER = "other"


class SourceType(str, Enum):
    """Type of source document."""
    PDF = "pdf"
    MARKDOWN = "markdown"


# Session schemas
class SessionCreate(BaseModel):
    """Schema for creating a new session (used internally)."""
    filename: str
    llm_provider: str = "openai"


class SessionResponse(BaseModel):
    """Schema for session responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    source_type: str = "pdf"
    total_chunks: int
    processed_chunks: int
    llm_provider: str
    created_at: datetime
    completed_at: datetime | None = None
    pdf_metadata: dict | None = None


class SessionWithStats(SessionResponse):
    """Session response with card statistics."""
    card_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    pending_count: int = 0


class SessionStatusResponse(BaseModel):
    """Schema for session processing status."""
    id: int
    status: str
    total_chunks: int
    processed_chunks: int
    progress_percent: float


# Card schemas
class CardBase(BaseModel):
    """Base schema for card data."""
    front: str
    back: str
    tags: list[str] = []


class CardCreate(CardBase):
    """Schema for creating a new card."""
    session_id: int
    chunk_index: int = 0


class CardImageResponse(BaseModel):
    """Schema for card image responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    stored_filename: str
    media_type: str = "image/png"


class CardResponse(BaseModel):
    """Schema for card responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    front: str
    back: str
    tags: list[str]
    status: str
    original_front: str | None = None
    original_back: str | None = None
    chunk_index: int
    created_at: datetime
    reviewed_at: datetime | None = None
    images: list[CardImageResponse] = []


class CardEditRequest(BaseModel):
    """Schema for editing a card."""
    front: str
    back: str
    tags: list[str] | None = None


class CardRejectRequest(BaseModel):
    """Schema for rejecting a card."""
    reason: str
    rejection_type: RejectionType


class CardRejectionResponse(BaseModel):
    """Schema for card rejection records."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    reason: str
    rejection_type: str
    auto_corrected: bool
    created_at: datetime


class CardWithRejections(CardResponse):
    """Card response with rejection history."""
    rejections: list[CardRejectionResponse] = []


# Prompt schemas
class PromptVersionResponse(BaseModel):
    """Schema for prompt version responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt_type: str
    system_prompt: str
    user_prompt_template: str
    version: int
    is_active: bool
    total_cards_generated: int
    approved_cards: int
    rejected_cards: int
    approval_rate: float
    created_at: datetime


class PromptSuggestionResponse(BaseModel):
    """Schema for prompt suggestion responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt_version_id: int
    session_id: int
    suggested_system_prompt: str
    suggested_user_prompt_template: str
    reasoning: str
    rejection_patterns: dict
    status: str
    created_at: datetime
    reviewed_at: datetime | None = None


class CurrentPromptsResponse(BaseModel):
    """Schema for current active prompts."""
    generation: PromptVersionResponse | None = None
    validation: PromptVersionResponse | None = None


# Export schemas
class ExportRequest(BaseModel):
    """Schema for export requests."""
    include_tags: bool = True
    deck_name: str | None = None


class ExportResponse(BaseModel):
    """Schema for export responses."""
    filename: str
    card_count: int
    download_url: str


class ExportWithMediaResponse(BaseModel):
    """Schema for export with media files."""
    filename: str
    card_count: int
    image_count: int
    download_url: str


# Batch operation schemas
class BatchApproveRequest(BaseModel):
    """Schema for batch approve requests."""
    card_ids: list[int]


class BatchRejectRequest(BaseModel):
    """Schema for batch reject requests."""
    card_ids: list[int]
    reason: str
    rejection_type: RejectionType


class BatchOperationResponse(BaseModel):
    """Schema for batch operation responses."""
    processed: int
    failed: int
    message: str


# PDF Preview schemas
class PDFPageThumbnail(BaseModel):
    """Schema for a PDF page thumbnail."""
    page_index: int
    thumbnail: str | None = None  # Base64-encoded image


class PDFChapter(BaseModel):
    """Schema for a PDF chapter/section."""
    title: str
    start_page: int  # 0-based page index
    end_page: int  # 0-based page index (inclusive)
    level: int = 0  # Nesting level (0 = top-level chapter)


class PDFPreviewResponse(BaseModel):
    """Schema for PDF preview response."""
    session_id: int
    filename: str
    page_count: int
    file_size: int
    title: str | None = None
    author: str | None = None
    thumbnails: list[PDFPageThumbnail] = []
    chapters: list[PDFChapter] = []


class StartGenerationRequest(BaseModel):
    """Schema for starting card generation with page selection."""
    page_indices: list[int] | None = None  # If None, use all pages
    chapter_indices: list[int] | None = None  # Select by chapter (overrides page_indices)
    use_native_pdf: bool = True  # Use Claude's native PDF support if available


class ContinueGenerationRequest(BaseModel):
    """Schema for continuing card generation after review."""
    focus_areas: str | None = None  # Optional user guidance on what to focus on
    page_indices: list[int] | None = None  # Optionally specify pages to re-process


# Markdown upload schemas
class MarkdownPreviewResponse(BaseModel):
    """Schema for markdown preview response."""
    session_id: int
    filename: str
    title: str | None = None
    image_count: int
    content_preview: str
    images: list[str]  # List of image filenames
