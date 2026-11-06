"""Traffic for the load test: python -m locust -f loadtest/locustfile.py

Each simulated user sends GET / to the balancer, waits a short random time, and
repeats. Locust reports requests per second, response times and failures.
"""

from locust import HttpUser, between, task


class BalancerUser(HttpUser):
    host = "http://localhost:8080"
    wait_time = between(0.1, 0.5)  # pause between two requests of the same user

    @task
    def get_root(self) -> None:
        self.client.get("/")
