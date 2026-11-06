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

## Things to try

- 10 users, then 50, then 200: when does the 95th percentile start to rise?
- While a run is going, `docker compose stop backend2`. Look at failures and
  how fast they stop.
- Start it again with `docker compose start backend2` and watch it get traffic again.
