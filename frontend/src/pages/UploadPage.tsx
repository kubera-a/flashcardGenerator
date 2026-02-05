import { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { sessionsApi } from '../api/client';
import type { PDFPreviewResponse, PDFPageThumbnail } from '../types';

type UploadStep = 'upload' | 'preview' | 'generating';

export default function UploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [llmProvider, setLlmProvider] = useState('anthropic');
  const [isDragging, setIsDragging] = useState(false);
  const [step, setStep] = useState<UploadStep>('upload');
  const [preview, setPreview] = useState<PDFPreviewResponse | null>(null);
  const [selectedPages, setSelectedPages] = useState<Set<number>>(new Set());
  const [useNativePdf, setUseNativePdf] = useState(true);

  const uploadPreviewMutation = useMutation({
    mutationFn: (file: File) => sessionsApi.uploadPreview(file, llmProvider, true),
    onSuccess: (response) => {
      const previewData = response.data as PDFPreviewResponse;
      setPreview(previewData);
      // Select all pages by default
      setSelectedPages(new Set(Array.from({ length: previewData.page_count }, (_, i) => i)));
      setStep('preview');
    },
  });

  const startGenerationMutation = useMutation({
    mutationFn: ({ sessionId, pageIndices, useNativePdf }: { sessionId: number; pageIndices: number[] | null; useNativePdf: boolean }) =>
      sessionsApi.startGeneration(sessionId, pageIndices, useNativePdf),
    onSuccess: (response) => {
      navigate(`/review/${response.data.id}`);
    },
  });

  // Legacy upload for quick generation
  const uploadMutation = useMutation({
    mutationFn: (file: File) => sessionsApi.upload(file, llmProvider),
    onSuccess: (response) => {
      navigate(`/review/${response.data.id}`);
    },
  });

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile?.type === 'application/pdf') {
      setFile(droppedFile);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
    }
  };

  const handleUploadPreview = () => {
    if (file) {
      uploadPreviewMutation.mutate(file);
    }
  };

  const handleQuickUpload = () => {
    if (file) {
      uploadMutation.mutate(file);
    }
  };

  const handleStartGeneration = () => {
    if (preview) {
      const pageIndices = selectedPages.size === preview.page_count
        ? null  // Use all pages
        : Array.from(selectedPages).sort((a, b) => a - b);

      startGenerationMutation.mutate({
        sessionId: preview.session_id,
        pageIndices,
        useNativePdf,
      });
    }
  };

  const togglePage = (pageIndex: number) => {
    const newSelected = new Set(selectedPages);
    if (newSelected.has(pageIndex)) {
      newSelected.delete(pageIndex);
    } else {
      newSelected.add(pageIndex);
    }
    setSelectedPages(newSelected);
  };

  const selectAllPages = () => {
    if (preview) {
      setSelectedPages(new Set(Array.from({ length: preview.page_count }, (_, i) => i)));
    }
  };

  const deselectAllPages = () => {
    setSelectedPages(new Set());
  };

  const handleBack = () => {
    setStep('upload');
    setPreview(null);
    setSelectedPages(new Set());
  };

  if (step === 'preview' && preview) {
    return (
      <div className="upload-page">
        <div className="preview-header">
          <button className="btn btn-secondary" onClick={handleBack}>
            &larr; Back
          </button>
          <h2>Select Pages</h2>
        </div>

        <div className="pdf-info">
          <p><strong>File:</strong> {preview.filename}</p>
          <p><strong>Pages:</strong> {preview.page_count}</p>
          <p><strong>Size:</strong> {(preview.file_size / 1024 / 1024).toFixed(2)} MB</p>
          {preview.title && <p><strong>Title:</strong> {preview.title}</p>}
          {preview.author && <p><strong>Author:</strong> {preview.author}</p>}
        </div>

        <div className="page-selection-controls">
          <button className="btn btn-small" onClick={selectAllPages}>
            Select All
          </button>
          <button className="btn btn-small" onClick={deselectAllPages}>
            Deselect All
          </button>
          <span className="selected-count">
            {selectedPages.size} of {preview.page_count} pages selected
          </span>
        </div>

        <div className="page-grid">
          {preview.thumbnails.map((thumb: PDFPageThumbnail) => (
            <div
              key={thumb.page_index}
              className={`page-thumbnail ${selectedPages.has(thumb.page_index) ? 'selected' : ''}`}
              onClick={() => togglePage(thumb.page_index)}
            >
              {thumb.thumbnail ? (
                <img src={thumb.thumbnail} alt={`Page ${thumb.page_index + 1}`} />
              ) : (
                <div className="thumbnail-placeholder">
                  Page {thumb.page_index + 1}
                </div>
              )}
              <div className="page-number">Page {thumb.page_index + 1}</div>
              <div className="page-checkbox">
                {selectedPages.has(thumb.page_index) ? '✓' : ''}
              </div>
            </div>
          ))}
        </div>

        <div className="generation-options">
          <label className="option-label">
            <span>LLM Provider:</span>
            <select
              value={llmProvider}
              onChange={(e) => setLlmProvider(e.target.value)}
              className="select-input"
            >
              <option value="anthropic">Anthropic (Claude) - Native PDF</option>
              <option value="openai">OpenAI (GPT-4) - Text Extraction</option>
            </select>
          </label>

          {llmProvider === 'anthropic' && (
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={useNativePdf}
                onChange={(e) => setUseNativePdf(e.target.checked)}
              />
              <span>Use Claude's native PDF support (recommended)</span>
            </label>
          )}
        </div>

        <div className="upload-actions">
          <button
            className="btn btn-primary btn-large"
            onClick={handleStartGeneration}
            disabled={selectedPages.size === 0 || startGenerationMutation.isPending}
          >
            {startGenerationMutation.isPending
              ? 'Starting...'
              : `Generate Cards from ${selectedPages.size} Pages`}
          </button>
        </div>

        {startGenerationMutation.isError && (
          <div className="error-message">
            Error starting generation: {String(startGenerationMutation.error)}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="upload-page">
      <h2>Upload PDF</h2>
      <p className="upload-description">
        Upload a PDF document to generate Anki flashcards. You can select which
        pages to process and choose your preferred LLM provider.
      </p>

      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        {file ? (
          <div className="file-info">
            <span className="file-icon">📄</span>
            <span className="file-name">{file.name}</span>
            <span className="file-size">
              ({(file.size / 1024 / 1024).toFixed(2)} MB)
            </span>
            <button
              className="btn btn-small"
              onClick={() => setFile(null)}
            >
              Remove
            </button>
          </div>
        ) : (
          <>
            <span className="upload-icon">📁</span>
            <p>Drag and drop a PDF here, or click to select</p>
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileSelect}
              className="file-input"
            />
          </>
        )}
      </div>

      <div className="upload-options">
        <label className="option-label">
          <span>LLM Provider:</span>
          <select
            value={llmProvider}
            onChange={(e) => setLlmProvider(e.target.value)}
            className="select-input"
          >
            <option value="anthropic">Anthropic (Claude) - Native PDF</option>
            <option value="openai">OpenAI (GPT-4) - Text Extraction</option>
          </select>
        </label>
      </div>

      <div className="upload-actions">
        <button
          className="btn btn-primary btn-large"
          onClick={handleUploadPreview}
          disabled={!file || uploadPreviewMutation.isPending}
        >
          {uploadPreviewMutation.isPending ? 'Loading Preview...' : 'Select Pages'}
        </button>
        <button
          className="btn btn-secondary btn-large"
          onClick={handleQuickUpload}
          disabled={!file || uploadMutation.isPending}
        >
          {uploadMutation.isPending ? 'Uploading...' : 'Quick Generate (All Pages)'}
        </button>
      </div>

      {(uploadPreviewMutation.isError || uploadMutation.isError) && (
        <div className="error-message">
          Error uploading file: {String(uploadPreviewMutation.error || uploadMutation.error)}
        </div>
      )}
    </div>
  );
}
