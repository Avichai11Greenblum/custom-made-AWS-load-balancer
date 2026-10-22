# Python Load Balancer (learning project)

## Goal
Learn how to operate many servers at once by building a load balancer from scratch in Python, practice design patterns, and mix in AWS services for free via LocalStack.

## Architecture
```
client -> [Load Balancer (Python async reverse proxy)] -> backend-1..N (FastAPI containers)
                |
                +-> LocalStack: CloudWatch (metrics), SNS (alerts)
```
Everything runs via docker compose.
Stack: uv, FastAPI (backends), aiohttp or httpx + Starlette (LB), boto3, pytest, LocalStack.

## Repo layout
```
load-balancer/
  pyproject.toml            # uv
  PLAN.md
  docker-compose.yml
  backend/                  # tiny FastAPI app: /, /health, /slow, returns its own hostname
    Dockerfile
  lb/
    app.py                  # proxy entrypoint
    algorithms/             # Strategy: round_robin, weighted, least_connections, ip_hash
    health.py               # active health checker (background task)
    events.py               # Observer: backend_up/down -> subscribers
    registry.py             # backend pool (Singleton/Registry)
    factory.py              # builds algorithm from config
    middleware.py           # Decorator/chain: logging, timing, retry
    aws/                    # CloudWatch + SNS adapters (Adapter pattern)
    config.py
  tests/
```

## Stages
1. **Backends + compose**: FastAPI backend image, run 3 replicas, curl each directly.
2. **Minimal proxy**: LB forwards requests to a hard-coded list (plain round robin).
3. **Strategy pattern**: algorithms behind one interface; add weighted, least-connections, ip-hash; Factory picks by config.
4. **Health checks + Observer**: background checks, remove/restore dead backends, publish events.
5. **Resilience**: retries/timeouts, circuit breaker (State pattern), graceful drain; middleware chain (Decorator).
6. **Dynamic pool**: Registry + admin API to add/remove backends at runtime; scale with `docker compose up --scale`.
7. **AWS via LocalStack**: CloudWatch metrics (req/s, latency, healthy count) and SNS alert on backend down, behind an Adapter so real AWS is just an endpoint swap.
8. **Load test + compare**: locust/hey against each algorithm; optionally benchmark against nginx.

## Design patterns map
| Pattern | Where |
|---|---|
| Strategy | balancing algorithms |
| Factory | build algorithm from config |
| Observer | health events -> logging, metrics, alerts |
| Singleton/Registry | backend pool |
| Decorator/Chain | request middleware |
| State | circuit breaker |
| Adapter | AWS clients |

## Verification
- Per stage: `uv run pytest`, plus `docker compose up` and a curl loop showing responses spread across backend hostnames.
- Kill a backend container: traffic stops going to it, SNS alert appears in LocalStack, it returns after restart.
- Stage 7: `aws --endpoint-url=http://localhost:4566 cloudwatch list-metrics` shows custom metrics.

## Status
- [ ] Stage 1 ... [ ] Stage 8 (nothing started)
