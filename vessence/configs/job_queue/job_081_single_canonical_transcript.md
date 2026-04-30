# Job #81: Canonicalize the Transcript Source (Discovery + Tooling + Docs)

Status: incomplete
Priority: high
Created: 2026-04-21

## Problem

Nobody — including Claude — knows where the real transcript lives, so every "read the android transcript" request turns into a fishing expedition across half a dozen partial stores. This is a **documentation + tooling gap**, not a missing-data problem.

Discovery during 2026-04-21 session: the canonical verbatim transcript **already exists** at `VAULT_HOME/conversation_history_ledger.db` (table `turns`, written by `conversation_manager._log_to_ledger` on every turn via `add_message`/`add_messages`). As of 2026-04-21 21:56 it holds 5,463 rows including every Stage 2 and Stage 3 turn. Both `add_message` and `add_messages` call `_log_to_ledger` unconditionally, so the Stage 2 short-circuit in `jane_proxy.py` does NOT skip the ledger write.

The fragmentation is in the peripheral stores (summaries, prompt inputs, empty stubs) which are easy to mistake for "the transcript."

## Fragmented Peripherals (not the canonical source — left in place)

| Store | Role | Why it's not "the transcript" |
|---|---|---|
| `VAULT_HOME/conversation_history_ledger.db` (table `turns`) | **CANONICAL** — verbatim user+assistant turns | — |
| `logs/jane_prompt_dump.jsonl` | prompt-input debug log | only records prompts going IN; missing final reply |
| `memory/v1/vector_db/short_term_memory/` Chroma | thematic summaries | summarized to ~200 chars, not verbatim; Stage 2 skipped |
| `logs/haiku_summaries.jsonl` | Haiku-generated summaries | partial, summarized |
| `data/jane_session_summaries/*.json` | per-session topic summaries | no turns |
| `vessence-data/conversation_history_ledger.db` | empty (0 bytes) | wrong path — real one lives in vault |
| `jane_chat.db`, `data/jane.db` | empty stubs | deprecated |
| Android app local UI | verbatim, client-only | server can't read it |

## Proposed Solution (scoped down after discovery)

1. **Point at the canonical store, don't build a new one.** Document `VAULT_HOME/conversation_history_ledger.db::turns` as THE transcript source.
2. **Add a thin helper script:** `agent_skills/show_transcript.py` with flags:
   - `--platform {android|web|cli|all}` — filters by session_id prefix (`jane_android_`, `jane_web_`, `jane_cli_`)
   - `-n N` — number of user+assistant pairs to show (default 3)
   - `--session <id>` — explicit session filter
   - `--since <ISO>` — time-window filter
   - Output: clean `user: ...` / `jane: ...` formatted tail, newest last.
3. **Point CLAUDE.md at the helper.** One line: "Read any transcript with `agent_skills/show_transcript.py [--platform X] [-n N]`." So Claude Code knows instantly, no hunting.
4. **Delete or clearly mark the empty stubs** (`vessence-data/conversation_history_ledger.db`, `jane_chat.db`, `data/jane.db`) so they stop being bait.
5. **Update docs:** `configs/memory_manage_architecture.md` + `configs/CODE_MAP.md` to explicitly name the canonical path.

## Files to Modify

- `agent_skills/show_transcript.py` (new) — the helper
- `CLAUDE.md` (project root) — one-line pointer to the helper
- `configs/memory_manage_architecture.md` — name the canonical store
- `configs/CODE_MAP.md` / `CODE_MAP_CORE.md` — already references `LEDGER_DB_PATH`; add "canonical transcript" annotation
- (optional) delete the 0-byte stubs under `vessence-data/`

## Decisions to Confirm With Chieh

1. Keep peripheral stores (prompt_dump, haiku_summaries, short_term chroma) as-is? They serve memory/retrieval purposes, not transcript display — leaving them seems right, but confirm.
2. Delete the empty stub DBs, or leave them alone?
3. Should the helper also expose a web endpoint (e.g. `/api/transcript?platform=android&n=3`) so the phone/web UI can render a unified history view? Or is a CLI helper enough for now?
4. Retention policy on the canonical ledger — it's at 5,463 rows / 3.3 MB. Never prune? Archive old sessions monthly? Leave alone?

## Secondary Bug Surfaced During Discovery (worth its own job?)

Session `jane_android_3b191135`, turn 5463:
- User: "okay can you tell me more about patient number two"
- Jane: "I don't have detail records for okay can you tell me more patient number two this week."

The Stage 2 clinic_schedules_info handler literal-substituted the raw user query into a "no record for X" template instead of resolving "patient number two" against the list it had just presented (Mock Patient at 8:30am on Wednesday). Garbled output + wrong semantic behavior.

## Acceptance Criteria

- `agent_skills/show_transcript.py --platform android -n 3` prints the last 3 verbatim user+jane pairs for the most recent android session, cleanly formatted.
- CLAUDE.md includes a pointer so "read the android transcript" is a one-command answer.
- `configs/memory_manage_architecture.md` names `VAULT_HOME/conversation_history_ledger.db::turns` as the canonical transcript source.
- Empty stub DBs are either removed or clearly documented as reserved-not-used.

## Result
Jane web is not running — skipping
