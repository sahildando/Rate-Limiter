# AWS Deployment Plan — Rate Limiter

Generated using the **AWS Deployments** plugin for this workspace.

## What this repo is

The workspace is an empty `Rate-Limiter` git repo. This plan maps a sensible **dev-sized** AWS architecture before any application code exists.

## Recommended architecture

| Layer | AWS service | Why |
|-------|-------------|-----|
| API edge | **API Gateway** | Built-in token-bucket throttling, usage plans per API key, and 429 responses ([AWS security design principles](https://docs.aws.amazon.com/whitepapers/latest/security-overview-amazon-api-gateway/security-design-principles.html)) |
| Compute | **Lambda** | Stateless request handler; ideal for low-traffic dev and bursty check/increment logic |
| Counter store | **ElastiCache Serverless (Redis)** | Sub-millisecond counters for token-bucket or sliding-window limits; scales to zero in dev per plugin defaults |
| Rule config | **DynamoDB** | Per-tenant limits, burst sizes, and window durations without redeploying code |
| Observability | **CloudWatch** | Track allowed vs. throttled requests, p99 latency, and Redis/Lambda errors |

See the diagram: [`rate-limiter-aws-architecture.drawio`](./rate-limiter-aws-architecture.drawio)

## Request flow

1. Client sends `POST /check` (or `/consume`) with an API key.
2. API Gateway enforces account- and usage-plan-level throttles.
3. Lambda loads the rule from DynamoDB (cached in-memory where possible).
4. Lambda runs `INCR` + `EXPIRE` (or Lua script) against Redis.
5. Lambda returns `{ allowed: true }` or HTTP 429; CloudWatch records the outcome.

## Estimated monthly cost (dev, ~100K requests/month)

| Service | Assumption | Est. cost |
|---------|------------|-----------|
| API Gateway | 100K REST requests | ~$0.35 |
| Lambda | 100K invocations, 128 MB, 50 ms avg | ~$0.02 |
| ElastiCache Serverless | Light dev traffic, minimal ECPUs | ~$5–15 |
| DynamoDB | On-demand, &lt;1 GB, low reads | ~$1–3 |
| CloudWatch | Basic metrics + 7-day logs | ~$1–2 |
| **Total** | | **~$8–20 / month** |

> Live pricing from the plugin's `awspricing` MCP requires AWS credentials configured locally. Re-run `/deploy` after `aws configure` for exact numbers.

## Next steps

1. Implement the Lambda handler (Node.js or Python) with Redis + DynamoDB clients.
2. Generate IaC with the `/deploy` skill (defaults to **CDK TypeScript**).
3. Create API Gateway usage plans for per-client rate tiers.
4. Add integration tests that assert 429 behavior under burst load.

## Plugin capabilities used here

- **awsknowledge** — validated API Gateway throttling patterns and ElastiCache Serverless scaling guidance
- **aws-architecture-diagram** — produced the draw.io architecture diagram in `docs/`
- **deploy** — service selection matrix and dev-sized defaults
