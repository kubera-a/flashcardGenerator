import { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { sessionsApi } from '../api/client';
import type { PDFPreviewResponse, PDFPageThumbnail, MarkdownPreviewResponse } from '../types';

type UploadStep = 'upload' | 'preview' | 'generating';
type FileType = 'pdf' | 'markdown';

export default function UploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [fileType, setFileType] = useState<FileType>('pdf');
  const [llmProvider, setLlmProvider] = useState('anthropic');
  const [isDragging, setIsDragging] = useState(false);
  const [step, setStep] = useState<UploadStep>('upload');
  const [pdfPreview, setPdfPreview] = useState<PDFPreviewResponse | null>(null);
  const [markdownPreview, setMarkdownPreview] = useState<MarkdownPreviewResponse | null>(null);
  const [selectedPages, setSelectedPages] = useState<Set<number>>(new Set());
  const [useNativePdf, setUseNativePdf] = useState(true);

  // PDF upload preview
  const uploadPdfPreviewMutation = useMutation({
    mutationFn: (file: File) => sessionsApi.uploadPreview(file, llmProvider, true),
    onSuccess: (response) => {
      const previewData = response.data as PDFPreviewResponse;
      setPdfPreview(previewData);
      setSelectedPages(new Set(Array.from({ length: previewData.page_count }, (_, i) => i)));
      setStep('preview');
    },
  });

  // Markdown upload preview
  const uploadMarkdownPreviewMutation = useMutation({
    mutationFn: (file: File) => sessionsApi.uploadMarkdownPreview(file, 'anthropic'),
    onSuccess: (response) => {
      const previewData = response.data as MarkdownPreviewResponse;
      setMarkdownPreview(previewData);
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

  const detectFileType = (file: File): FileType => {
    const extension = file.name.toLowerCase().split('.').pop();
    if (extension === 'zip') return 'markdown';
    return 'pdf';
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      const type = detectFileType(droppedFile);
      if (type === 'pdf' && droppedFile.type !== 'application/pdf') return;
      setFile(droppedFile);
      setFileType(type);
      // Force anthropic for markdown
      if (type === 'markdown') {
        setLlmProvider('anthropic');
      }
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
      const type = detectFileType(selectedFile);
      setFile(selectedFile);
      setFileType(type);
      // Force anthropic for markdown
      if (type === 'markdown') {
        setLlmProvider('anthropic');
      }
    }
  };

  const handleUploadPreview = () => {
    if (file) {
      if (fileType === 'markdown') {
        uploadMarkdownPreviewMutation.mutate(file);
      } else {
        uploadPdfPreviewMutation.mutate(file);
      }
    }
  };

  const handleQuickUpload = () => {
    if (file && fileType === 'pdf') {
      uploadMutation.mutate(file);
    }
  };

  const handleStartGeneration = () => {
    if (fileType === 'markdown' && markdownPreview) {
      startGenerationMutation.mutate({
        sessionId: markdownPreview.session_id,
        pageIndices: null,
        useNativePdf: false,
      });
    } else if (pdfPreview) {
      const pageIndices = selectedPages.size === pdfPreview.page_count
        ? null
        : Array.from(selectedPages).sort((a, b) => a - b);

      startGenerationMutation.mutate({
        sessionId: pdfPreview.session_id,
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
    if (pdfPreview) {
      setSelectedPages(new Set(Array.from({ length: pdfPreview.page_count }, (_, i) => i)));
    }
  };

  const deselectAllPages = () => {
    setSelectedPages(new Set());
  };

  const handleBack = () => {
    setStep('upload');
    setPdfPreview(null);
    setMarkdownPreview(null);
    setSelectedPages(new Set());
  };

  // Markdown preview step
  if (step === 'preview' && markdownPreview) {
    return (
      <div className="upload-page">
        <div className="preview-header">
          <button className="btn btn-secondary" onClick={handleBack}>
            &larr; Back
          </button>
          <h2>Markdown Preview</h2>
        </div>

        <div className="pdf-info">
          <p><strong>File:</strong> {markdownPreview.filename}</p>
          {markdownPreview.title && <p><strong>Title:</strong> {markdownPreview.title}</p>}
          <p><strong>Images:</strong> {markdownPreview.image_count}</p>
        </div>

        <div className="markdown-preview-content">
          <h3>Content Preview:</h3>
          <pre className="content-preview">{markdownPreview.content_preview}</pre>
        </div>

        {markdownPreview.images.length > 0 && (
          <div className="image-list">
            <h3>Images ({markdownPreview.images.length}):</h3>
            <ul>
              {markdownPreview.images.slice(0, 10).map((img, idx) => (
                <li key={idx}>{img}</li>
              ))}
              {markdownPreview.images.length > 10 && (
                <li>... and {markdownPreview.images.length - 10} more</li>
              )}
            </ul>
          </div>
        )}

        <div className="generation-options">
          <p className="info-text">
            Markdown with images requires Claude (Anthropic) for multimodal processing.
          </p>
        </div>

        <div className="upload-actions">
          <button
            className="btn btn-primary btn-large"
            onClick={handleStartGeneration}
            disabled={startGenerationMutation.isPending}
          >
            {startGenerationMutation.isPending
              ? 'Starting...'
              : `Generate Cards from Markdown`}
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

  // PDF preview step
  if (step === 'preview' && pdfPreview) {
    return (
      <div className="upload-page">
        <div className="preview-header">
          <button className="btn btn-secondary" onClick={handleBack}>
            &larr; Back
          </button>
          <h2>Select Pages</h2>
        </div>

        <div className="pdf-info">
          <p><strong>File:</strong> {pdfPreview.filename}</p>
          <p><strong>Pages:</strong> {pdfPreview.page_count}</p>
          <p><strong>Size:</strong> {(pdfPreview.file_size / 1024 / 1024).toFixed(2)} MB</p>
          {pdfPreview.title && <p><strong>Title:</strong> {pdfPreview.title}</p>}
          {pdfPreview.author && <p><strong>Author:</strong> {pdfPreview.author}</p>}
        </div>

        <div className="page-selection-controls">
          <button className="btn btn-small" onClick={selectAllPages}>
            Select All
          </button>
          <button className="btn btn-small" onClick={deselectAllPages}>
            Deselect All
          </button>
          <span className="selected-count">
            {selectedPages.size} of {pdfPreview.page_count} pages selected
          </span>
        </div>

        <div className="page-grid">
          {pdfPreview.thumbnails.map((thumb: PDFPageThumbnail) => (
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

  const isLoading = uploadPdfPreviewMutation.isPending || uploadMarkdownPreviewMutation.isPending;
  const hasError = uploadPdfPreviewMutation.isError || uploadMarkdownPreviewMutation.isError || uploadMutation.isError;
  const errorMessage = uploadPdfPreviewMutation.error || uploadMarkdownPreviewMutation.error || uploadMutation.error;

  return (
    <div className="upload-page">
      <h2>Upload Document</h2>
      <p className="upload-description">
        Upload a PDF document or a ZIP file containing markdown with images.
        For markdown, create a ZIP with your .md file and an images folder.
      </p>

      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        {file ? (
          <div className="file-info">
            <span className="file-icon">{fileType === 'markdown' ? '📝' : '📄'}</span>
            <span className="file-name">{file.name}</span>
            <span className="file-size">
              ({(file.size / 1024 / 1024).toFixed(2)} MB)
            </span>
            <span className="file-type-badge">
              {fileType === 'markdown' ? 'Markdown ZIP' : 'PDF'}
            </span>
            <button
              className="btn btn-small"
              onClick={() => {
                setFile(null);
                setFileType('pdf');
              }}
            >
              Remove
            </button>
          </div>
        ) : (
          <>
            <span className="upload-icon">📁</span>
            <p>Drag and drop a PDF or ZIP file here, or click to select</p>
            <p className="upload-hint">
              PDF for documents, ZIP for markdown with images
            </p>
            <input
              type="file"
              accept=".pdf,.zip"
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
            disabled={fileType === 'markdown'}
          >
            <option value="anthropic">Anthropic (Claude) - Native PDF</option>
            <option value="openai">OpenAI (GPT-4) - Text Extraction</option>
          </select>
        </label>
        {fileType === 'markdown' && (
          <p className="info-text">
            Markdown with images requires Claude (Anthropic) for multimodal processing.
          </p>
        )}
      </div>

      <div className="upload-actions">
        <button
          className="btn btn-primary btn-large"
          onClick={handleUploadPreview}
          disabled={!file || isLoading}
        >
          {isLoading ? 'Uploading...' : 'Upload & Preview'}
        </button>
        {fileType === 'pdf' && (
          <button
            className="btn btn-secondary btn-large"
            onClick={handleQuickUpload}
            disabled={!file || uploadMutation.isPending}
          >
            {uploadMutation.isPending ? 'Uploading...' : 'Quick Generate (All Pages)'}
          </button>
        )}
      </div>

      {hasError && (
        <div className="error-message">
          Error uploading file: {String(errorMessage)}
        </div>
      )}
    </div>
  );
}
