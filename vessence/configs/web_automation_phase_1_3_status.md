# Web Automation — Phase 1–3 Status

**Shipped:** 2026-04-19 (overnight)
**Spec:** `configs/project_specs/web_automation_skill.md`
**Test coverage:** 60 unit + 2 live Playwright smoke tests green
**Review panels:** Two Gemini reviews landed (Phase 1 + Phase 2/3), critical findings applied inline. Codex timed out on both.

### Critical fixes applied from Gemini reviews

**Phase 1 review (pre-Phase 2):**
- Memory leak in SnapshotStore → now a `WeakKeyDictionary`.
- Ref-based risk classification was ignoring the element's role/name → `classify_action` now resolves the ref through the snapshot store ("click e04" sees "Delete Account" and elevates to high risk).
- `substring` URL matching was false-positiving ("company" → "pay") → now word-boundary with a token-split matcher.
- Silent a11y snapshot failures would make Opus loop → now raise `SnapshotError`.
- Zombie Chromium on server exit → atexit shutdown registered.
- `extract` on textbox returned empty → now uses `input_value()` for textbox/searchbox roles.

**Phase 2/3 review:**
- Path traversal through IDs → strict regex `^[a-zA-Z0-9_\-]+$` / `^s_[a-f0-9]{16}$` / `^wf_[a-f0-9]{16}$` on all get/delete.
- Iframe credential exfiltration → `fill_secret` now resolves the element's OWNING frame URL (not top-level page.url) for domain binding.
- Index last-write-wins race → `fcntl.flock` exclusive lock + atomic temp-rename on every index mutation in `secrets.py` and `workflow.py`.
- Corrupt index silently wiping on next write → now raises `SecretIndexCorrupted` / `WorkflowIndexCorrupted` instead of returning `{}`.
- `/api/docs` endpoints missing auth → now `Depends(require_auth)`.
- `bind_check` only checked the first navigate step → now iterates every navigate in the plan.
- Soft-delete name collision on restore → explicit guard, refuses to clobber a newer workflow.

---

## What works right now

All endpoints require the normal Jane auth cookie (Google-OAuth session).

### Phase 1 — Ad-hoc plan

Run a scripted browser plan end-to-end in one session.

```bash
curl -X POST http://localhost:8081/api/web_automation/plan \
  -H 'Content-Type: application/json' \
  -d '{
    "steps": [
      {"action": "navigate", "args": {"url": "https://example.com"}},
      {"action": "snapshot", "args": {}},
      {"action": "extract",  "args": {}}
    ],
    "headless": true
  }'
```

Action vocabulary:

| Action | Args | Purpose |
|---|---|---|
| `navigate` | `url`, `wait?` | Load a URL |
| `snapshot` | — | Accessibility tree + compact `e01`-style refs |
| `status` | — | Current URL + title |
| `click` | `ref` | Click an element by snapshot ref |
| `fill` | `ref`, `text` | Type into a textbox |
| `fill_secret` | `ref`, `secret_id`, `field?` | Type a stored credential (domain-bound) |
| `press` | `key` | Keyboard press (Enter, Escape, Tab…) |
| `select` | `ref`, `value` | Select dropdown option |
| `wait` | `for_`, `timeout_ms?` | Wait for load state / url_contains / text |
| `extract` | `ref?` | Read text (or input value for textboxes) |
| `screenshot` | `path`, `reason?` | Full-page PNG |

High/critical-risk actions (navigating to `/checkout`, clicking a "Delete Account" button, etc.) require `"confirm": true` on the step. The risk classifier is **perception-aware** — it resolves `click(ref=e04)` to the element's role+name before deciding the tier.

### Phase 2 — Named profiles + encrypted secrets

```bash
# Create a profile (no auth yet — placeholder storage_state).
curl -X POST http://localhost:8081/api/web_automation/profiles \
  -d '{"display_name": "citywater", "domain": "citywater.com"}'

# Do a one-time login capture — opens a VISIBLE browser, you log in
# manually, it saves the post-login cookies.
curl -X POST http://localhost:8081/api/web_automation/profiles/citywater/capture \
  -d '{
    "login_url": "https://citywater.com/login",
    "success_url_pattern": "citywater.com/(dashboard|account)",
    "timeout_s": 300
  }'

# Run a plan using the saved profile.
curl -X POST http://localhost:8081/api/web_automation/plan \
  -d '{"profile_id": "citywater", "steps": [...]}'
```

Secrets are Fernet-encrypted, domain-bound, and never surface plaintext in logs/traces:

```bash
# Create.
curl -X POST http://localhost:8081/api/web_automation/secrets \
  -d '{"domain": "citywater.com", "label": "login", "username": "chieh", "password": "..."}'
# → {"secret_id": "s_<16hex>"}

# Use via fill_secret inside a plan:
{"action": "fill_secret", "args": {"ref": "e03", "secret_id": "s_...", "field": "password"}}
```

A `fill_secret` against a DIFFERENT domain raises `SecretDomainMismatch` — the primary defense against prompt-injection exfiltration.

### Phase 3 — Named workflows (save + replay)

```bash
# Save.
curl -X POST http://localhost:8081/api/web_automation/workflows \
  -d '{
    "name": "pay water bill",
    "description": "Log in and pay the current invoice",
    "browser_profile_id": "citywater",
    "steps": [
      {"action": "navigate", "args": {"url": "https://citywater.com/account"}},
      {"action": "snapshot"},
      {"action": "click", "args": {"ref": "e04"}, "requires_confirmation": true}
    ]
  }'
# → {"workflow_id": "wf_<16hex>"}

# List.
curl http://localhost:8081/api/web_automation/workflows

# Run by name.
curl -X POST 'http://localhost:8081/api/web_automation/workflows/pay%20water%20bill/run'

# Soft-delete (restorable for 30 days).
curl -X DELETE 'http://localhost:8081/api/web_automation/workflows/pay%20water%20bill'
```

Saving the same name twice reuses the same `workflow_id` (edit semantics), so existing run records stay linked.

---

## What does NOT work yet (and why)

| Missing | Status | Reason |
|---|---|---|
| Opus-driven `[[CLIENT_TOOL:web.*]]` mid-stream tool loop | Deferred | Iterative agent loop needs jane_proxy rewrite — the existing CLIENT_TOOL extractor treats browser tools as sync client dispatches. Runs as one-shot plans for now; user can curl the endpoint directly. |
| `semantic.py` observe/act/extract | Deferred | Opus in Stage 3 is already the semantic layer per spec section 9.7 — a dedicated module is a cost/caching optimization, not a correctness requirement. |
| Workflow recording during ad-hoc | Not wired | Schema lands in Phase 3 but the capture-during-session hook is a Phase 4 feature. |
| Self-healing selector re-match | Not wired | Needs `semantic.py`. |
| noVNC / screenshot streaming to Android | Out of scope | Explicitly Phase 4 per spec 9.2. |
| Scheduled workflow runs (cron) | Out of scope | Explicitly Phase 4 per spec 9.9 — six named blockers listed there. |

---

## Quick smoke test

```bash
# End-to-end, real Chromium, no profile, no creds.
curl -sX POST http://localhost:8081/api/web_automation/plan \
  -H 'Content-Type: application/json' \
  -d '{"steps":[{"action":"navigate","args":{"url":"https://example.com"}},{"action":"extract","args":{}}],"headless":true}' \
  | python3 -m json.tool
```

Expected: `"ok": true`, `summary` contains "This domain is for use in documentation examples".

---

## File map

```
agent_skills/web_automation/
  __init__.py            # module surface
  browser_session.py     # Playwright singleton + per-task context (Phase 1)
  snapshot.py            # a11y tree + compact refs (Phase 1)
  actions.py             # typed action registry inc. fill_secret (Phase 1+2)
  safety.py              # perception-aware risk classifier (Phase 1 + Gemini fixes)
  artifacts.py           # run records + secret redaction (Phase 1)
  skill.py               # run_task + dispatch_action orchestrator (Phase 1)
  profiles.py            # domain-bound auth profiles (Phase 2)
  secrets.py             # Fernet-encrypted credential store (Phase 2)
  workflow.py            # named save/load/replay + soft-delete (Phase 3)

jane_web/jane_v2/classes/web_automation/
  __init__.py
  metadata.py            # classifier metadata, escalation_context
  handler.py             # always declines → Stage 3 (Opus drives)

intent_classifier/v2/classes/
  web_automation.py             # 40 exemplars
  web_automation_adversarial.json  # 30 adversarial phrases, 0 false positives

test_code/web_automation/
  test_safety.py         # 7 tests
  test_snapshot.py       # 5 tests
  test_artifacts.py      # 7 tests
  test_actions_and_skill.py  # 11 tests
  test_phase2.py         # 21 tests (profiles, secrets, fill_secret, perception, iframe guard, traversal, corrupt-index halt)
  test_phase3.py         # 9 tests (workflow save/load/list/delete/rebuild)
  test_live_smoke.py     # 2 live Playwright tests (RUN_LIVE=1)

jane_web/main.py         # 11 new endpoints: /api/web_automation/{plan,profiles,secrets,workflows}
```

---

## Open Gemini-flagged items not yet fixed

From the Phase 1 review (applied most; these remain):

- **Link href resolution** is fragile on pages with many repeated link texts (e.g. multiple "Read more" links). Low priority — most sites have unique visible link text.
- **Recursion in `snapshot.walk()`** could hit the Python limit on a pathologically deep DOM. Unlikely in practice.
- **Download artifact cleanup** — `accept_downloads=True` is enabled but we don't sweep `/tmp` yet. Cleanup sweeper is on the Phase 3.5 TODO.
