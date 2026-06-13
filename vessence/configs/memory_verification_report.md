# Memory Verification Report — 2026-06-13 02:43

Checked: 20 | Stale: 13 | Fixed: 13 | Deleted: 0 | Errors: 0 | Skipped recent: 189

- **UPDATED** `d6737ef0-b55` — Confirmed from actual code: alembic heads reports 0077_section_event_border_color, the listed migration files exist, and app/db/models.py plus services still contain the referenced tables/global LaTeX macro architecture. The old 0056 head claim is stale.
- **UPDATED** `4e7a059b-b5a` — Verified the current code: all substantive claims are correct, but the stored memory is truncated at the Module display_title.
- **UPDATED** `4c1fe65b-dfa` — Confirmed against standing_codex.py, persistent_codex.py, memory_retrieval.py, install_codex_memory.py, codex_auto_memory.py, codex_memory_mcp.py, and current ~/.codex state; the old memory was truncated and incomplete.
- **UPDATED** `7c38acc8-a32` — Confirmed from the Markdown note, lecture series index, and pdfinfo: paths, deck ID, title, and 30-slide count are correct; only the final trigger/title text was truncated.
- **UPDATED** `e3bd58d1-099` — Code confirms the durable distribution and prompt-cache claims. Codex was wrong that nothing is listening on 127.0.0.1:8501; ss shows uvicorn bound there. Updated to remove the unverified historical restart claim and keep durable facts.
- **UPDATED** `51540a64-7e1` — Confirmed against the actual repo. Codex was right that the memory is partially stale: q2 and q8 are randomized now, while the q1-q12 registry coverage and q3/q7/q9/q10/q11/q12 descriptions match current code.
- **UPDATED** `8f16fbf6-501` — Confirmed from scripts/run_dev_local.sh, app/main.py, the enabled user systemd unit, and /tmp logs; the old chieh-class-v2-dev-8501 service/log names are stale.
- **UPDATED** `310bdda4-225` — Codex was right: the main claims match the current code, but the trailing deploy fragment is incomplete and has no matching current-code reference.
- **UPDATED** `migrated-lon` — Confirmed from configs/templates/user_profile.md, git check-ignore, startup_code/claude_full_startup_context.py, ~/.claude/settings.json, startup_code/claude_smart_context.py, context_builder/v1/claude_smart_context.py, and context_builder/v1/context_builder.py. Codex was right that only the startup-context claim was stale.
- **UPDATED** `migrated-lon` — Code confirms Codex was mostly right: v3 Stage 2 writes FIFO and ledger but does not mutate state.history, and ChromaDB writeback only happens on qualifying Stage 3 non-local turns.
- **UPDATED** `migrated-lon` — The code confirms the original memory was stale/incomplete: current handler prefers params when present, gates ask/low confidence, and keeps incoherent bodies in a Stage 2 confirmation flow.
- **UPDATED** `migrated-lon` — Actual code confirms the memory was truncated and overbroad: the resolver now clears high-precision interrupts/topic pivots, and Stage 2 follow-up dispatch has an LLM continuation check for longer replies, but short clinic schedule prompts can still be swallowed by todo_list and forced to Stage 3.
- **UPDATED** `migrated-lon` — Code confirms the FIFO/skip_fifo implementation and completed job status; the stale part was the open commitment/restart-pending framing. Codex was broadly right, with the nuance that only streaming Stage 3 uses stream_message directly.
