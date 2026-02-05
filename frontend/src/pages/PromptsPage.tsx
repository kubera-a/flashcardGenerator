import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { promptsApi } from '../api/client';
import type { CurrentPrompts, PromptSuggestion, PromptVersion } from '../types';

function PromptViewer({ prompt, title }: { prompt: PromptVersion | null; title: string }) {
  if (!prompt) {
    return (
      <div className="prompt-viewer empty">
        <h4>{title}</h4>
        <p>No active prompt</p>
      </div>
    );
  }

  return (
    <div className="prompt-viewer">
      <div className="prompt-header">
        <h4>{title}</h4>
        <span className="version-badge">v{prompt.version}</span>
        {prompt.is_active && <span className="active-badge">Active</span>}
      </div>
      <div className="prompt-metrics">
        <span>Cards Generated: {prompt.total_cards_generated}</span>
        <span>Approved: {prompt.approved_cards}</span>
        <span>Rejected: {prompt.rejected_cards}</span>
        <span>Approval Rate: {(prompt.approval_rate * 100).toFixed(1)}%</span>
      </div>
      <div className="prompt-content">
        <div className="prompt-section">
          <h5>System Prompt</h5>
          <pre>{prompt.system_prompt}</pre>
        </div>
        <div className="prompt-section">
          <h5>User Prompt Template</h5>
          <pre>{prompt.user_prompt_template}</pre>
        </div>
      </div>
    </div>
  );
}

function SuggestionCard({
  suggestion,
  currentPrompt,
  onApprove,
  onReject,
}: {
  suggestion: PromptSuggestion;
  currentPrompt: PromptVersion | null;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}) {
  return (
    <div className="suggestion-card">
      <div className="suggestion-header">
        <h4>Prompt Improvement Suggestion</h4>
        <span className="suggestion-status">{suggestion.status}</span>
      </div>

      <div className="suggestion-reasoning">
        <h5>Analysis & Reasoning</h5>
        <p>{suggestion.reasoning}</p>
      </div>

      <div className="rejection-patterns">
        <h5>Rejection Patterns Detected</h5>
        <div className="patterns-grid">
          {Object.entries(suggestion.rejection_patterns.type_distribution || {}).map(
            ([type, count]) => (
              <div key={type} className="pattern-item">
                <span className="pattern-type">{type}</span>
                <span className="pattern-count">{String(count)}</span>
              </div>
            )
          )}
        </div>
      </div>

      <div className="prompt-diff">
        <div className="diff-section">
          <h5>Suggested System Prompt</h5>
          <div className="diff-content">
            <div className="diff-old">
              <span className="diff-label">Current:</span>
              <pre>{currentPrompt?.system_prompt || 'N/A'}</pre>
            </div>
            <div className="diff-new">
              <span className="diff-label">Suggested:</span>
              <pre>{suggestion.suggested_system_prompt}</pre>
            </div>
          </div>
        </div>

        <div className="diff-section">
          <h5>Suggested User Prompt Template</h5>
          <div className="diff-content">
            <div className="diff-old">
              <span className="diff-label">Current:</span>
              <pre>{currentPrompt?.user_prompt_template || 'N/A'}</pre>
            </div>
            <div className="diff-new">
              <span className="diff-label">Suggested:</span>
              <pre>{suggestion.suggested_user_prompt_template}</pre>
            </div>
          </div>
        </div>
      </div>

      {suggestion.status === 'pending' && (
        <div className="suggestion-actions">
          <button className="btn btn-success" onClick={() => onApprove(suggestion.id)}>
            Apply Changes
          </button>
          <button className="btn btn-danger" onClick={() => onReject(suggestion.id)}>
            Reject
          </button>
        </div>
      )}
    </div>
  );
}

export default function PromptsPage() {
  const queryClient = useQueryClient();

  const { data: currentPrompts, isLoading: promptsLoading } = useQuery({
    queryKey: ['prompts', 'current'],
    queryFn: async () => {
      const response = await promptsApi.getCurrent();
      return response.data as CurrentPrompts;
    },
  });

  const { data: suggestions, isLoading: suggestionsLoading } = useQuery({
    queryKey: ['prompts', 'suggestions'],
    queryFn: async () => {
      const response = await promptsApi.getSuggestions();
      return response.data as PromptSuggestion[];
    },
  });

  const { data: history } = useQuery({
    queryKey: ['prompts', 'history'],
    queryFn: async () => {
      const response = await promptsApi.getHistory();
      return response.data as PromptVersion[];
    },
  });

  const approveMutation = useMutation({
    mutationFn: (id: number) => promptsApi.approveSuggestion(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
      alert('Prompt updated successfully!');
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (id: number) => promptsApi.rejectSuggestion(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts', 'suggestions'] });
    },
  });

  if (promptsLoading) {
    return <div className="loading">Loading prompts...</div>;
  }

  return (
    <div className="prompts-page">
      <h2>Prompt Management</h2>
      <p className="page-description">
        View and manage the prompts used for flashcard generation. When you finalize a session,
        the system analyzes your feedback and suggests improvements to the prompts.
      </p>

      <section className="current-prompts">
        <h3>Current Active Prompts</h3>
        <div className="prompts-grid">
          <PromptViewer
            prompt={currentPrompts?.generation || null}
            title="Generation Prompt"
          />
          <PromptViewer
            prompt={currentPrompts?.validation || null}
            title="Validation Prompt"
          />
        </div>
      </section>

      <section className="pending-suggestions">
        <h3>Pending Suggestions</h3>
        {suggestionsLoading ? (
          <div className="loading">Loading suggestions...</div>
        ) : suggestions?.length === 0 ? (
          <div className="empty-state">
            <p>No pending suggestions. Finalize a session to generate prompt improvements.</p>
          </div>
        ) : (
          <div className="suggestions-list">
            {suggestions?.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                currentPrompt={currentPrompts?.generation || null}
                onApprove={(id) => approveMutation.mutate(id)}
                onReject={(id) => rejectMutation.mutate(id)}
              />
            ))}
          </div>
        )}
      </section>

      <section className="prompt-history">
        <h3>Version History</h3>
        {history?.length === 0 ? (
          <div className="empty-state">
            <p>No prompt history available.</p>
          </div>
        ) : (
          <table className="history-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Version</th>
                <th>Active</th>
                <th>Cards</th>
                <th>Approval Rate</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {history?.map((prompt) => (
                <tr key={prompt.id} className={prompt.is_active ? 'active' : ''}>
                  <td>{prompt.prompt_type}</td>
                  <td>v{prompt.version}</td>
                  <td>{prompt.is_active ? '✓' : ''}</td>
                  <td>{prompt.total_cards_generated}</td>
                  <td>{(prompt.approval_rate * 100).toFixed(1)}%</td>
                  <td>{new Date(prompt.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
