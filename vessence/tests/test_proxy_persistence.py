from jane_web.proxy_persistence import (
    privacy_local_only_for_class,
    stage3_writeback_decision,
)


def test_privacy_local_only_for_class_handles_empty_values_and_lookup_failures():
    assert not privacy_local_only_for_class(None, lambda cls: "local_only")
    assert privacy_local_only_for_class("send_message", lambda cls: "local_only")
    assert not privacy_local_only_for_class("weather", lambda cls: "normal")

    def broken_lookup(cls):
        raise RuntimeError("missing policy")

    assert not privacy_local_only_for_class("send_message", broken_lookup)


def test_stage3_writeback_decision_prioritizes_privacy_skip():
    decision = stage3_writeback_decision("stage3", privacy_local_only=True)

    assert not decision.run_stage3_writeback
    assert decision.reason == "privacy_local_only"
    assert decision.skip_log_stage == "persistence_privacy_skip_haiku_summary"


def test_stage3_writeback_decision_skips_non_stage3_work():
    decision = stage3_writeback_decision("stage2", privacy_local_only=False)

    assert not decision.run_stage3_writeback
    assert decision.reason == "non_stage3"
    assert decision.skip_log_stage == "persistence_stage2_skip_theme_summary"


def test_stage3_writeback_decision_runs_for_default_or_stage3():
    assert stage3_writeback_decision(None, privacy_local_only=False).run_stage3_writeback
    assert stage3_writeback_decision("stage3", privacy_local_only=False).run_stage3_writeback
    assert stage3_writeback_decision("STAGE3", privacy_local_only=False).run_stage3_writeback
