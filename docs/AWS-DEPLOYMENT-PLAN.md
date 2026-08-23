# AWS Deployment Plan — API Monitoring Platform

> **Updated:** This repo now has a full FastAPI + Next.js + Celery stack. See **[AWS-DEPLOY.md](./AWS-DEPLOY.md)** for the CDK deployment guide.

## Recommended architecture (dev-sized)

| Layer | AWS service | Why |
|-------|-------------|-----|
| API | **ECS Fargate + ALB** | FastAPI is a long-running WSGI/ASGI app — Fargate matches the existing Docker setup |
| Workers | **ECS Fargate** | Celery worker + scheduler (same image, different commands) |
| PostgreSQL | **Aurora Serverless v2** | Scales down in dev; matches async SQLAlchemy + Alembic |
| Redis | **ElastiCache Serverless** | Rate limits, locks, Celery broker |
| Frontend | **Amplify Hosting** | Next.js dashboard with `NEXT_PUBLIC_API_URL` |
| Secrets | **Secrets Manager** | JWT + Aurora credentials |

See the diagram: [`rate-limiter-aws-architecture.drawio`](./rate-limiter-aws-architecture.drawio)

## Estimated monthly cost (dev)

| Service | Est. cost |
|---------|-----------|
| NAT Gateway + Aurora + Fargate + ALB + Redis | **~$125–140 / month** |

See [AWS-DEPLOY.md](./AWS-DEPLOY.md) for the full breakdown.

## Deploy

```bash
./scripts/deploy-aws.sh
```

Infrastructure code lives in [`infra/`](../infra/).
