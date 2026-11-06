# Python Load Balancer

An asynchronous HTTP reverse proxy and load balancer written from scratch in Python (aiohttp), with health checks, a circuit breaker, runtime administration, AWS alerts and metrics (on LocalStack), and a load test that compares the balancing algorithms.

I built it to learn how traffic is spread over many servers and to practise applying design patterns to real code, not as a replacement for nginx or HAProxy.

```
                         +--> backend1 (FastAPI, Docker)
client --> [ load balancer ] --> backend2
              |   |        +--> backend3
              |   +-- admin API (127.0.0.1:8081): add / remove / drain backends
              +-- alerts (SNS -> SQS) and metrics (CloudWatch), via LocalStack
```

## What it does

- **Proxying:** streams request and response bodies, strips hop-by-hop headers, sets `X-Forwarded-For`.
- **Four balancing algorithms**, chosen by config: round robin, weighted round robin, least connections, IP hash.
- **Active health checks:** failing backends leave rotation after consecutive failed probes and return after consecutive passes.
- **Circuit breaker per backend:** fed by real traffic, so a backend that passes `/health` but returns 5xx still gets cut off, then probed with a single trial request.
- **Safe retries:** GET/HEAD/OPTIONS without a body are retried on another backend. Other requests are never repeated.
- **Load shedding:** a limit on concurrent requests returns 503 instead of falling over.
- **Admin API:** list, add, remove, drain and undrain backends while the balancer runs, with no restart. Draining waits for in-flight requests to finish.
- **AWS integration (optional, LocalStack):** SNS alerts when a backend goes down or up or a circuit opens or closes, and CloudWatch metrics for requests, errors, latency and healthy backend count.

## Design patterns

| Pattern | Where |
|---|---|
| Strategy + Factory | the balancing algorithms and the function that builds one by name |
| Observer | health and circuit events are published once, and listeners (logs, alerts) react independently |
| State | the circuit breaker: closed, open, half-open |
| Decorator / chain | the middleware layers (logging, metrics, load shedding) and the background AWS sinks |
| Registry | one `BackendRegistry` shared by the proxy, health checker and admin API |
| Adapter | `AlertSink` and `MetricsSink` hide AWS behind interfaces, so the balancer runs without it |

## Load test results

Run with locust: 150 users, 60 seconds per algorithm, with `backend3` made 300 ms slower on purpose. Everything ran on one laptop, so compare the rows with each other and treat the numbers as indicative.

| Algorithm | Requests/s | Median latency | Traffic to the slow backend |
|---|---|---|---|
| Round robin | ~245 | ~20 ms | 33 % |
| Weighted round robin (3, 3, 1) | ~270 | ~5 ms | ~14 % |
| Least connections | ~290 | ~5 ms | ~9 % |
| IP hash | ~180 | ~310 ms | 100 % |

What it shows:
- Round robin ignores how fast a backend is and sends it a third of the traffic.
- Weighted round robin helps only because the weights were set by hand.
- Least connections adapts to the slow backend with no configuration.
- IP hash sends all traffic from one client IP to the same backend. That suits sticky sessions, not a load test run from one machine.

No request failed in any run. See [loadtest/](loadtest/) to reproduce it, including a script that runs every algorithm and draws the comparison chart.

## Quick start

Needs Docker and [uv](https://docs.astral.sh/uv/).

```bash
docker compose up -d                  # three backends on :8001-8003
uv sync
uv run python -m lb.proxy             # balancer on :8080, admin API on 127.0.0.1:8081
```

```bash
for i in 1 2 3 4 5 6; do curl -s localhost:8080/; echo; done       # spread over the backends
curl -s localhost:8081/admin/backends                              # state of every backend
curl -s -X POST "localhost:8081/admin/drain?url=http://localhost:8001"
curl -s -X POST localhost:8081/admin/backends -d '{"url": "http://localhost:8004", "weight": 2}'
```

Choose the algorithm with `LB_ALGORITHM` (`round_robin`, `weighted_round_robin`, `least_connections`, `ip_hash`). Weights go in the backend list: `LB_BACKENDS="http://localhost:8001|3,http://localhost:8002|1"`.

### AWS alerts and metrics (optional)

```bash
docker compose -f docker-compose.aws.yml up -d
LB_AWS_ENABLED=true uv run python -m lb.proxy
uv run python -m lb.aws.read_alerts     # print the alerts that arrived
uv run python -m lb.aws.read_metrics    # print the latest metrics
```

Off by default. If LocalStack is unreachable at startup, the balancer logs an error and runs without alerts or metrics.

## Configuration

All settings are environment variables, read in [lb/config.py](lb/config.py).

| Variable | Default | Meaning |
|---|---|---|
| `LB_ALGORITHM` | `round_robin` | balancing algorithm |
| `LB_BACKENDS` | three local backends | `url\|weight,url\|weight` (empty starts with none) |
| `LB_PORT` / `LB_ADMIN_PORT` | `8080` / `8081` | proxy and admin API ports |
| `LB_MAX_ATTEMPTS` | `3` | backends tried for a retryable request |
| `LB_MAX_IN_FLIGHT` | `1000` | concurrent requests before answering 503 |
| `LB_HEALTH_INTERVAL` | `2` | seconds between health probes |
| `LB_CB_FAILURE_THRESHOLD` / `LB_CB_RECOVERY_TIMEOUT` | `5` / `10` | failures that open the circuit, seconds before a trial |
| `LB_AWS_ENABLED` | `false` | turn on SNS alerts and CloudWatch metrics |

## Decisions worth knowing

- **Only safe requests are retried.** A body can be read only once, and repeating a POST could do the work twice.
- **The admin API has no authentication, so it only listens on `127.0.0.1`.**
- **AWS can never break proxying.** boto3 calls block, so they run on worker threads, and delivery errors are logged and swallowed.
- **A new backend starts unhealthy** and gets traffic only after the health checker has seen it pass, so a server that is not up yet never gets requests.
- **A circuit alert fires once per outage.** While a backend stays broken the breaker retries every recovery period, and each failed trial would otherwise repeat the alert.
- **LocalStack is pinned to 4.12.** Older images lack the CloudWatch protocol current boto3 uses, and releases from 2026.03 need an auth token.

## Tests and CI

```bash
uv run pytest
```

Unit and integration tests cover the algorithms, health checks, circuit breaker, middleware, registry, admin API, alerts and metrics. AWS calls are tested against mocks, so no LocalStack is needed. GitHub Actions runs the suite on every pull request and every push to `main`.

## Project layout

```
lb/
  proxy.py              entrypoint: forwarding, retries
  config.py             settings from environment variables
  choose_servers_algos/ the four algorithms and their factory
  resilience/           circuit breaker, health checker
  observers/            events, listeners, alert listeners
  middleware/           logging, metrics, load shedding
  backend_servers_pool/ backend model and registry
  admin/                runtime administration API
  metrics/              request counters and the metrics publisher
  aws/                  SNS / SQS / CloudWatch adapters, check and read scripts
backend/                the FastAPI test backend
loadtest/               locust test, comparison script and results
tests/
```

## Limitations

Single process (one event loop), HTTP only (no TLS termination, no WebSocket upgrade), health checks are HTTP `GET`, and metrics are reported for the balancer as a whole, not per backend. PLAN.md has the stage-by-stage history of how it was built.
