import axios from 'axios';

// Use relative URL in production (Docker), absolute in development
const API_BASE_URL = import.meta.env.DEV
  ? 'http://localhost:8000/api/v1'
  : '/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Sessions API
export const sessionsApi = {
  // Legacy upload (starts generation immediately)
  upload: async (file: File, llmProvider: string = 'openai') => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/sessions/?llm_provider=${llmProvider}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // Upload PDF with preview (for page selection)
  uploadPreview: async (file: File, llmProvider: string = 'openai', generateThumbnails: boolean = true) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/sessions/upload-preview?llm_provider=${llmProvider}&generate_thumbnails=${generateThumbnails}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // Upload markdown ZIP with preview
  uploadMarkdownPreview: async (file: File, llmProvider: string = 'anthropic') => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/sessions/upload-markdown?llm_provider=${llmProvider}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // Start generation with page selection
  startGeneration: (sessionId: number, pageIndices: number[] | null, useNativePdf: boolean = true) =>
    api.post(`/sessions/${sessionId}/start-generation`, {
      page_indices: pageIndices,
      use_native_pdf: useNativePdf,
    }),
  // Get thumbnails for a session
  getThumbnails: (sessionId: number, pageIndices?: number[]) => {
    const params = pageIndices ? `?page_indices=${pageIndices.join(',')}` : '';
    return api.get(`/sessions/${sessionId}/thumbnails${params}`);
  },
  list: () => api.get('/sessions/'),
  get: (id: number) => api.get(`/sessions/${id}`),
  getStatus: (id: number) => api.get(`/sessions/${id}/status`),
  finalize: (id: number) => api.post(`/sessions/${id}/finalize`),
  rename: (id: number, displayName: string) =>
    api.patch(`/sessions/${id}/rename`, { display_name: displayName }),
  delete: (id: number) => api.delete(`/sessions/${id}`),
};

// Cards API
export const cardsApi = {
  getForSession: (sessionId: number, status?: string) => {
    const params = status ? `?status=${status}` : '';
    return api.get(`/cards/session/${sessionId}${params}`);
  },
  get: (id: number) => api.get(`/cards/${id}`),
  approve: (id: number) => api.patch(`/cards/${id}/approve`),
  reject: (id: number, reason: string, rejectionType: string) =>
    api.patch(`/cards/${id}/reject`, { reason, rejection_type: rejectionType }),
  edit: (id: number, front: string, back: string, tags?: string[]) =>
    api.patch(`/cards/${id}/edit`, { front, back, tags }),
  autoCorrect: (id: number) => api.post(`/cards/${id}/auto-correct`),
  batchApprove: (cardIds: number[]) =>
    api.post('/cards/batch/approve', { card_ids: cardIds }),
  batchReject: (cardIds: number[], reason: string, rejectionType: string) =>
    api.post('/cards/batch/reject', {
      card_ids: cardIds,
      reason,
      rejection_type: rejectionType,
    }),
};

// Prompts API
export const promptsApi = {
  getCurrent: () => api.get('/prompts/current'),
  getHistory: (promptType?: string) => {
    const params = promptType ? `?prompt_type=${promptType}` : '';
    return api.get(`/prompts/history${params}`);
  },
  getSuggestions: () => api.get('/prompts/suggestions'),
  getSuggestion: (id: number) => api.get(`/prompts/suggestions/${id}`),
  approveSuggestion: (id: number) => api.post(`/prompts/suggestions/${id}/approve`),
  rejectSuggestion: (id: number) => api.post(`/prompts/suggestions/${id}/reject`),
  getAnalytics: () => api.get('/prompts/analytics'),
};

// Export API
export const exportApi = {
  exportSession: (sessionId: number, deckName?: string, includeTags: boolean = true) =>
    api.post(`/export/session/${sessionId}`, {
      include_tags: includeTags,
      deck_name: deckName,
    }),
  exportSessionWithMedia: (sessionId: number, deckName?: string, includeTags: boolean = true) =>
    api.post(`/export/session/${sessionId}/with-media`, {
      include_tags: includeTags,
      deck_name: deckName,
    }),
  list: () => api.get('/export/list'),
  ankiConnectStatus: () => api.get('/export/anki-connect/status'),
  sendToAnki: (sessionId: number, deckName?: string, includeTags: boolean = true) =>
    api.post(`/export/session/${sessionId}/anki-connect`, {
      include_tags: includeTags,
      deck_name: deckName,
    }),
};

// Images API
export const imagesApi = {
  getImageUrl: (sessionId: number, filename: string) =>
    `${API_BASE_URL}/images/${sessionId}/${filename}`,
  getOriginalImageUrl: (sessionId: number, filename: string) =>
    `${API_BASE_URL}/images/${sessionId}/original/${encodeURIComponent(filename)}`,
};
