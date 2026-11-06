# Results

Setup: 50 users, ramp-up 5 users per second, 60 seconds. `backend3` answers `/`
300 ms late (`docker-compose.uneven.yml`). Everything runs on one laptop, so
compare the rows with each other and do not trust the absolute numbers.

## Even backends vs uneven backends (round robin)

| Backends | RPS | Median ms | p95 ms | Failures |
|---|---|---|---|---|
| Even | | | | |
| Uneven | | | | |

## Algorithms on uneven backends

Total, for all `/` requests:

| Algorithm | RPS | Median ms | p95 ms | Failures |
|---|---|---|---|---|
| round_robin | | | | |
| weighted_round_robin (3, 3, 1) | | | | |
| least_connections | | | | |
| ip_hash | | | | |

Requests per backend (the count in each `/ (backendN)` row):

| Algorithm | backend1 | backend2 | backend3 |
|---|---|---|---|
| round_robin | | | |
| weighted_round_robin (3, 3, 1) | | | |
| least_connections | | | |
| ip_hash | | | |

## A backend stops during the run

| Algorithm | Failures | What the chart showed |
|---|---|---|
| round_robin | | |
| least_connections | | |

## What I learned

-
