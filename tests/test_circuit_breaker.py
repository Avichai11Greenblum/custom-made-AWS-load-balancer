from lb.resilience.circuit_breaker import CircuitBreaker


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_breaker(failure_threshold=3, recovery_timeout=10.0):
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold, recovery_timeout, clock=clock, name="b1")
    return breaker, clock


def open_circuit(breaker, failures=3):
    for _ in range(failures):
        breaker.record_failure()


def test_starts_closed_and_available():
    breaker, _ = make_breaker()
    assert breaker.state_name == "closed"
    assert breaker.is_available()


def test_opens_after_threshold_consecutive_failures():
    breaker, _ = make_breaker(failure_threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state_name == "closed"
    breaker.record_failure()
    assert breaker.state_name == "open"
    assert not breaker.is_available()


def test_success_resets_the_failure_count():
    breaker, _ = make_breaker(failure_threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state_name == "closed"


def test_open_circuit_becomes_available_after_recovery_timeout():
    breaker, clock = make_breaker(recovery_timeout=10.0)
    open_circuit(breaker)
    clock.now = 9.9
    assert not breaker.is_available()
    clock.now = 10.0
    assert breaker.is_available()
    assert breaker.state_name == "open"  # checking availability changes nothing


def test_begin_attempt_after_timeout_moves_to_half_open_with_one_trial():
    breaker, clock = make_breaker()
    open_circuit(breaker)
    clock.now = 10.0
    breaker.begin_attempt()
    assert breaker.state_name == "half-open"
    assert not breaker.is_available()  # trial already in flight


def test_successful_trial_closes_the_circuit():
    breaker, clock = make_breaker()
    open_circuit(breaker)
    clock.now = 10.0
    breaker.begin_attempt()
    breaker.record_success()
    assert breaker.state_name == "closed"
    assert breaker.is_available()


def test_failed_trial_reopens_the_circuit_and_restarts_the_timeout():
    breaker, clock = make_breaker(recovery_timeout=10.0)
    open_circuit(breaker)
    clock.now = 10.0
    breaker.begin_attempt()
    breaker.record_failure()
    assert breaker.state_name == "open"
    clock.now = 15.0
    assert not breaker.is_available()
    clock.now = 20.0
    assert breaker.is_available()


def test_cancelled_trial_allows_another_trial():
    breaker, clock = make_breaker()
    open_circuit(breaker)
    clock.now = 10.0
    breaker.begin_attempt()
    breaker.cancel_attempt()
    assert breaker.state_name == "half-open"
    assert breaker.is_available()


def test_late_results_are_ignored_while_open():
    breaker, _ = make_breaker()
    open_circuit(breaker)
    breaker.record_success()
    assert breaker.state_name == "open"
