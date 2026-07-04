from jane_web.rate_limit import RateLimiter, active_window_hits, rate_limit_category, stale_rate_limit_keys


def test_rate_limit_category_matches_existing_endpoint_buckets():
    assert rate_limit_category("/api/device-diagnostics") == ("", 0, 0)
    assert rate_limit_category("/api/jane/chat") == ("chat", 30, 60)
    assert rate_limit_category("/api/cli-login/code") == ("auth", 10, 60)
    assert rate_limit_category("/api/files/upload") == ("upload", 20, 60)
    assert rate_limit_category("/api/anything") == ("api", 60, 60)
    assert rate_limit_category("/chat") == ("", 0, 0)


def test_active_window_hits_uses_strict_cutoff_boundary():
    assert active_window_hits([39.9, 40.0, 40.1, 100.0], cutoff=40.0) == [40.1, 100.0]


def test_stale_rate_limit_keys_uses_last_hit_and_empty_list_policy():
    assert stale_rate_limit_keys(
        {
            "empty": [],
            "stale": [1.0, 79.9],
            "fresh": [1.0, 80.0],
        },
        now=200.0,
    ) == ["empty", "stale"]


def test_rate_limiter_blocks_after_max_requests_until_window_expires():
    now = 100.0
    limiter = RateLimiter(time_fn=lambda: now)

    assert limiter.check("rl:chat:ip", 2, 60)
    assert limiter.check("rl:chat:ip", 2, 60)
    assert not limiter.check("rl:chat:ip", 2, 60)
    assert limiter._hits["rl:chat:ip"] == [100.0, 100.0]

    now = 161.0

    assert limiter.check("rl:chat:ip", 2, 60)
    assert limiter._hits["rl:chat:ip"] == [161.0]


def test_rate_limiter_periodically_removes_stale_keys():
    now = 0.0
    limiter = RateLimiter(time_fn=lambda: now)
    assert limiter.check("stale", 10, 60)

    now = 121.0
    assert limiter.check("fresh", 10, 60)

    assert "stale" not in limiter._hits
    assert limiter._hits["fresh"] == [121.0]
    assert limiter._last_cleanup == 121.0
