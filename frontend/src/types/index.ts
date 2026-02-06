// API Types

export type CardStatus = 'pending' | 'approved' | 'rejected' | 'edited';
export type RejectionType = 'unclear' | 'incorrect' | 'too_complex' | 'duplicate' | 'other';
export type SourceType = 'pdf' | 'markdown';

export interface Session {
  id: number;
  filename: string;
  status: string;
  source_type: SourceType;
  total_chunks: number;
  processed_chunks: number;
  llm_provider: string;
  created_at: string;
  completed_at: string | null;
  pdf_metadata: Record<string, unknown> | null;
}

export interface SessionWithStats extends Session {
  card_count: number;
  approved_count: number;
  rejected_count: number;
  pending_count: number;
}

export interface SessionStatus {
  id: number;
  status: string;
  total_chunks: number;
  processed_chunks: number;
  progress_percent: number;
}

export interface CardImage {
  id: number;
  original_filename: string;
  stored_filename: string;
  media_type: string;
}

export interface Card {
  id: number;
  session_id: number;
  front: string;
  back: string;
  tags: string[];
  status: CardStatus;
  original_front: string | null;
  original_back: string | null;
  chunk_index: number;
  created_at: string;
  reviewed_at: string | null;
  images: CardImage[];
}

export interface CardRejection {
  id: number;
  card_id: number;
  reason: string;
  rejection_type: string;
  auto_corrected: boolean;
  created_at: string;
}

export interface CardWithRejections extends Card {
  rejections: CardRejection[];
}

export interface CardRejectRequest {
  reason: string;
  rejection_type: RejectionType;
}

export interface CardEditRequest {
  front: string;
  back: string;
  tags?: string[];
}

export interface PromptVersion {
  id: number;
  prompt_type: string;
  system_prompt: string;
  user_prompt_template: string;
  version: number;
  is_active: boolean;
  total_cards_generated: number;
  approved_cards: number;
  rejected_cards: number;
  approval_rate: number;
  created_at: string;
}

export interface PromptSuggestion {
  id: number;
  prompt_version_id: number;
  session_id: number;
  suggested_system_prompt: string;
  suggested_user_prompt_template: string;
  reasoning: string;
  rejection_patterns: Record<string, unknown>;
  status: string;
  created_at: string;
  reviewed_at: string | null;
}

export interface CurrentPrompts {
  generation: PromptVersion | null;
  validation: PromptVersion | null;
}

export interface ExportResponse {
  filename: string;
  card_count: number;
  download_url: string;
}

export interface ExportWithMediaResponse {
  filename: string;
  card_count: number;
  image_count: number;
  download_url: string;
}

export interface BatchOperationResponse {
  processed: number;
  failed: number;
  message: string;
}

// PDF Preview Types
export interface PDFPageThumbnail {
  page_index: number;
  thumbnail: string | null;
}

export interface PDFPreviewResponse {
  session_id: number;
  filename: string;
  page_count: number;
  file_size: number;
  title: string | null;
  author: string | null;
  thumbnails: PDFPageThumbnail[];
}

export interface StartGenerationRequest {
  page_indices: number[] | null;
  use_native_pdf: boolean;
}

// Markdown Preview Types
export interface MarkdownPreviewResponse {
  session_id: number;
  filename: string;
  title: string | null;
  image_count: number;
  content_preview: string;
  images: string[];
}
