"""Idle-state helpers for the prompt queue runner."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def read_activity_timestamp(path: str | Path, key: str, logger: Any = None) -> float:
    try:
        with Path(path).open() as f:
            return float(json.load(f).get(key, 0) or 0)
    except FileNotFoundError:
        return 0.0
    except Exception as exc:
        if logger is not None:
            logger.warning("%s read error: %s", Path(path).name, exc)
        return 0.0


def read_activity_timestamp_any(
    path: str | Path,
    keys: Iterable[str],
    logger: Any = None,
) -> float:
    try:
        with Path(path).open() as f:
            state = json.load(f)
        for key in keys:
            ts = float(state.get(key, 0) or 0)
            if ts:
                return ts
        return 0.0
    except FileNotFoundError:
        return 0.0
    except Exception as exc:
        if logger is not None:
            logger.warning("%s read error: %s", Path(path).name, exc)
        return 0.0


def most_recent_activity_timestamp(
    sources: Iterable[tuple[str | Path, str]],
    logger: Any = None,
) -> float:
    most_recent = 0.0
    for path, key in sources:
        ts = read_activity_timestamp(path, key, logger=logger)
        if ts > most_recent:
            most_recent = ts
    return most_recent


def most_recent_activity_timestamp_any(
    sources: Iterable[tuple[str | Path, Iterable[str]]],
    logger: Any = None,
) -> float:
    most_recent = 0.0
    for path, keys in sources:
        ts = read_activity_timestamp_any(path, keys, logger=logger)
        if ts > most_recent:
            most_recent = ts
    return most_recent


def is_idle_from_timestamp(now_ts: float, last_activity_ts: float, threshold_seconds: float) -> bool:
    if last_activity_ts == 0:
        return True
    return now_ts - last_activity_ts >= threshold_seconds
