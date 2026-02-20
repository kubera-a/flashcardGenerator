import { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sessionsApi, cardsApi, exportApi, imagesApi } from '../api/client';
import type { Card, SessionWithStats, RejectionType, AnkiConnectStatusResponse, AnkiConnectExportResponse } from '../types';

// Convert [IMAGE: filename] references to img tags
function renderWithImages(text: string, sessionId: number): React.ReactNode {
  const pattern = /\[IMAGE:\s*([^\]]+)\]/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }

    // Add the image
    const filename = match[1].trim();
    const imageUrl = imagesApi.getOriginalImageUrl(sessionId, filename);
    parts.push(
      <img
        key={key++}
        src={imageUrl}
        alt={filename}
        className="card-image"
        style={{ maxWidth: '100%', maxHeight: '400px', objectFit: 'contain', display: 'block', margin: '8px auto' }}
        onError={(e) => {
          // Try stored filename format if original fails
          const target = e.target as HTMLImageElement;
          const storedUrl = imagesApi.getImageUrl(sessionId, `${sessionId}_${filename.replace(/ /g, '_')}`);
          if (target.src !== storedUrl) {
            target.src = storedUrl;
          }
        }}
      />
    );

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return <>{parts}</>;
}

function CardItem({
  card,
  sessionId,
  onApprove,
  onReject,
  onEdit,
  onAutoCorrect,
}: {
  card: Card;
  sessionId: number;
  onApprove: (id: number) => void;
  onReject: (id: number, reason: string, type: RejectionType) => void;
  onEdit: (id: number, front: string, back: string) => void;
  onAutoCorrect: (id: number) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [editFront, setEditFront] = useState(card.front);
  const [editBack, setEditBack] = useState(card.back);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectType, setRejectType] = useState<RejectionType>('unclear');

  const handleSaveEdit = () => {
    onEdit(card.id, editFront, editBack);
    setIsEditing(false);
  };

  const handleReject = () => {
    if (rejectReason.trim()) {
      onReject(card.id, rejectReason, rejectType);
      setIsRejecting(false);
      setRejectReason('');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved': return '#10b981';
      case 'rejected': return '#ef4444';
      case 'edited': return '#3b82f6';
      default: return '#6b7280';
    }
  };

  return (
    <div className={`card-item ${card.status}`}>
      <div className="card-status-indicator" style={{ backgroundColor: getStatusColor(card.status) }}>
        {card.status}
      </div>

      {isEditing ? (
        <div className="card-edit-form">
          <label>
            Question:
            <textarea
              value={editFront}
              onChange={(e) => setEditFront(e.target.value)}
              rows={3}
            />
          </label>
          <label>
            Answer:
            <textarea
              value={editBack}
              onChange={(e) => setEditBack(e.target.value)}
              rows={3}
            />
          </label>
          <div className="edit-actions">
            <button className="btn btn-primary" onClick={handleSaveEdit}>
              Save
            </button>
            <button className="btn btn-secondary" onClick={() => setIsEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : isRejecting ? (
        <div className="card-reject-form">
          <label>
            Rejection Type:
            <select
              value={rejectType}
              onChange={(e) => setRejectType(e.target.value as RejectionType)}
            >
              <option value="unclear">Unclear question</option>
              <option value="incorrect">Incorrect information</option>
              <option value="too_complex">Too complex</option>
              <option value="duplicate">Duplicate</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label>
            Reason (for LLM to learn):
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Explain why this card should be improved..."
              rows={3}
            />
          </label>
          <div className="reject-actions">
            <button
              className="btn btn-danger"
              onClick={handleReject}
              disabled={!rejectReason.trim()}
            >
              Reject
            </button>
            <button className="btn btn-secondary" onClick={() => setIsRejecting(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="card-content">
            <div className="card-front">
              <strong>Q:</strong> {renderWithImages(card.front, sessionId)}
            </div>
            <div className="card-back">
              <strong>A:</strong> {renderWithImages(card.back, sessionId)}
            </div>
            {card.tags.length > 0 && (
              <div className="card-tags">
                {card.tags.map((tag, i) => (
                  <span key={i} className="tag">{tag}</span>
                ))}
              </div>
            )}
          </div>

          <div className="card-actions">
            {card.status === 'pending' && (
              <>
                <button
                  className="btn btn-success"
                  onClick={() => onApprove(card.id)}
                >
                  Approve
                </button>
                <button
                  className="btn btn-danger"
                  onClick={() => setIsRejecting(true)}
                >
                  Reject
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => setIsEditing(true)}
                >
                  Edit
                </button>
              </>
            )}
            {card.status === 'rejected' && (
              <>
                <button
                  className="btn btn-success"
                  onClick={() => onApprove(card.id)}
                >
                  Approve
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => onAutoCorrect(card.id)}
                >
                  Auto-Correct
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => setIsEditing(true)}
                >
                  Edit Manually
                </button>
              </>
            )}
            {(card.status === 'approved' || card.status === 'edited') && (
              <>
                <button
                  className="btn btn-danger"
                  onClick={() => setIsRejecting(true)}
                >
                  Reject
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => setIsEditing(true)}
                >
                  Edit
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function ReviewPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<string>('all');
  const [isRenamingSession, setIsRenamingSession] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef<HTMLInputElement>(null);

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      sessionsApi.rename(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
    },
  });

  useEffect(() => {
    if (isRenamingSession && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [isRenamingSession]);

  const { data: session, isLoading: sessionLoading } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: async () => {
      const response = await sessionsApi.get(Number(sessionId));
      return response.data as SessionWithStats;
    },
    refetchInterval: (query) => {
      const data = query.state.data as SessionWithStats | undefined;
      return data?.status === 'processing' ? 2000 : false;
    },
  });

  const { data: cards, isLoading: cardsLoading } = useQuery({
    queryKey: ['cards', sessionId, filter],
    queryFn: async () => {
      const status = filter === 'all' ? undefined : filter;
      const response = await cardsApi.getForSession(Number(sessionId), status);
      return response.data as Card[];
    },
    enabled: session?.status !== 'processing',
  });

  const approveMutation = useMutation({
    mutationFn: (id: number) => cardsApi.approve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cards', sessionId] });
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason, type }: { id: number; reason: string; type: RejectionType }) =>
      cardsApi.reject(id, reason, type),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cards', sessionId] });
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
    },
  });

  const editMutation = useMutation({
    mutationFn: ({ id, front, back }: { id: number; front: string; back: string }) =>
      cardsApi.edit(id, front, back),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cards', sessionId] });
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
    },
  });

  const autoCorrectMutation = useMutation({
    mutationFn: (id: number) => cardsApi.autoCorrect(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cards', sessionId] });
    },
  });

  const batchApproveMutation = useMutation({
    mutationFn: (cardIds: number[]) => cardsApi.batchApprove(cardIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cards', sessionId] });
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: () => sessionsApi.finalize(Number(sessionId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
      alert('Session finalized! Prompt suggestions will be generated based on your feedback.');
    },
  });

  const downloadCsvMutation = useMutation({
    mutationFn: async () => {
      const response = await exportApi.exportSession(Number(sessionId));
      return response.data;
    },
    onSuccess: async (data) => {
      const baseUrl = import.meta.env.DEV ? 'http://localhost:8000' : '';
      const downloadUrl = `${baseUrl}${data.download_url}`;

      // Fetch the CSV and trigger download with save dialog
      const response = await fetch(downloadUrl);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = data.filename || 'flashcards.csv';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
    onError: (error) => {
      console.error('CSV download failed:', error);
      alert('Failed to download CSV. Please try again.');
    },
  });

  const exportWithMediaMutation = useMutation({
    mutationFn: async () => {
      const response = await exportApi.exportSessionWithMedia(Number(sessionId));
      return response.data;
    },
    onSuccess: (data) => {
      alert(`Exported ${data.card_count} cards${data.image_count > 0 ? ` and ${data.image_count} images` : ''} to folder: ${data.folder_name}`);
    },
    onError: (error) => {
      console.error('Export with media failed:', error);
      alert('Failed to export with media. Please try again.');
    },
  });

  // AnkiConnect status polling
  const { data: ankiStatus } = useQuery<AnkiConnectStatusResponse>({
    queryKey: ['anki-connect-status'],
    queryFn: async () => {
      const response = await exportApi.ankiConnectStatus();
      return response.data;
    },
    refetchInterval: 30000,
    enabled: (session?.card_count ?? 0) - (session?.rejected_count ?? 0) > 0,
  });

  const sendToAnkiMutation = useMutation<AnkiConnectExportResponse>({
    mutationFn: async () => {
      const response = await exportApi.sendToAnki(Number(sessionId));
      return response.data;
    },
    onSuccess: (data) => {
      if (data.success) {
        alert(`Sent ${data.cards_sent} cards to Anki deck "${data.deck_name}"${data.images_sent > 0 ? ` with ${data.images_sent} images` : ''}.`);
      } else {
        alert(`Sent ${data.cards_sent} cards to Anki deck "${data.deck_name}".\n${data.errors.join('\n')}`);
      }
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail || 'Failed to send to Anki. Is Anki running with AnkiConnect?';
      alert(detail);
    },
  });

  // Check if session has images (markdown session)
  const hasImages = session?.source_type === 'markdown' ||
    (session?.pdf_metadata as Record<string, unknown> | null)?.image_count;

  if (sessionLoading) {
    return <div className="loading">Loading session...</div>;
  }

  if (!session) {
    return <div className="error">Session not found</div>;
  }

  const progress = session.total_chunks > 0
    ? Math.round((session.processed_chunks / session.total_chunks) * 100)
    : 0;

  return (
    <div className="review-page">
      <div className="review-header">
        <div className="header-info">
          <button className="btn btn-secondary" onClick={() => navigate('/')}>
            ← Back
          </button>
          {isRenamingSession ? (
            <input
              ref={renameInputRef}
              className="session-name-input"
              style={{ fontSize: '1.5rem' }}
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onBlur={() => {
                const trimmed = renameValue.trim();
                if (trimmed && trimmed !== (session.display_name || session.filename)) {
                  renameMutation.mutate({ id: session.id, name: trimmed });
                }
                setIsRenamingSession(false);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  (e.target as HTMLInputElement).blur();
                } else if (e.key === 'Escape') {
                  setRenameValue(session.display_name || session.filename);
                  setIsRenamingSession(false);
                }
              }}
            />
          ) : (
            <div className="session-name-row">
              <h2>{session.display_name || session.filename}</h2>
              <button
                className="btn-icon"
                onClick={() => {
                  setRenameValue(session.display_name || session.filename);
                  setIsRenamingSession(true);
                }}
                title="Rename session"
              >
                &#9998;
              </button>
            </div>
          )}
          <span className={`status-badge ${session.status}`}>{session.status}</span>
        </div>

        <div className="header-stats">
          <span className="stat">
            <strong>{session.card_count}</strong> Total
          </span>
          <span className="stat approved">
            <strong>{session.approved_count}</strong> Approved
          </span>
          <span className="stat rejected">
            <strong>{session.rejected_count}</strong> Rejected
          </span>
          <span className="stat pending">
            <strong>{session.pending_count}</strong> Pending
          </span>
        </div>

        <div className="header-actions">
          {session.pending_count > 0 && (
            <button
              className="btn btn-success"
              onClick={() => {
                if (confirm(`Approve all ${session.pending_count} pending cards?`)) {
                  const pendingCards = cards?.filter(c => c.status === 'pending').map(c => c.id) || [];
                  if (pendingCards.length > 0) {
                    batchApproveMutation.mutate(pendingCards);
                  }
                }
              }}
              disabled={batchApproveMutation.isPending}
            >
              {batchApproveMutation.isPending ? 'Approving...' : `Approve All (${session.pending_count})`}
            </button>
          )}
          {session.status !== 'finalized' && session.pending_count === 0 && session.card_count > 0 && (
            <button
              className="btn btn-primary"
              onClick={() => finalizeMutation.mutate()}
              disabled={finalizeMutation.isPending}
            >
              {finalizeMutation.isPending ? 'Finalizing...' : 'Finalize Session'}
            </button>
          )}
          {(session.card_count - session.rejected_count > 0) && (
            <>
              <button
                className="btn btn-primary"
                onClick={() => sendToAnkiMutation.mutate()}
                disabled={sendToAnkiMutation.isPending || !ankiStatus?.available}
                title={ankiStatus?.available ? 'Send cards directly to Anki via AnkiConnect' : 'Anki is not running or AnkiConnect is not installed'}
              >
                {sendToAnkiMutation.isPending ? 'Sending...' : 'Send to Anki'}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => downloadCsvMutation.mutate()}
                disabled={downloadCsvMutation.isPending}
              >
                {downloadCsvMutation.isPending ? 'Downloading...' : 'Download CSV'}
              </button>
              {hasImages && (
                <button
                  className="btn btn-secondary"
                  onClick={() => exportWithMediaMutation.mutate()}
                  disabled={exportWithMediaMutation.isPending}
                >
                  {exportWithMediaMutation.isPending ? 'Exporting...' : 'Export with Images'}
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {session.status === 'processing' && (
        <div className="processing-status">
          <p>Processing PDF and generating flashcards...</p>
          <div className="progress-bar large">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <p className="progress-text">
            {session.processed_chunks} / {session.total_chunks} chunks processed ({progress}%)
          </p>
        </div>
      )}

      {session.status !== 'processing' && (
        <>
          <div className="filter-bar">
            <label>Filter:</label>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">All Cards</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="edited">Edited</option>
            </select>
          </div>

          {cardsLoading ? (
            <div className="loading">Loading cards...</div>
          ) : cards?.length === 0 ? (
            <div className="empty-state">
              <p>No cards match the current filter.</p>
            </div>
          ) : (
            <div className="cards-list">
              {cards?.map((card) => (
                <CardItem
                  key={card.id}
                  card={card}
                  sessionId={Number(sessionId)}
                  onApprove={(id) => approveMutation.mutate(id)}
                  onReject={(id, reason, type) => rejectMutation.mutate({ id, reason, type })}
                  onEdit={(id, front, back) => editMutation.mutate({ id, front, back })}
                  onAutoCorrect={(id) => autoCorrectMutation.mutate(id)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
