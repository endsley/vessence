#!/usr/bin/env python3
"""Summarize cron token usage telemetry from NDJSON logs."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


def _default_log_path() -> Path:
    return Path(
        os.environ.get(
            "CRON_TOKEN_METER_FILE",
            str(
                Path(os.environ.get("VESSENCE_DATA_HOME", "/tmp")).expanduser()
                / "logs" / "System_log" / "cron_llm_usage.jsonl"
            ),
        )
    ).expanduser()


def _read_records(path: Path, *, since_epoch: float | None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if since_epoch is not None:
                if float(payload.get("epoch", 0.0)) < since_epoch:
                    continue
            records.append(payload)
    return records


def _print_report(records: list[dict[str, Any]], *, top_n: int) -> None:
    if not records:
        print("No telemetry records found for the selected window.")
        return

    agg = defaultdict(
        lambda: {
            "calls": 0,
            "success": 0,
            "fail": 0,
            "prompt_tokens": 0,
            "response_tokens": 0,
            "elapsed_ms": 0,
            "providers": defaultdict(int),
            "models": defaultdict(int),
        }
    )

    for record in records:
        job = record.get("job") or "unknown"
        data = agg[job]
        data["calls"] += 1
        if record.get("success"):
            data["success"] += 1
        else:
            data["fail"] += 1
        data["prompt_tokens"] += int(record.get("prompt_tokens_est", 0) or 0)
        data["response_tokens"] += int(record.get("response_tokens_est", 0) or 0)
        data["elapsed_ms"] += int(record.get("elapsed_ms", 0) or 0)
        data["providers"][record.get("provider", "unknown")] += 1
        model = (record.get("model") or "").strip()
        if model:
            data["models"][model] += 1

    rows = []
    for job, data in agg.items():
        total = data["prompt_tokens"] + data["response_tokens"]
        rows.append((job, total, data))
    rows.sort(key=lambda item: item[1], reverse=True)

    print("Cron LLM usage summary (estimated tokens)")
    print(f"window: {len(records)} calls, {len(rows)} jobs")
    print("-" * 120)
    print(
        f"{'Job':34} {'Calls':>5} {'OK':>5} {'Fail':>5} "
        f"{'PromptTok':>10} {'RespTok':>10} {'TotTok':>10} {'AvgMs':>8}"
    )
    print("-" * 120)

    for job, total, data in rows[:top_n]:
        calls = data["calls"]
        ok = data["success"]
        fail = data["fail"]
        prompt_tokens = data["prompt_tokens"]
        response_tokens = data["response_tokens"]
        avg_ms = (data["elapsed_ms"] / calls) if calls else 0.0
        print(
            f"{job[:33]:34} "
            f"{calls:5d} {ok:5d} {fail:5d} "
            f"{prompt_tokens:10d} {response_tokens:10d} {total:10d} {avg_ms:8.1f}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize cron token usage by job.")
    parser.add_argument(
        "--log-file",
        default=str(_default_log_path()),
        help="Path to cron_llm_usage.jsonl (defaults to CRON_TOKEN_METER_FILE).",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="Only include records from the last N hours.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Disable time filtering and include all records.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Show only top N jobs by estimated token usage.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.log_file).expanduser()
    since_epoch = None
    if not args.all:
        import time

        since_epoch = time.time() - (float(args.hours) * 3600.0)
    records = _read_records(path, since_epoch=since_epoch)
    _print_report(records, top_n=args.top)


if __name__ == "__main__":
    main()
