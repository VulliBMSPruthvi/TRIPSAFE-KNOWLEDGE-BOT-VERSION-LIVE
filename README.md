# TripSafe Knowledge Bot v2

Internal RAG-based chatbot for TripSafe travel insurance. Google SSO only, Anthropic Claude for generation, FAISS for retrieval, sentence-transformers for embeddings (no OpenAI anywhere).

> **Build status:** Phase A scaffold (steps 1–6 of the build plan). Auth, RAG, admin portal, and frontend land in Phases B–D.

---

## Architecture at a glance

| Layer        | Choice                                                           |
|--------------|------------------------------------------------------------------|
| Backend      | FastAPI (Python 3.11), async SQLAlchemy, Alembic                 |
| LLM          | Anthropic Claude — default `claude-haiku-4-5`, admin-switchable  |
| Embeddings   | `sentence-transformers/all-MiniLM-L6-v2` (local, free, private)  |
| Vector store | FAISS `IndexFlatL2` + pickled metadata                           |
| Auth         | Google OAuth 2.0 SSO only, JWT (15-min access + 7-day refresh)   |
| Database     | PostgreSQL (prod) / SQLite (dev fallback)                        |
| Cache / RL   | Redis                                                            |
| Frontend     | React + Vite + TypeScript + Tailwind (Phase D)                   |
| Deploy       | AWS ECS Fargate + ALB + RDS + S3 + Secrets Manager (Phase D)     |

### Why these choices

- **Claude Haiku 4.5 as default**: ~5× cheaper than Sonnet 4.6 with quality that's more than adequate for retrieval-grounded answers. Admins can switch to Sonnet 4.6 or Opus 4.7 from the Admin Portal — the active model is read from the `settings` table on every `/chat` call, so changes take effect immediately with no redeploy.
- **sentence-transformers, not Anthropic embeddings**: Anthropic does not expose an embeddings API. Running `all-MiniLM-L6-v2` in-container is free, private (no data leaves the VPC), and fast enough for the corpus size. Same model is used at index-build time and query time — never mix.
- **FAISS `IndexFlatL2`**: corpus is small (single-digit thousands of chunks). Flat search is exact, fast enough, and avoids the operational complexity of IVF/HNSW.
- **ECS Fargate, not EC2**: no SSH access to underlying hosts, IAM task roles per service, smaller attack surface. Cost premium is acceptable for an internal tool of this size.

---

## Local development

### Prerequisites

- Docker Desktop (Windows / macOS / Linux)
- Git
- (Optional) Python 3.11 if you want to run anything outside Docker

### First-time setup

```bash
git clone https://github.com/VulliBMSPruthvi/TRIPSAFE-KNOWLEDGE-BOT-VERSION-LIVE.git
cd TRIPSAFE-KNOWLEDGE-BOT-VERSION-LIVE
cp .env.example .env
# Edit .env: at minimum set APP_SECRET_KEY, JWT_SECRET, ANTHROPIC_API_KEY
docker compose up --build
```

The app boots on http://localhost:8000. Health check:

```bash
curl http://localhost:8000/health
```

### Run migrations

Migrations run automatically inside the container on startup. To run them manually:

```bash
docker compose exec app alembic upgrade head
```

To create a new migration after editing models:

```bash
docker compose exec app alembic revision --autogenerate -m "describe change"
```

---

## Environment variables

See [.env.example](./.env.example) for the full list with comments. Notable ones:

| Var                          | Purpose                                                       |
|------------------------------|---------------------------------------------------------------|
| `APP_SECRET_KEY`             | Used for signing cookies / CSRF                                |
| `JWT_SECRET`                 | Symmetric secret for JWT access tokens                         |
| `DATABASE_URL`               | SQLAlchemy async URL                                           |
| `ANTHROPIC_API_KEY`          | Claude API key                                                 |
| `GOOGLE_OAUTH_CLIENT_ID/SECRET` | Bootstrap OAuth creds; admins can override via Admin Portal |
| `ADMIN_SEED_EMAILS`          | Comma-separated emails that get `role=admin` on first login    |
| `FAISS_INDEX_DIR`            | Where `.faiss` and `.pkl` live (mounted volume in prod)        |
| `EMBEDDING_MODEL`            | sentence-transformers model name                               |

**No secret ever lives in code or git.** Production injects them from AWS Secrets Manager into the ECS task definition.

---

## Building the FAISS index manually

Phase A ships an empty `faiss_store/`. In Phase B the admin portal handles index builds, but a CLI fallback is also available:

```bash
docker compose exec app python -m scripts.build_index
```

It reads everything from `uploads/`, chunks at 500 word-tokens, embeds with `all-MiniLM-L6-v2`, and writes `trip_safe_index.faiss` + `trip_safe_metadata.pkl` into `FAISS_INDEX_DIR`.

---

## Admin setup

On first successful Google login, the email is checked against `ADMIN_SEED_EMAILS`. Matching users are auto-assigned `role=admin`. This check is server-side and runs on every login (so demoting someone in the DB without removing them from the seed list would re-promote them next login — adjust the seed list when offboarding admins).

After Phase B–C ships:
- `/admin` → Dashboard, Users, Chat Logs, Knowledge Base, System Prompt, Activity Log, **Integrations** (Google OAuth creds + active Claude model)
- Non-admin users hitting `/admin/*` get HTTP 403, not a redirect.

---

## AWS deployment

Full runbook in Phase D. Short version:

1. Build & push image to ECR.
2. Provision RDS (private subnet), S3 bucket (private, SSE), ALB (public, ACM cert).
3. Store secrets in AWS Secrets Manager under `tripsafe/prod/*`.
4. Create ECS Fargate service with task role granting least-privilege access to S3 + Secrets Manager + CloudWatch Logs.
5. Wire Route 53 → ALB.

Templates land in `infra/` in Phase D.

---

## Project layout

```
tripsafe-kb-v2/
├── app/
│   ├── api/v1/{auth,chat,admin}/   # versioned route groups
│   ├── core/                       # config, security, FastAPI deps
│   ├── db/                         # async engine, Alembic
│   ├── models/                     # SQLAlchemy ORM (one file per table)
│   ├── schemas/                    # Pydantic request/response
│   ├── services/                   # auth, rag, indexer, activity
│   └── main.py                     # app factory
├── frontend/                       # React (Phase D)
├── infra/                          # AWS task defs, IAM, S3 policies (Phase D)
├── scripts/build_index.py          # CLI index rebuild
├── uploads/                        # source .docx/.csv (gitignored)
├── faiss_store/                    # .faiss/.pkl (gitignored)
├── Dockerfile
├── docker-compose.yml
└── alembic.ini
```

---

## Security posture

- All secrets via env vars (pydantic-settings); zero hardcoded credentials.
- HTTPS-only in production (ALB terminates TLS, HTTP → HTTPS redirect).
- CORS whitelist (no wildcards).
- JWT in httpOnly cookies (never localStorage). Refresh tokens stored as bcrypt hashes; revocable via DB.
- Admin authorization enforced on every request: JWT valid AND `role=admin` AND `is_active=true` → else 403.
- File uploads: extension + MIME-validated, 20 MB cap, UUID-prefixed filenames.
- SQLAlchemy ORM everywhere; no raw SQL.
- CSP headers + React's default escaping for XSS defense.
- All activity (auth events, chats, admin actions) logged to `activity_log` with no PII (IDs and action types only).

---

## License

Internal — TripSafe / Tripjack.
