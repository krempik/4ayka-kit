import time
from types import SimpleNamespace

from ayka.middleware import RateLimiter, _client_ip


def test_allow_then_block():
    rl = RateLimiter(max_requests=3, window_seconds=60)
    assert [rl.allowed("a") for _ in range(3)] == [True, True, True]
    assert rl.allowed("a") is False


def test_buckets_isolated():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    assert rl.allowed("a") is True
    assert rl.allowed("b") is True


def test_admin_limits_stricter():
    rl = RateLimiter(max_requests=1000, admin_max_requests=2)
    assert rl.allowed("x") is True
    assert rl.allowed("x", protected=True) is True
    assert rl.allowed("x", protected=True) is True
    assert rl.allowed("x", protected=True) is False  # admin bucket full
    assert rl.allowed("x") is True  # normal bucket unaffected


def test_protected_prefix():
    rl = RateLimiter(protected_prefixes=("/api/admin/",))
    assert rl.is_protected("/api/admin/stats")
    assert not rl.is_protected("/api/msg")


def test_window_expires():
    rl = RateLimiter(max_requests=1, window_seconds=0.05)
    assert rl.allowed("a") is True
    assert rl.allowed("a") is False
    time.sleep(0.06)
    assert rl.allowed("a") is True


def test_client_ip_takes_leftmost_forwarded():
    req = SimpleNamespace(
        headers={"x-forwarded-for": "1.2.3.4, 10.0.0.1, 203.0.113.5"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert _client_ip(req) == "1.2.3.4"


def test_client_ip_falls_back_to_socket():
    req = SimpleNamespace(headers={}, client=SimpleNamespace(host="203.0.113.9"))
    assert _client_ip(req) == "203.0.113.9"


def test_client_ip_ignores_unknown():
    req = SimpleNamespace(
        headers={"x-forwarded-for": "unknown, 10.0.0.1"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert _client_ip(req) == "127.0.0.1"