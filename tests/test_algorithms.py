from collections import Counter

import pytest

from lb.backend_servers_pool.backend_server import BackendServer
from lb.config import parse_backends
from lb.choose_servers_algos.factory import create_server_strategy


def make_backends(*weights: int) -> list[BackendServer]:
    return [BackendServer(url=f"http://b{i}", traffic_weight=w) for i, w in enumerate(weights, start=1)]


def test_round_robin_cycles_in_order():
    backends = make_backends(1, 1, 1)
    algo = create_server_strategy("round_robin")
    picked = [algo.choose_server(backends, "1.1.1.1").url for _ in range(6)]
    assert picked == ["http://b1", "http://b2", "http://b3"] * 2


def test_weighted_round_robin_respects_weights():
    backends = make_backends(5, 1, 1)
    algo = create_server_strategy("weighted_round_robin")
    counts = Counter(algo.choose_server(backends, "1.1.1.1").url for _ in range(70))
    assert counts == {"http://b1": 50, "http://b2": 10, "http://b3": 10}


def test_weighted_round_robin_is_smooth():
    backends = make_backends(5, 1, 1)
    algo = create_server_strategy("weighted_round_robin")
    first_seven = [algo.choose_server(backends, "1.1.1.1").url for _ in range(7)]
    # The heavy backend must not take all 5 turns in a row.
    assert first_seven.count("http://b1") == 5
    assert first_seven != ["http://b1"] * 5 + ["http://b2", "http://b3"]


def test_least_connections_picks_least_busy():
    backends = make_backends(1, 1, 1)
    backends[0].active_connections = 5
    backends[1].active_connections = 1
    backends[2].active_connections = 3
    algo = create_server_strategy("least_connections")
    assert algo.choose_server(backends, "1.1.1.1").url == "http://b2"


def test_least_connections_rotates_between_ties():
    backends = make_backends(1, 1, 1)
    algo = create_server_strategy("least_connections")
    picked = {algo.choose_server(backends, "1.1.1.1").url for _ in range(3)}
    assert picked == {"http://b1", "http://b2", "http://b3"}


def test_ip_hash_is_sticky():
    backends = make_backends(1, 1, 1)
    algo = create_server_strategy("ip_hash")
    first = algo.choose_server(backends, "10.0.0.7").url
    assert all(algo.choose_server(backends, "10.0.0.7").url == first for _ in range(10))


def test_ip_hash_spreads_different_clients():
    backends = make_backends(1, 1, 1)
    algo = create_server_strategy("ip_hash")
    picked = {algo.choose_server(backends, f"10.0.0.{i}").url for i in range(50)}
    assert len(picked) > 1


def test_factory_rejects_unknown_name():
    with pytest.raises(ValueError):
        create_server_strategy("does_not_exist")


def test_parse_backends_with_and_without_weight():
    backends = parse_backends("http://a:1|3, http://b:2")
    assert [(b.url, b.traffic_weight) for b in backends] == [("http://a:1", 3), ("http://b:2", 1)]


def test_parse_backends_empty_string_means_no_backends():
    assert parse_backends("") == []
