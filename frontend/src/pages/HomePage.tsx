import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { sessionsApi, exportApi } from '../api/client';
import type { SessionWithStats } from '../types';

function SessionCard({ session, onDelete, onExport, onRename }: {
  session: SessionWithStats;
  onDelete: (id: number) => void;
  onExport: (id: number) => void;
  onRename: (id: number, name: string) => void;
}) {
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(session.display_name || session.filename);
  const inputRef = useRef<HTMLInputElement>(null);
  const progress = session.total_chunks > 0
    ? Math.round((session.processed_chunks / session.total_chunks) * 100)
    : 0;

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleRenameSubmit = () => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== (session.display_name || session.filename)) {
      onRename(session.id, trimmed);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleRenameSubmit();
    } else if (e.key === 'Escape') {
      setEditValue(session.display_name || session.filename);
      setIsEditing(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'processing': return '#f59e0b';
      case 'ready': return '#10b981';
      case 'reviewing': return '#3b82f6';
      case 'finalized': return '#8b5cf6';
      case 'failed': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const displayName = session.display_name || session.filename;

  return (
    <div className="session-card">
      <div className="session-header">
        {isEditing ? (
          <input
            ref={inputRef}
            className="session-name-input"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={handleRenameSubmit}
            onKeyDown={handleKeyDown}
          />
        ) : (
          <div className="session-name-row">
            <h3>{displayName}</h3>
            <button
              className="btn-icon"
              onClick={() => {
                setEditValue(displayName);
                setIsEditing(true);
              }}
              title="Rename session"
            >
              &#9998;
            </button>
          </div>
        )}
        <span
          className="status-badge"
          style={{ backgroundColor: getStatusColor(session.status) }}
        >
          {session.status}
        </span>
      </div>

      {session.status === 'processing' && (
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
          <span className="progress-text">{progress}%</span>
        </div>
      )}

      <div className="session-stats">
        <div className="stat">
          <span className="stat-value">{session.card_count}</span>
          <span className="stat-label">Total Cards</span>
        </div>
        <div className="stat">
          <span className="stat-value approved">{session.approved_count}</span>
          <span className="stat-label">Approved</span>
        </div>
        <div className="stat">
          <span className="stat-value rejected">{session.rejected_count}</span>
          <span className="stat-label">Rejected</span>
        </div>
        <div className="stat">
          <span className="stat-value pending">{session.pending_count}</span>
          <span className="stat-label">Pending</span>
        </div>
      </div>

      <div className="session-meta">
        <span>Provider: {session.llm_provider}</span>
        <span>Created: {new Date(session.created_at).toLocaleDateString()}</span>
      </div>

      <div className="session-actions">
        {(session.status === 'ready' || session.status === 'reviewing' || session.status === 'finalized') && (
          <button
            className="btn btn-primary"
            onClick={() => navigate(`/review/${session.id}`)}
          >
            {session.status === 'finalized' ? 'View Cards' : 'Review Cards'}
          </button>
        )}
        {(session.card_count - session.rejected_count > 0 || session.status === 'finalized') && (
          <button
            className="btn btn-secondary"
            onClick={() => onExport(session.id)}
          >
            Export to Anki
          </button>
        )}
        <button
          className="btn btn-danger"
          onClick={() => onDelete(session.id)}
        >
          Delete
        </button>
      </div>
    </div>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: sessions, isLoading, error } = useQuery({
    queryKey: ['sessions'],
    queryFn: async () => {
      const response = await sessionsApi.list();
      return response.data as SessionWithStats[];
    },
    refetchInterval: 5000, // Poll for updates
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      sessionsApi.rename(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => sessionsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });

  const exportMutation = useMutation({
    mutationFn: (id: number) => exportApi.exportSession(id),
    onSuccess: (response) => {
      // Trigger download
      const downloadUrl = `http://localhost:8000${response.data.download_url}`;
      window.open(downloadUrl, '_blank');
    },
  });

  const handleRename = (id: number, name: string) => {
    renameMutation.mutate({ id, name });
  };

  const handleDelete = (id: number) => {
    if (confirm('Are you sure you want to delete this session?')) {
      deleteMutation.mutate(id);
    }
  };

  const handleExport = (id: number) => {
    exportMutation.mutate(id);
  };

  if (isLoading) {
    return <div className="loading">Loading sessions...</div>;
  }

  if (error) {
    return <div className="error">Error loading sessions: {String(error)}</div>;
  }

  return (
    <div className="home-page">
      <div className="page-header">
        <h2>Your Sessions</h2>
        <button className="btn btn-primary" onClick={() => navigate('/upload')}>
          Upload New PDF
        </button>
      </div>

      {sessions?.length === 0 ? (
        <div className="empty-state">
          <p>No sessions yet. Upload a PDF to get started!</p>
          <button className="btn btn-primary" onClick={() => navigate('/upload')}>
            Upload PDF
          </button>
        </div>
      ) : (
        <div className="sessions-grid">
          {sessions?.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              onDelete={handleDelete}
              onExport={handleExport}
              onRename={handleRename}
            />
          ))}
        </div>
      )}
    </div>
  );
}
