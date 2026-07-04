"""Pure context-window compaction helpers."""

from __future__ import annotations


def compaction_token_target(
    *,
    current_tokens: int,
    compaction_threshold: int,
    max_tokens: int,
) -> int:
    return current_tokens - compaction_threshold + int(max_tokens * 0.25)


def clamp_compaction_split_index(split_index: int, message_count: int) -> int | None:
    if split_index >= message_count - 1:
        split_index = message_count - 2
    if split_index <= 0:
        return None
    return split_index


def compaction_split_index(
    message_token_counts: list[int],
    *,
    current_tokens: int,
    compaction_threshold: int,
    max_tokens: int,
) -> int | None:
    if current_tokens <= compaction_threshold:
        return None

    tokens_to_remove = compaction_token_target(
        current_tokens=current_tokens,
        compaction_threshold=compaction_threshold,
        max_tokens=max_tokens,
    )
    split_index = 0
    tokens_so_far = 0
    for index, count in enumerate(message_token_counts):
        tokens_so_far += count
        if tokens_so_far >= tokens_to_remove:
            split_index = index + 1
            break

    return clamp_compaction_split_index(split_index, len(message_token_counts))
