"""Run the same load test against every balancing algorithm and draw a comparison.

    uv run python loadtest/run_comparison.py

For each algorithm it starts the balancer, runs locust without the browser, and
stops the balancer again. Then it draws loadtest/results/comparison.png. The
backends must already be running. Use --plot-only to redraw from saved results.
"""

import argparse
import csv
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "loadtest" / "results"
LOCUSTFILE = REPO_ROOT / "loadtest" / "locustfile.py"
BALANCER_PORT = 8080  # the same address the locustfile sends traffic to
BACKEND_PORTS = (8001, 8002, 8003)

# Extra settings per algorithm. Weighted round robin only differs from plain round
# robin when the weights differ, so the slow backend3 gets a smaller weight.
ALGORITHMS: dict[str, dict[str, str]] = {
    "round_robin": {},
    "weighted_round_robin": {
        "LB_BACKENDS": "http://localhost:8001|3,http://localhost:8002|3,http://localhost:8003|1"
    },
    "least_connections": {},
    "ip_hash": {},
}


def port_is_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port: int, want_open: bool, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_open(port) == want_open:
            return True
        time.sleep(0.3)
    return False


def check_ready_to_run() -> None:
    if port_is_open(BALANCER_PORT):
        sys.exit(f"Port {BALANCER_PORT} is in use. Stop the running balancer first.")
    missing = [port for port in BACKEND_PORTS if not port_is_open(port)]
    if missing:
        sys.exit(f"Backends are not running on ports {missing}. Start them with docker compose first.")


def run_one(name: str, users: int, spawn_rate: int, duration: int) -> None:
    """Start the balancer with this algorithm, run locust against it, stop the balancer."""
    print(f"\n=== {name}: {users} users, {duration} s ===", flush=True)
    environment = {**os.environ, "LB_ALGORITHM": name, **ALGORITHMS[name]}
    with open(RESULTS_DIR / f"{name}_balancer.log", "w") as balancer_log:
        balancer = subprocess.Popen(
            [sys.executable, "-m", "lb.proxy"],
            cwd=REPO_ROOT,
            env=environment,
            stdout=balancer_log,
            stderr=subprocess.STDOUT,
        )
        try:
            if not wait_for_port(BALANCER_PORT, want_open=True, timeout=20):
                sys.exit(f"The balancer did not start. See {balancer_log.name}")
            # Locust exits with 1 when some requests failed. The results are still saved.
            subprocess.run(
                [
                    sys.executable, "-m", "locust",
                    "-f", str(LOCUSTFILE),
                    "--headless",
                    "-u", str(users),
                    "-r", str(spawn_rate),
                    "-t", f"{duration}s",
                    "--csv", str(RESULTS_DIR / name),
                    "--html", str(RESULTS_DIR / f"{name}.html"),
                    "--only-summary",
                ],
                cwd=REPO_ROOT,
            )
        finally:
            balancer.terminate()
            try:
                balancer.wait(timeout=10)
            except subprocess.TimeoutExpired:
                balancer.kill()
    wait_for_port(BALANCER_PORT, want_open=False, timeout=10)  # free the port for the next run


def read_summary(name: str) -> dict:
    """Read the numbers of one run from the CSV that locust saved."""
    with open(RESULTS_DIR / f"{name}_stats.csv", newline="") as stats_file:
        rows = {row["Name"]: row for row in csv.DictReader(stats_file)}
    total = rows["Aggregated"]
    # Rows named "/ (backend1)" hold the requests that backend answered.
    per_backend = {
        row_name[3:-1]: int(row["Request Count"])
        for row_name, row in rows.items()
        if row_name.startswith("/ (")
    }
    return {
        "rps": float(total["Requests/s"]),
        "median": float(total["Median Response Time"]),
        "p95": float(total["95%"]),
        "failures": int(total["Failure Count"]),
        "per_backend": per_backend,
    }


def print_table(summaries: dict[str, dict]) -> None:
    print(f"\n{'algorithm':<22}{'RPS':>8}{'median ms':>11}{'p95 ms':>9}{'failed':>8}  requests per backend")
    for name, summary in summaries.items():
        spread = ", ".join(f"{backend}={count}" for backend, count in sorted(summary["per_backend"].items()))
        print(f"{name:<22}{summary['rps']:>8.1f}{summary['median']:>11.0f}{summary['p95']:>9.0f}{summary['failures']:>8}  {spread}")


def plot(summaries: dict[str, dict], title: str, path: Path) -> None:
    names = list(summaries)
    labels = [f"{name.replace('_', chr(10))}\n({summaries[name]['failures']} failed)" for name in names]
    positions = range(len(names))
    figure, (rps_axes, latency_axes, share_axes) = plt.subplots(1, 3, figsize=(17, 5.5))

    rps_axes.bar(positions, [summaries[name]["rps"] for name in names])
    rps_axes.set_title("Requests per second (higher is better)")

    bar_width = 0.38
    latency_axes.bar([p - bar_width / 2 for p in positions], [summaries[n]["median"] for n in names], bar_width, label="median")
    latency_axes.bar([p + bar_width / 2 for p in positions], [summaries[n]["p95"] for n in names], bar_width, label="95th percentile")
    latency_axes.set_title("Response time in ms (lower is better)")
    latency_axes.legend()

    backends = sorted({backend for name in names for backend in summaries[name]["per_backend"]})
    bottom = [0.0] * len(names)
    for backend in backends:
        shares = []
        for name in names:
            counts = summaries[name]["per_backend"]
            shares.append(100 * counts.get(backend, 0) / (sum(counts.values()) or 1))
        share_axes.bar(positions, shares, bottom=bottom, label=backend)
        bottom = [low + share for low, share in zip(bottom, shares)]
    share_axes.set_title("Share of requests per backend (%)")
    share_axes.legend()

    for axes in (rps_axes, latency_axes, share_axes):
        axes.set_xticks(list(positions), labels)
        axes.spines[["top", "right"]].set_visible(False)
    figure.suptitle(title)
    figure.tight_layout()
    figure.savefig(path, dpi=150)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--spawn-rate", type=int, default=5, help="users started per second")
    parser.add_argument("--duration", type=int, default=60, help="seconds per algorithm")
    parser.add_argument("--algorithms", nargs="+", choices=list(ALGORITHMS), default=list(ALGORITHMS))
    parser.add_argument("--plot-only", action="store_true", help="skip the runs, redraw from saved results")
    return parser.parse_args()


def run_all_algorithms(args: argparse.Namespace) -> None:
    check_ready_to_run()
    for name in args.algorithms:
        run_one(name, args.users, args.spawn_rate, args.duration)


def report_results(args: argparse.Namespace) -> None:
    """Print the table and save the chart, from the results saved on disk."""
    summaries = {name: read_summary(name) for name in args.algorithms}
    print_table(summaries)
    chart_path = RESULTS_DIR / "comparison.png"
    plot(summaries, f"{args.users} users, {args.duration} s per algorithm", chart_path)
    print(f"\nChart saved to {chart_path}")


def main() -> None:
    args = parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if not args.plot_only:
        run_all_algorithms(args)
    report_results(args)


if __name__ == "__main__":
    main()
