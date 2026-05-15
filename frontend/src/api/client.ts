// Thin wrapper over fetch() with httpOnly-cookie auth.
// `credentials: "include"` is required so the browser sends ts_access cookie.

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string, public payload?: unknown) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  expectJson = true,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(init.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    let payload: unknown = undefined;
    try {
      payload = await res.json();
    } catch {
      /* non-json error body */
    }
    const msg =
      (payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : res.statusText) || "Request failed";
    throw new ApiError(res.status, msg, payload);
  }
  if (!expectJson) return undefined as T;
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ── Types ────────────────────────────────────────────────────────────

export type UserRole = "admin" | "user";

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface ChatRequest {
  prompt: string;
  session_id?: string | null;
}

export interface RetrievedChunk {
  source: string;
  text: string;
  distance: number;
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  content: string;
  retrieved_chunks: RetrievedChunk[];
  model: string;
}

export interface ChatSession {
  id: string;
  started_at: string;
  last_message_at: string;
  message_count: number;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  retrieved_chunks: RetrievedChunk[] | null;
  created_at: string;
}

export interface DashboardStats {
  total_users: number;
  active_users: number;
  total_chats: number;
  chats_today: number;
  active_sessions_30m: number;
  rag_index_loaded: boolean;
  rag_chunk_count: number;
  rag_loaded_at: string | null;
  recent_activity: Array<{
    id: string;
    action_type: string;
    user_id: string | null;
    user_email: string | null;
    created_at: string;
  }>;
}

export interface AdminUserRow extends User {}

export interface KnowledgeFileRow {
  id: string;
  filename: string;
  file_size: number;
  content_type: string;
  uploaded_by: string | null;
  uploaded_at: string;
  is_active: boolean;
}

export interface IndexBuildRow {
  id: string;
  triggered_by: string | null;
  status: "pending" | "running" | "complete" | "failed";
  chunk_count: number | null;
  source_files: Array<{ filename: string; chunks: number }> | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface IndexStatus {
  loaded: boolean;
  chunk_count: number;
  loaded_at: string | null;
  latest_build: IndexBuildRow | null;
}

export interface SystemPromptRow {
  id: string;
  content: string;
  created_by: string | null;
  created_at: string;
  is_active: boolean;
}

export interface ModelOption {
  value: string;
  label: string;
  description: string;
}

export interface ChatModelSettings {
  current_model: string;
  available_models: ModelOption[];
}

export interface GoogleOAuthSettings {
  client_id: string;
  client_secret_set: boolean;
  redirect_uri: string;
}

export interface ActivityRow {
  id: string;
  user_id: string | null;
  user_email: string | null;
  action_type: string;
  extra: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface ActivityPage {
  rows: ActivityRow[];
  total: number;
  page: number;
  page_size: number;
}

// ── Endpoints ────────────────────────────────────────────────────────

export const api = {
  // Auth
  me: () => request<User>("/auth/me"),
  logout: () => request<{ status: string }>("/auth/logout", { method: "POST" }),
  loginUrl: () => `${BASE}/auth/google/login`,

  // Chat
  sendChat: (body: ChatRequest) =>
    request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify(body) }),
  /**
   * Streams chat events as Server-Sent Events. Callbacks receive parsed
   * events. Returns a promise that resolves when the stream ends.
   */
  streamChat: async (
    body: ChatRequest,
    handlers: {
      onStart?: (e: { session_id: string; model: string; sources: { source: string; distance: number }[] }) => void;
      onDelta?: (text: string) => void;
      onDone?: (e: { message_id: string }) => void;
      onError?: (detail: string) => void;
    },
    signal?: AbortSignal,
  ): Promise<void> => {
    const res = await fetch("/api/v1/chat/stream", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok || !res.body) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = (j && (j as { detail?: string }).detail) || detail;
      } catch {
        /* non-json */
      }
      handlers.onError?.(detail);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 2);
        if (!raw.startsWith("data:")) continue;
        const payload = raw.slice(5).trim();
        if (!payload) continue;
        try {
          const evt = JSON.parse(payload);
          if (evt.type === "start") handlers.onStart?.(evt);
          else if (evt.type === "delta") handlers.onDelta?.(evt.text);
          else if (evt.type === "done") handlers.onDone?.(evt);
          else if (evt.type === "error") handlers.onError?.(evt.detail);
        } catch {
          /* swallow malformed event */
        }
      }
    }
  },
  listSessions: () => request<ChatSession[]>("/chat/sessions"),
  sessionMessages: (sessionId: string) =>
    request<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),

  // Admin: dashboard
  dashboard: () => request<DashboardStats>("/admin/dashboard"),

  // Admin: users
  listUsers: () => request<AdminUserRow[]>("/admin/users"),
  changeRole: (id: string, role: UserRole) =>
    request<AdminUserRow>(`/admin/users/${id}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  changeActive: (id: string, is_active: boolean) =>
    request<AdminUserRow>(`/admin/users/${id}/active`, {
      method: "PATCH",
      body: JSON.stringify({ is_active }),
    }),

  // Admin: chat logs
  adminSessions: (userId?: string) =>
    request<Array<ChatSession & { user_id: string; user_email: string; user_name: string }>>(
      `/admin/chats/sessions${userId ? `?user_id=${userId}` : ""}`,
    ),
  adminSessionMessages: (sessionId: string) =>
    request<ChatMessage[]>(`/admin/chats/sessions/${sessionId}/messages`),
  searchChats: (q: string) =>
    request<Array<{
      message_id: string;
      session_id: string;
      user_id: string;
      user_email: string;
      role: string;
      content: string;
      created_at: string;
    }>>(`/admin/chats/search?q=${encodeURIComponent(q)}`),
  exportUserChats: (userId: string) =>
    `${BASE}/admin/chats/users/${userId}/export.csv`,

  // Admin: knowledge
  listFiles: () => request<KnowledgeFileRow[]>("/admin/knowledge/files"),
  uploadFile: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<KnowledgeFileRow>("/admin/knowledge/files", {
      method: "POST",
      body: fd,
    });
  },
  deleteFile: (id: string) =>
    request<void>(`/admin/knowledge/files/${id}`, { method: "DELETE" }, false),
  indexStatus: () => request<IndexStatus>("/admin/knowledge/index/status"),
  rebuildIndex: () =>
    request<IndexBuildRow>("/admin/knowledge/index/rebuild", { method: "POST" }),
  listBuilds: () => request<IndexBuildRow[]>("/admin/knowledge/index/builds"),

  // Admin: prompts
  activePrompt: () => request<SystemPromptRow | null>("/admin/prompts/active"),
  promptHistory: () => request<SystemPromptRow[]>("/admin/prompts/history"),
  savePrompt: (content: string) =>
    request<SystemPromptRow>("/admin/prompts", {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  activatePrompt: (id: string) =>
    request<SystemPromptRow>(`/admin/prompts/${id}/activate`, { method: "POST" }),

  // Admin: integrations
  getModelSettings: () => request<ChatModelSettings>("/admin/integrations/model"),
  setModel: (model: string) =>
    request<ChatModelSettings>("/admin/integrations/model", {
      method: "PATCH",
      body: JSON.stringify({ model }),
    }),
  getGoogleOAuth: () => request<GoogleOAuthSettings>("/admin/integrations/google"),
  setGoogleOAuth: (client_id: string, client_secret: string) =>
    request<GoogleOAuthSettings>("/admin/integrations/google", {
      method: "PATCH",
      body: JSON.stringify({ client_id, client_secret }),
    }),

  // Admin: activity
  activity: (params: {
    page?: number;
    action_type?: string;
    user_id?: string;
  } = {}) => {
    const search = new URLSearchParams();
    if (params.page) search.set("page", String(params.page));
    if (params.action_type) search.set("action_type", params.action_type);
    if (params.user_id) search.set("user_id", params.user_id);
    const qs = search.toString();
    return request<ActivityPage>(`/admin/activity${qs ? `?${qs}` : ""}`);
  },
};
