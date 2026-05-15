# AWS App Runner — Go-Live Runbook

End-to-end deployment of TripSafe Knowledge Bot v2 to AWS App Runner.

- **Region**: ap-south-1 (Mumbai)
- **Account**: 138218764618
- **Estimated time**: ~90 minutes the first time
- **Estimated cost**: ~$30–50/month at 300–500 users

> **Conventions**
> Replace `<your-...>` placeholders with your real values as you go.
> All AWS Console links assume you're signed in. Each step lists both
> the **Console path** and the equivalent **CLI command** — pick one.

---

## 0 · Prerequisites

- ✅ AWS account `138218764618` with admin access
- ✅ Sign in to https://138218764618.signin.aws.amazon.com/console
- ✅ Switch to **Mumbai (ap-south-1)** region (top-right region selector)
- ✅ Code pushed to GitHub `main` branch
- ⏳ Anthropic API key (you have it locally)
- ⏳ OpenAI API key (you have it locally — used for embeddings only)
- ⏳ Google OAuth client ID + secret (you have these)

---

## 1 · Create an ECR repository (~3 min)

This is where your Docker images live.

**Console**: ECR → Private registry → "Create repository"
- Name: `tripsafe-kb-v2`
- Image scanning: enabled
- Encryption: AES-256
- Click "Create repository"
- **Copy the URI** — looks like `138218764618.dkr.ecr.ap-south-1.amazonaws.com/tripsafe-kb-v2`

**CLI**:
```bash
aws ecr create-repository \
  --repository-name tripsafe-kb-v2 \
  --region ap-south-1 \
  --image-scanning-configuration scanOnPush=true
```

---

## 2 · Create the S3 bucket for FAISS files (~3 min)

App Runner containers are ephemeral. The FAISS index files (~50 MB) live in S3 so they survive restarts and are shared across scaled-out replicas.

**Console**: S3 → "Create bucket"
- Name: `tripsafe-kb-v2-138218764618` (must be globally unique)
- Region: `ap-south-1`
- Block all public access: **ON** (private bucket)
- Bucket versioning: **Enable** (keeps prior indexes as backup)
- Default encryption: SSE-S3 (AES-256)
- Click "Create"

**CLI**:
```bash
aws s3api create-bucket \
  --bucket tripsafe-kb-v2-138218764618 \
  --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-versioning \
  --bucket tripsafe-kb-v2-138218764618 \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption \
  --bucket tripsafe-kb-v2-138218764618 \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

---

## 3 · Create the RDS PostgreSQL database (~10 min, mostly waiting)

**Console**: RDS → "Create database"
- Choose: **Standard create**
- Engine: PostgreSQL
- Version: 16.x
- Template: **Free tier** (if eligible) or **Dev/Test**
- Settings:
  - DB instance identifier: `tripsafe-kb-v2-db`
  - Master username: `tripsafe`
  - Master password: **generate a strong one and save it now** — you'll need it in Step 5
- Instance class: `db.t4g.micro` (2 vCPU, 1 GiB) — about $13/mo
- Storage: 20 GiB gp3
- Connectivity:
  - VPC: default
  - Public access: **No** (we'll connect from App Runner via VPC connector)
  - Actually for App Runner simplicity, set **Public access: Yes** for now and lock down with a security group rule allowing only the App Runner egress IP range. Or use a VPC connector — slightly more setup but more secure. **For first deploy go with Yes; you can move to VPC connector later.**
  - VPC security group: create new, name it `tripsafe-rds-sg`
- Initial database name: `tripsafe`
- Click "Create database" → wait ~5 min for status to become "Available"

Once it's available, note the **Endpoint** (looks like `tripsafe-kb-v2-db.xxxxx.ap-south-1.rds.amazonaws.com`).

**Inbound rule on `tripsafe-rds-sg`**:
- Type: PostgreSQL (5432)
- Source: `0.0.0.0/0` if Public access = Yes (you can tighten later)

---

## 4 · Generate your production secrets (~2 min)

Open a terminal and run:

```bash
# JWT signing secret
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Save as JWT_SECRET

# App secret (used for OAuth state)
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Save as APP_SECRET_KEY
```

Keep both values handy for the next step.

---

## 5 · Store secrets in AWS Secrets Manager (~10 min)

**Console**: Secrets Manager → "Store a new secret"

Create these secrets. For each, choose "Other type of secret" → key/value:

| Secret name                        | Key                          | Value                              |
|-----------------------------------|------------------------------|------------------------------------|
| `tripsafe/prod/db_url`            | `value`                      | `postgresql+asyncpg://tripsafe:<password>@<rds-endpoint>:5432/tripsafe` |
| `tripsafe/prod/anthropic_api_key` | `value`                      | `sk-ant-...` (your Anthropic key)  |
| `tripsafe/prod/openai_api_key`    | `value`                      | `sk-...` (your OpenAI key)         |
| `tripsafe/prod/jwt_secret`        | `value`                      | the JWT_SECRET from Step 4         |
| `tripsafe/prod/app_secret_key`    | `value`                      | the APP_SECRET_KEY from Step 4     |
| `tripsafe/prod/google_oauth`      | `client_id` + `client_secret`| your Google OAuth values           |

For each: name → "Next" → encryption key: default → "Next" → no rotation → "Store".

**CLI shortcut** for one of them:
```bash
aws secretsmanager create-secret \
  --name tripsafe/prod/jwt_secret \
  --secret-string '{"value":"<JWT_SECRET>"}' \
  --region ap-south-1
```

---

## 6 · Set up IAM role for App Runner (~5 min)

App Runner needs two roles:
- **Access role** — to pull images from ECR
- **Instance role** — to read from S3 + Secrets Manager at runtime

**Console**: IAM → Roles → "Create role"

### 6a. Access role
- Trusted entity: **AWS service** → **App Runner** → use case: "App Runner – ECR access"
- Attach: `AWSAppRunnerServicePolicyForECRAccess` (managed)
- Name: `AppRunnerECRAccessRole`

### 6b. Instance role
- Trusted entity: **AWS service** → **App Runner** → use case: "App Runner – Tasks"
- No managed policy yet — we'll attach a custom one
- Name: `tripsafe-kb-v2-instance-role`

After creating, click into the role → **Add permissions** → **Create inline policy** → JSON:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::tripsafe-kb-v2-138218764618",
        "arn:aws:s3:::tripsafe-kb-v2-138218764618/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:ap-south-1:138218764618:secret:tripsafe/prod/*"
    }
  ]
}
```

Name the policy: `tripsafe-kb-v2-runtime-access`.

---

## 7 · Push your first image to ECR (~10 min)

You can either do this manually for the first deploy, or let GitHub Actions do it (Step 9). For now, manual:

```bash
# Authenticate Docker to your ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin \
    138218764618.dkr.ecr.ap-south-1.amazonaws.com

# Build the production image (run from project root)
docker build -f Dockerfile.prod \
  -t 138218764618.dkr.ecr.ap-south-1.amazonaws.com/tripsafe-kb-v2:latest .

# Push
docker push 138218764618.dkr.ecr.ap-south-1.amazonaws.com/tripsafe-kb-v2:latest
```

> ⏱ Build is ~10 min the first time (Vite + torch install). Cached re-runs are ~2 min.

---

## 8 · Create the App Runner service (~15 min)

**Console**: App Runner → "Create service"

- Source: **Container registry**
- Provider: Amazon ECR
- Browse image: select `tripsafe-kb-v2:latest`
- Deployment trigger: **Automatic** (so future `git push` to main → ECR push → auto-deploy)
- ECR access role: `AppRunnerECRAccessRole` (created in 6a)
- Click **Next**

### Service settings
- Service name: `tripsafe-kb-v2`
- Virtual CPU: **1 vCPU**
- Memory: **2 GB** (FAISS + sentence-transformers can use this)
- Port: **8000**

### Environment variables (the heart of the deployment)

Add each as a separate row. **For secrets, click "Reference" and pick the Secrets Manager ARN**:

| Variable                       | Value source                  | What to enter                                                 |
|-------------------------------|-------------------------------|--------------------------------------------------------------|
| `APP_ENV`                     | Plain                         | `production`                                                  |
| `APP_DEBUG`                   | Plain                         | `false`                                                       |
| `APP_BASE_URL`                | Plain                         | (you'll fill after you get the App Runner URL — see Step 11)  |
| `FRONTEND_BASE_URL`           | Plain                         | same as `APP_BASE_URL`                                        |
| `APP_SECRET_KEY`              | Secrets Manager → reference   | `arn:...tripsafe/prod/app_secret_key:value::`                 |
| `JWT_SECRET`                  | Secrets Manager → reference   | `arn:...tripsafe/prod/jwt_secret:value::`                     |
| `JWT_ACCESS_TOKEN_MINUTES`    | Plain                         | `15`                                                          |
| `JWT_REFRESH_TOKEN_DAYS`      | Plain                         | `7`                                                           |
| `DATABASE_URL`                | Secrets Manager → reference   | `arn:...tripsafe/prod/db_url:value::`                         |
| `ANTHROPIC_API_KEY`           | Secrets Manager → reference   | `arn:...tripsafe/prod/anthropic_api_key:value::`              |
| `DEFAULT_CHAT_MODEL`          | Plain                         | `claude-haiku-4-5`                                            |
| `EMBEDDING_PROVIDER`          | Plain                         | `openai`                                                      |
| `OPENAI_API_KEY`              | Secrets Manager → reference   | `arn:...tripsafe/prod/openai_api_key:value::`                 |
| `OPENAI_EMBEDDING_MODEL`      | Plain                         | `text-embedding-3-small`                                      |
| `GOOGLE_OAUTH_CLIENT_ID`      | Secrets Manager → reference   | `arn:...tripsafe/prod/google_oauth:client_id::`               |
| `GOOGLE_OAUTH_CLIENT_SECRET`  | Secrets Manager → reference   | `arn:...tripsafe/prod/google_oauth:client_secret::`           |
| `GOOGLE_OAUTH_REDIRECT_URI`   | Plain                         | (fill after Step 11: `<App Runner URL>/api/v1/auth/google/callback`) |
| `ADMIN_SEED_EMAILS`           | Plain                         | `vulli.pruthvi@tripjack.com,vullipruthvi@gmail.com`           |
| `CORS_ALLOWED_ORIGINS`        | Plain                         | (fill after Step 11: your App Runner URL)                     |
| `FAISS_INDEX_DIR`             | Plain                         | `/app/faiss_store`                                            |
| `UPLOADS_DIR`                 | Plain                         | `/app/uploads`                                                |
| `USE_S3_FOR_FAISS`            | Plain                         | `true`                                                        |
| `AWS_REGION`                  | Plain                         | `ap-south-1`                                                  |
| `AWS_S3_BUCKET`               | Plain                         | `tripsafe-kb-v2-138218764618`                                 |

### Health check
- Protocol: **HTTP**
- Path: `/health`
- Interval: 20 s
- Timeout: 5 s
- Healthy threshold: 1
- Unhealthy threshold: 5

### Security
- **Instance role**: `tripsafe-kb-v2-instance-role` (from 6b)

### Networking
- Public ingress
- Outgoing traffic: Public (App Runner can reach the internet — needed for Claude + OpenAI APIs)

Click **Create & deploy**. Takes **~5–10 minutes** for the first deploy.

When it's ready, App Runner shows a URL like:
`https://abcdef1234.ap-south-1.awsapprunner.com`

**Copy this URL.**

---

## 9 · Fill in the URL-dependent env vars (~3 min)

Now that you have the live URL, go back to the App Runner service → **Configuration** → **Edit**:

- `APP_BASE_URL` = your App Runner URL
- `FRONTEND_BASE_URL` = your App Runner URL
- `GOOGLE_OAUTH_REDIRECT_URI` = `<App Runner URL>/api/v1/auth/google/callback`
- `CORS_ALLOWED_ORIGINS` = your App Runner URL

Click **Deploy** to apply. ~3 min for the redeploy.

---

## 10 · Update Google Cloud Console OAuth (~2 min)

1. Go to https://console.cloud.google.com/apis/credentials
2. Open your `tripsafe-kb-v2` OAuth client
3. Under **Authorized redirect URIs**, add:
   ```
   <App Runner URL>/api/v1/auth/google/callback
   ```
4. Save. Wait ~30s for Google to propagate.

---

## 11 · First chat end-to-end (~5 min)

1. Open your App Runner URL in a browser.
2. Click **Sign in with Google** → use `vulli.pruthvi@tripjack.com` → you should be granted admin automatically (admin seeding).
3. Click your avatar → **Admin portal**.
4. **Knowledge Base** → upload your `TripSafe Policy Wordings.docx` (and FAQ / Plans).
5. Click **Rebuild index** → should complete in **~15 seconds** (OpenAI embeddings, no slow model download).
6. **Back to Chat** → ask: *"What does TripSafe cover?"* → get a real Claude answer.

🎉 **You're live.**

---

## 12 · Set up GitHub Actions auto-deploy (~10 min, optional but recommended)

So you never have to manually `docker build/push` again.

1. **Create an IAM role for GitHub OIDC**:
   - Console: IAM → Identity providers → **Add provider** → OpenID Connect
     - URL: `https://token.actions.githubusercontent.com`
     - Audience: `sts.amazonaws.com`
   - Then IAM → Roles → Create role → **Web identity** → pick the GitHub provider
     - GitHub organization: `VulliBMSPruthvi`
     - GitHub repository: `TRIPSAFE-KNOWLEDGE-BOT-VERSION-LIVE`
     - Branch: `main`
   - Attach policies:
     - `AmazonEC2ContainerRegistryPowerUser` (push to ECR)
     - Create inline policy: allow `apprunner:StartDeployment` on your service ARN
   - Role name: `github-actions-deploy-tripsafe`
   - **Copy the role ARN.**

2. **Add GitHub repository secrets**:
   - Go to: https://github.com/VulliBMSPruthvi/TRIPSAFE-KNOWLEDGE-BOT-VERSION-LIVE/settings/secrets/actions
   - Add `AWS_DEPLOY_ROLE_ARN` = the role ARN from step 1
   - Add `APP_RUNNER_SERVICE_ARN` = ARN of your App Runner service (find in App Runner console)

3. **Push to main** → `.github/workflows/deploy.yml` runs → image builds → ECR push → App Runner deploys.

---

## 13 · Ongoing operations

### Updating chat model

Admin Portal → Integrations → pick a different Claude model → "Apply". Effective immediately.

### Updating system prompt

Admin Portal → System Prompt → edit → Save.

### Uploading new knowledge files

Admin Portal → Knowledge Base → Upload file → Rebuild index. Takes ~15 seconds with OpenAI embeddings.

### Viewing logs

Console: App Runner → your service → **Logs** tab → "View in CloudWatch".

### Cost monitoring

Console: Billing → Cost Explorer. Set up a budget alarm (e.g., $80/month) so you get an email if costs creep.

### Scaling

App Runner auto-scales 1 → 25 instances based on traffic. For 300–500 internal users, 1 instance is plenty.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| App Runner deploy fails on `alembic upgrade head` | DB unreachable | Check RDS security group allows 5432 from App Runner public egress, and `DATABASE_URL` secret is correct |
| Google login redirects to `redirect_uri_mismatch` | Forgot Step 10 | Add the App Runner callback URL in Google Cloud Console |
| Chat returns 503 "Knowledge base not built" | S3 bucket empty | Upload files + rebuild index from admin portal |
| Empty page on live URL | Frontend dist not in image | Confirm Dockerfile.prod's frontend-builder stage succeeded |
| Cost spike | Something is hammering /chat | Check Activity Log, deactivate the user; consider tightening rate limit |

---

## What I built into the code that supports all of the above

| Concern | Where it's handled |
|---|---|
| HTTPS-only cookies in prod | `app/api/v1/auth.py` — `secure=settings.is_production` |
| Strict CORS in prod | `app/main.py` — `_enforce_production_invariants` rejects `*` |
| HSTS header in prod | `app/main.py` security_headers middleware |
| Production refuses to start with default secrets | `app/main.py` — `_enforce_production_invariants` |
| Single-process container (App Runner requirement) | `Dockerfile.prod` runs gunicorn directly |
| Container survives restart | `s3_store.pull_to_local()` runs in startup hook |
| Multi-replica index consistency | `s3_store.push_from_local()` after every rebuild |
| Admin-only Sources visibility | `frontend/src/pages/ChatPage.tsx` — `isAdmin` check in `Bubble` |
| AI disclaimer per message | Same file — appended to every assistant bubble |
| No duplicate uploaded files | `app/api/v1/admin/knowledge.py` — replace-on-upload |
