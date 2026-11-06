# Load test

Sends traffic through the balancer with [locust](https://locust.io) and shows
live charts in the browser.

## Run

1. Start the backends and the balancer (round robin is the default):
   ```bash
   docker compose up -d
   uv run python -m lb.proxy
   ```
2. In a second terminal start locust:
   ```bash
   uv run python -m locust -f loadtest/locustfile.py
   ```
3. Open http://localhost:8089, set the number of users and the ramp-up, and press Start.
   The host is already `http://localhost:8080`.

## Reading the UI

- **Users**: simulated clients running at the same time.
- **Ramp up (users started/second)**: how fast users are added. A slow ramp-up
  shows where things start to degrade.
- **Statistics tab**: one row per URL, plus the totals.
  - *Median* is what a typical request takes. *95%ile* is the time that 95 % of
    requests beat, so it shows the slow tail that the median hides.
  - *Failures* counts non-2xx responses and connection errors.
- **Charts tab**: requests per second and failures, response times (median and
  95th percentile), and the number of users, all over time.
- **Download Data tab**: the HTML report and CSV files of the run.

## Uneven backends

With three identical backends every algorithm looks the same. To make them
differ, slow one down on purpose. `backend3` then waits 300 ms before answering `/`:

```bash
docker compose -f docker-compose.yml -f docker-compose.uneven.yml up -d --build
```

Back to equal backends: `docker compose up -d --build`.

The locust file now sends 90 % `GET /` and 10 % `GET /slow?seconds=0.5`. In the
Statistics tab the `/` requests get one row per backend, such as `/ (backend3)`,
so you can see the slow backend's median and 95th percentile next to the others.
The number of requests per row shows how much traffic each backend received.

Check with round robin first: the three `/` rows should have about the same
number of requests, but `backend3` should be slower. Then see what least
connections does to that (`LB_ALGORITHM=least_connections`).

## Comparing the algorithms

Run the same test once per algorithm, with the same conditions each time, so the
only difference between runs is the algorithm. Use the uneven backends from above.

### All at once

`run_comparison.py` does the steps below for every algorithm. It starts and stops
the balancer itself, so stop any balancer you started by hand first. It needs
matplotlib for the chart (`uv add --dev matplotlib`).
```bash
uv run python loadtest/run_comparison.py
```
It takes about 5 minutes (60 seconds per algorithm). At the end it prints a table
and saves `loadtest/results/comparison.png`: requests per second, response times,
and the share of requests each backend received. Useful options:
```bash
uv run python loadtest/run_comparison.py --users 100 --duration 30
uv run python loadtest/run_comparison.py --algorithms round_robin least_connections
uv run python loadtest/run_comparison.py --plot-only   # redraw from the saved results
```
The "Aggregated" numbers include the `/slow` requests (10 % of the traffic), the
same for every algorithm, so compare the algorithms with each other.

### Step by step

The command below runs locust without the browser, for exactly 60 seconds, and
saves the numbers (CSV) and a report with graphs (HTML) in `loadtest/results/`.
Stop the balancer (Ctrl+C), then for each algorithm start it again and run locust.

| Algorithm | Start the balancer with |
|---|---|
| `round_robin` | `LB_ALGORITHM=round_robin uv run python -m lb.proxy` |
| `weighted_round_robin` | `LB_ALGORITHM=weighted_round_robin LB_BACKENDS="http://localhost:8001\|3,http://localhost:8002\|3,http://localhost:8003\|1" uv run python -m lb.proxy` |
| `least_connections` | `LB_ALGORITHM=least_connections uv run python -m lb.proxy` |
| `ip_hash` | `LB_ALGORITHM=ip_hash uv run python -m lb.proxy` |

Then, in a second terminal (change `round_robin` in the two result names to match):
```bash
uv run python -m locust -f loadtest/locustfile.py --headless -u 50 -r 5 -t 60s \
  --csv loadtest/results/round_robin --html loadtest/results/round_robin.html
```

Fill in a row of `loadtest/RESULTS.md` after each run. The numbers are in the
`*_stats.csv` file (one row per URL, and one for the total) or in the HTML report.

Notes:
- Weighted round robin only differs from round robin when the weights differ, so
  it gets weights 3, 3 and 1: the slow `backend3` gets a third of the others' share.
- IP hash sends all requests from one client IP to the same backend. Every locust
  user here comes from the same IP, so all traffic should land on one backend.
  That is expected, and it is what the test is meant to show.

### Failure during the run

Repeat one or two algorithms with a backend dying in the middle. Start the same
locust command, wait about 20 seconds, then in another terminal:
```bash
docker compose stop backend1
```
Compare the failures and the response times before and after. Bring it back with
`docker compose start backend1`.

## Things to try

- 10 users, then 50, then 200: when does the 95th percentile start to rise?
- While a run is going, `docker compose stop backend2`. Look at failures and
  how fast they stop.
- Start it again with `docker compose start backend2` and watch it get traffic again.
