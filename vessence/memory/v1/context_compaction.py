"""Pure context-window compaction helpers."""

from __future__ import annotations


def compaction_split_index(
    message_token_counts: list[int],
    *,
    current_tokens: int,
    compaction_threshold: int,
    max_tokens: int,
) -> int | None:
    if current_tokens <= compaction_threshold:
        return None

    tokens_to_remove = (
        current_tokens - compaction_threshold
        + int(max_tokens * 0.25)
    )
    split_index = 0
    tokens_so_far = 0
    for index, count in enumerate(message_token_counts):
        tokens_so_far += count
        if tokens_so_far >= tokens_to_remove:
            split_index = index + 1
            break

    if split_index >= len(message_token_counts) - 1:
        split_index = len(message_token_counts) - 2
    if split_index <= 0:
        return None
    return split_index
