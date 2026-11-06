"""Traffic for the load test: python -m locust -f loadtest/locustfile.py

Each simulated user repeatedly sends a request to the balancer and waits a short
random time. Most requests are GET /, some are GET /slow. Successful GET /
requests are listed per backend in the Statistics tab, using the name the
backend puts in its answer.
"""

from locust import HttpUser, between, task


class BalancerUser(HttpUser):
    host = "http://localhost:8080"
    wait_time = between(0.1, 0.5)  # pause between two requests of the same user

    @task(9)
    def get_root(self) -> None:
        with self.client.get("/", catch_response=True) as response:
            if response.ok:
                backend_name = response.json().get("name", "unknown")
                response.request_meta["name"] = f"/ ({backend_name})"

    @task(1)
    def get_slow(self) -> None:
        self.client.get("/slow?seconds=0.5", name="/slow")
