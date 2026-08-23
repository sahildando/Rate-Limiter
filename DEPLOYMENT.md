# Production Deployment Guide

Deploy the API Monitoring Platform using managed services. Do **not** commit secrets.

## Architecture

```
GitHub → Vercel (frontend)     GitHub → Render (API, worker, scheduler)
                │                              │
                └──────────┬───────────────────┘
                           ▼
              Neon PostgreSQL + Upstash Redis
                           │
                           ▼
                   External HTTP APIs
```

## 1. Neon PostgreSQL

1. Create a project at [neon.tech](https://neon.tech).
2. Copy the **pooled** connection string (`postgresql://...?sslmode=require`).
3. Set `DATABASE_URL` on all Render services (API, worker, scheduler).

The backend normalizes `postgresql://` → `postgresql+asyncpg://` and enables TLS for Neon hosts.

Run migrations once (Render `preDeployCommand` in `render.yaml`):

```bash
cd backend && alembic upgrade head
```

## 2. Upstash Redis

1. Create a Redis database at [upstash.com](https://upstash.com).
2. Copy the **TLS** URL (`rediss://...`).
3. Set on Render:
   - `REDIS_URL`
   - `CELERY_BROKER_URL`
   - `CELERY_RESULT_BACKEND`

Use the same Upstash URL for all three unless you prefer separate databases.

## 3. Render (API + worker + scheduler)

1. Push this repository to GitHub.
2. Open the Blueprint:
   [Create Render Blueprint](https://dashboard.render.com/blueprint/new?repo=https://github.com/sahildando/Rate-Limiter)
3. Apply the blueprint from `render.yaml`.
4. Set secret environment variables in the Dashboard:

| Variable | Required on |
|----------|-------------|
| `DATABASE_URL` | API, worker, scheduler |
| `REDIS_URL` | API, worker, scheduler |
| `CELERY_BROKER_URL` | API, worker, scheduler |
| `CELERY_RESULT_BACKEND` | API, worker, scheduler |
| `JWT_SECRET` | API, worker, scheduler |
| `CORS_ORIGINS` | API only |
| `FRONTEND_URL` | API only (optional) |

Generate `JWT_SECRET`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

5. After deploy, note the API URL (e.g. `https://api-monitoring-api.onrender.com`).

### Smoke test

```bash
chmod +x scripts/smoke-test.sh
./scripts/smoke-test.sh https://<your-api>.onrender.com
```

## 4. Vercel (frontend)

1. Import the GitHub repository in [Vercel](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = your Render API URL (no trailing slash)
4. Deploy.

Set Render `CORS_ORIGINS` to your Vercel URL, e.g.:

```
https://rate-limiter.vercel.app
```

Redeploy the API after updating CORS.

## 5. End-to-end verification

1. Open the Vercel frontend URL.
2. Register and log in.
3. Create a monitor for `https://example.com`.
4. Wait for the scheduler/worker (may take several minutes on free tier).
5. Confirm status becomes UP and checks appear.

## Known free-tier limitations

| Platform | Limitation |
|----------|------------|
| Render web | Spins down after ~15 min inactivity; cold starts add latency |
| Render worker | May sleep; monitoring is **not** true 24/7 uptime |
| Render scheduler | Single instance required to avoid duplicate enqueue |
| Neon | Storage and compute limits on free tier |
| Upstash | Request and memory limits |
| Vercel | Hobby plan limits |

This deployment demonstrates architecture and DevOps practices. It does **not** provide commercial-grade always-on monitoring while services are sleeping.

## Local development

```bash
docker compose up --build
```

Uses local PostgreSQL/Redis — not production URLs.
