from jane_web import main
from jane_web.pipeline_selection import should_use_v2_pipeline, should_use_v3_pipeline


def test_pipeline_selection_preserves_v2_rollback_policy() -> None:
    assert should_use_v2_pipeline({}) is True
    assert should_use_v2_pipeline({"JANE_PIPELINE": "v2"}) is True
    assert should_use_v2_pipeline({"JANE_PIPELINE": " V1 "}) is False


def test_pipeline_selection_preserves_v3_opt_in_policy() -> None:
    assert should_use_v3_pipeline({}) is False
    assert should_use_v3_pipeline({"JANE_USE_V3_PIPELINE": "0"}) is False
    assert should_use_v3_pipeline({"JANE_USE_V3_PIPELINE": " 1 "}) is True
    assert should_use_v3_pipeline({"JANE_USE_V3_PIPELINE": "1"}) is True


def test_main_route_facades_use_extracted_pipeline_policy(monkeypatch) -> None:
    class Body:
        pass

    monkeypatch.setenv("JANE_PIPELINE", "v1")
    monkeypatch.setenv("JANE_USE_V3_PIPELINE", "1")

    assert main._should_use_v2(Body()) is False
    assert main._should_use_v3(Body()) is True


def test_main_app_uses_lifespan_instead_of_deprecated_event_handlers() -> None:
    assert main.app.router.lifespan_context is main._app_lifespan
    assert main.app.router.on_startup == []
    assert main.app.router.on_shutdown == []
