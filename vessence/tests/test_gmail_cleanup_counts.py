from agent_skills.gmail_cleanup_counts import add_outcome_count, count_message_outcomes, merge_outcome_counts


def test_count_message_outcomes_counts_successes_and_failures():
    failures = []

    def process_one(message_id):
        if message_id == "bad":
            raise RuntimeError("boom")
        return "processed" if message_id != "skip" else "skipped"

    counts = count_message_outcomes(
        ["ok-1", "skip", "bad", "ok-2"],
        process_one,
        failure_outcome="failed",
        log_failure=lambda message_id, exc: failures.append((message_id, str(exc))),
    )

    assert counts == {"processed": 2, "skipped": 1, "failed": 1}
    assert failures == [("bad", "boom")]


def test_outcome_count_helpers_merge_and_increment():
    counts = {"processed": 1}

    add_outcome_count(counts, "processed")
    add_outcome_count(counts, "skipped", 3)
    merge_outcome_counts(counts, {"processed": 2, "failed": 1})

    assert counts == {"processed": 4, "skipped": 3, "failed": 1}
