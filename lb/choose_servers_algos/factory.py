from lb.choose_servers_algos.base import ServerStrategy
from lb.choose_servers_algos.ip_hash import IpHash
from lb.choose_servers_algos.least_connections import LeastConnections
from lb.choose_servers_algos.round_robin import RoundRobin
from lb.choose_servers_algos.weighted_round_robin import WeightedRoundRobin

ALGORITHMS: dict[str, type[ServerStrategy]] = {
    "round_robin": RoundRobin,
    "weighted_round_robin": WeightedRoundRobin,
    "least_connections": LeastConnections,
    "ip_hash": IpHash,
}


def create_server_strategy(name: str) -> ServerStrategy:
    try:
        return ALGORITHMS[name]()
    except KeyError:
        raise ValueError(f"Unknown algorithm {name!r}. Choose from: {', '.join(ALGORITHMS)}")
