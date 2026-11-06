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

## Things to try

- 10 users, then 50, then 200: when does the 95th percentile start to rise?
- While a run is going, `docker compose stop backend2`. Look at failures and
  how fast they stop.
- Start it again with `docker compose start backend2` and watch it get traffic again.
