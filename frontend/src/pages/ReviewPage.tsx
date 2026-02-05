import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sessionsApi, cardsApi, exportApi } from '../api/client';
import type { Card, SessionWithStats, RejectionType } from '../types';

function CardItem({
  card,
  onApprove,
  onReject,
  onEdit,
  onAutoCorrect,
}: {
  card: Card;
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
              <strong>Q:</strong> {card.front}
            </div>
            <div className="card-back">
              <strong>A:</strong> {card.back}
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
              <button
                className="btn btn-secondary"
                onClick={() => setIsEditing(true)}
              >
                Edit
              </button>
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

  const finalizeMutation = useMutation({
    mutationFn: () => sessionsApi.finalize(Number(sessionId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
      alert('Session finalized! Prompt suggestions will be generated based on your feedback.');
    },
  });

  const exportMutation = useMutation({
    mutationFn: () => exportApi.exportSession(Number(sessionId)),
    onSuccess: (response) => {
      // Use relative URL in production, absolute in development
      const baseUrl = import.meta.env.DEV ? 'http://localhost:8000' : '';
      const downloadUrl = `${baseUrl}${response.data.download_url}`;
      window.open(downloadUrl, '_blank');
    },
  });

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
          <h2>{session.filename}</h2>
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
          {session.status !== 'finalized' && session.pending_count === 0 && session.card_count > 0 && (
            <button
              className="btn btn-primary"
              onClick={() => finalizeMutation.mutate()}
              disabled={finalizeMutation.isPending}
            >
              {finalizeMutation.isPending ? 'Finalizing...' : 'Finalize Session'}
            </button>
          )}
          {(session.approved_count > 0) && (
            <button
              className="btn btn-secondary"
              onClick={() => exportMutation.mutate()}
              disabled={exportMutation.isPending}
            >
              {exportMutation.isPending ? 'Exporting...' : 'Export to Anki'}
            </button>
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
