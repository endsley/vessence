from jane_web.cache_control import cache_control_header


def test_cache_control_header_matches_existing_path_classes():
    assert cache_control_header("/static/app.js") == "public, max-age=86400"
    assert cache_control_header("/api/briefing/image/article-1") == "public, max-age=3600"
    assert cache_control_header("/api/files") == "no-store"
    assert cache_control_header("/") == "no-cache"
    assert cache_control_header("/chat") == "no-cache"
