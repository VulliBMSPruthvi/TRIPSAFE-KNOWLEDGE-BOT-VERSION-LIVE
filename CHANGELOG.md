# Changelog

All notable changes to this project will be documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Phase A — Foundation (in progress)
- Repository scaffolding: folder layout, `.gitignore`, `.env.example`, README, this changelog.
- Docker: dev `Dockerfile`, `docker-compose.yml` with app + Postgres + Redis services.
- Database: SQLAlchemy 2.x async models for all 9 tables (users, refresh_tokens, chat_sessions, chat_messages, knowledge_files, index_builds, system_prompts, activity_log, settings).
- Alembic: initial migration `0001_initial.py` covering every table.
- Core: `config.py` (pydantic-settings, env-only), `security.py` (JWT access/refresh, bcrypt hashing), `dependencies.py` (`get_current_user`, `admin_required`).
- App factory: FastAPI with CORS middleware, CSP headers, `/health` endpoint.
- Design tokens: TripSafe Design System CSS exported into `frontend/src/styles/` for Phase D.

### Phase B — Auth + RAG
- Pydantic schemas: `auth.py` (UserPublic, TokenResponse), `chat.py` (ChatRequest/Response, ChatMessagePublic, ChatSessionPublic).
- `services/settings_store.py`: cached DB-backed key/value, used for runtime-mutable values (active chat model, OAuth credentials).
- `services/activity.py`: audit log writer with action-type constants; no PII in `extra` blobs.
- `services/auth.py`: Google OAuth 2.0 flow (manual via httpx — authorize URL, code exchange, userinfo). State CSRF via itsdangerous signed serializer (10-min TTL). Server-side admin seeding from `ADMIN_SEED_EMAILS`. Refresh-token rotation with revocation on every refresh.
- `services/rag.py`: singleton engine wrapping sentence-transformers (`all-MiniLM-L6-v2`) + FAISS `IndexFlatL2` + Anthropic Claude. `reload()` for hot-swapping the index in Phase C. Graceful degradation when no index exists yet.
- `api/v1/auth.py`: `GET /google/login`, `GET /google/callback`, `POST /refresh`, `POST /logout`, `GET /me`. JWT in httpOnly + SameSite=Lax cookies. Refresh cookie scoped to `/api/v1/auth`.
- `api/v1/chat.py`: `POST /chat` (creates/reuses session, retrieves chunks, calls Claude, persists both messages with retrieved chunks for audit), `GET /sessions`, `GET /sessions/{id}/messages`. Active model read fresh from `settings` table per call.
- App lifespan: seeds defaults (`chat_model`), tries to load FAISS index (non-fatal if absent).
- Dockerfile: install CPU-only torch from PyTorch's CPU index BEFORE other requirements → image down from ~5 GB to ~1.5 GB.

### Phase C — Admin Portal API
- `schemas/admin.py`: Pydantic shapes for every admin response (dashboard, users, chats, files, builds, prompts, integrations, activity log).
- `services/indexer.py`: text extraction (`.docx` via python-docx, `.csv` via pandas), ~500-word chunking with 50-word overlap, batch embedding via the shared sentence-transformers singleton, FAISS IndexFlatL2 build, atomic file swap (tmp → rename) with timestamped backups in `faiss_store/backups/`, hot reload into the in-memory engine. Settles `IndexBuild` row to `complete` or `failed` no matter what.
- `api/v1/admin/` sub-package, all routes gated by `Depends(admin_required)` at the router level — non-admin gets 403 before any handler runs:
  - `dashboard.py`: `GET /admin/dashboard` (total/active users, total/today chats, 30-min active sessions, RAG state, last 20 activity items).
  - `users.py`: list users, change role, deactivate/reactivate. Refuses to let an admin demote or deactivate themselves.
  - `chat_logs.py`: list all sessions, view a session's transcript, keyword search, **CSV export of a user's full chat history**.
  - `knowledge.py`: list/upload/delete source files (`.docx` + `.csv`, 20 MB cap, UUID-prefixed stored names), index status, trigger rebuild (with concurrent-build guard), build history.
  - `prompts.py`: get active prompt, save new version (auto-deactivates previous), list last 10, revert to older version.
  - `integrations.py`: **chat-model dropdown** (`claude-haiku-4-5` / `sonnet-4-6` / `opus-4-7`) — change takes effect on the next `/chat` call with no restart. Google OAuth client_id/secret CRUD; secret never logged.
  - `activity_log.py`: paginated (50/page), filterable by user / action_type / date range.
- Rate limiting wired: `slowapi.limit(rate_limit_chat)` on `POST /chat`, `slowapi.limit(rate_limit_auth)` on `GET /auth/google/login`. Limits configurable via env.
- `scripts/build_index.py`: CLI fallback for first-time/index rebuild before any admin exists. Same chunk+embed pipeline as the admin route.

### Phase D — Frontend
- Vite + React 18 + TypeScript + TailwindCSS. Tailwind theme fully mapped to TripSafe design tokens (brand blue/cyan/navy, gray 50→900, semantic success/warning/danger/info, Inter + Poppins fonts, 4–96px spacing, 6–24px radii, brand-tinted shadows, brand gradients).
- `api/client.ts`: typed fetch wrapper with `credentials: include` for cookie auth; covers every backend endpoint.
- `auth/AuthContext.tsx`: fetches `/auth/me` on app load, exposes user/loading/refresh/logout. `auth/guards.tsx` provides `<RequireAuth>` and `<RequireAdmin>` — non-admins on `/admin/*` get redirected to `/`, and the backend separately returns 403.
- Primitives: Button (4 variants × 3 sizes), Card + CardHeader, Input + Textarea, Badge (6 tones), Spinner, Logo.
- Login page: full-bleed hero gradient + Google SSO button.
- Chat portal: header with logo + avatar + sign-out + conditional Admin button; message bubbles with collapsible "Sources" details; bouncing typing indicator; auto-scroll; mobile responsive.
- Admin portal shell with sidebar + 7 tabs:
  - **Dashboard**: stat tiles + RAG state badge + recent activity feed.
  - **Users**: table with promote/demote/deactivate (self-row guard).
  - **Chat Logs**: keyword search, session list, transcript pane, per-user CSV export.
  - **Knowledge Base**: file upload, list/delete, **Rebuild index** with live polling, build history.
  - **System Prompt**: editor with history + revert.
  - **Integrations**: radio-card model picker (Haiku 4.5 / Sonnet 4.6 / Opus 4.7); Google OAuth credential form.
  - **Activity Log**: paginated, filterable, expandable JSON details.
- `frontend/Dockerfile` (Node 20 alpine, Vite dev with HMR) + `frontend` service in `docker-compose.yml`. Vite proxies `/api/*` to the backend so cookies stay first-party on `localhost:5173`.
- `.env.example`: `GOOGLE_OAUTH_REDIRECT_URI` now points at `localhost:5173/api/v1/auth/google/callback`.

### Phase D-polish — UX upgrade
- **Markdown rendering**: bot replies are now properly formatted (`**bold**` bolds, `# heading` heads, tables, code blocks, ordered/unordered lists, blockquotes, fenced code with syntax highlighting). New `MarkdownMessage` component wraps `react-markdown` + `remark-gfm` + `rehype-highlight`.
- **Streaming responses**: new `POST /api/v1/chat/stream` returns Server-Sent Events. Backend bridges Anthropic's synchronous `messages.stream` to async via a worker-thread + asyncio queue so the event loop stays free. Frontend uses `fetch` + `ReadableStream` to read deltas and append them to the active bubble — Claude-style typing effect with a soft cursor caret while streaming.
- **Google-style account menu**: replaces the inline name/email/buttons with a circular avatar in the header. Click → dropdown with photo, name, email, Admin badge, Admin/Back-to-Chat toggle, Sign out. Click-outside + Escape to close.
- **Welcome screen**: large brand-gradient sparkle, big heading, 2×2 suggestion cards ("What does TripSafe cover?", "How do plans differ?", "How do I file a claim?", "Medical emergency coverage?") that auto-send.
- **Chat history sidebar**: lists this user's sessions with last-message-time ("12m ago" / "3h ago"), New Chat button at top, click to load any past conversation. Refreshes after every send.
- **Embedding provider switch**: `EMBEDDING_PROVIDER=openai` (in addition to `local`) — uses OpenAI's text-embedding-3-small via httpx. Bypasses the slow corporate-proxy model download. Chat answers still come from Claude.
- **Zombie build reaper**: on startup, any `pending`/`running` `IndexBuild` rows are marked `failed` with a clear reason — fixes the stuck-row issue when a container is killed mid-build.
- **Login page polish**: cleaner card layout, properly-aligned Google icon on a white pill inside the brand-blue button, calmer brand-tinted glows.
- New deps: `react-markdown@9`, `remark-gfm@4`, `rehype-highlight@7`, `highlight.js@11`.

### Phase E — AWS deployment (planned)
- Multi-stage production Dockerfile for frontend (build → nginx).
- ECS Fargate task definition + S3 + IAM templates.
- Route 53 + ALB + ACM cert.
- GitHub Actions CI/CD.


