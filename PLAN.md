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
    proxy.py                # proxy entrypoint
    config.py               # settings from environment variables
    app_keys.py             # typed keys for shared objects on the aiohttp app
    backend_servers_pool/
      backend_server.py     # BackendServer dataclass
      registry.py           # backend pool (Singleton/Registry), Stage 6
    choose_servers_algos/   # Strategy: round_robin, weighted, least_connections, ip_hash
      factory.py            # builds a strategy by name
    resilience/
      circuit_breaker.py    # State pattern
      health_checker.py     # active health checker (background task)
    observers/              # Observer pattern
      health_events.py      # event publisher + BackendUp/BackendDown events
      event_listener.py     # EventListener base class (one subclass per reaction)
      listeners.py          # concrete listeners (logging for now)
    middleware/             # Decorator/chain: request logging, max in flight
    admin/
      api.py                # admin API on its own port: drain, undrain (Stage 6 adds more)
    aws/                    # CloudWatch + SNS adapters (Adapter pattern), Stage 7
  tests/
```

## Stages
1. **Backends + compose**: FastAPI backend image, run 3 replicas, curl each directly.
2. **Minimal proxy**: LB forwards requests to a hard-coded list (plain round robin).
3. **Strategy pattern**: algorithms behind one interface; add weighted, least-connections, ip-hash; Factory picks by config.
4. **Health checks + Observer**: background checks, remove/restore dead backends, publish events.
5. **Resilience**, in two parts:
   - **5a**: retries on connection errors/timeouts (safe requests only) + circuit breaker per backend (State pattern).
   - **5b-i**: middleware chain (Decorator): request logging with timing, max-in-flight load shedding.
   - **5b-ii**: graceful drain (`draining` flag, finish in-flight requests, no new ones).
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
- [x] Stage 1: backends + compose
- [x] Stage 2: minimal proxy (aiohttp, `lb/proxy.py`)
- [x] Stage 3: Strategy + Factory, tests, CI
- [x] Stage 4: health checks + Observer
- [x] Stage 5a: retries + circuit breaker
- [x] Stage 5b-i: middleware chain (written, needs verification)
- [x] Stage 5b-i: middleware chain
- [ ] Stage 5b-ii: graceful drain (written, needs verification; admin API grows in Stage 6)
- [ ] Stage 6: dynamic pool
- [ ] Stage 7: AWS via LocalStack
- [ ] Stage 8: load test + compare
