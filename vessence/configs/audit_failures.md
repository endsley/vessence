# Audit Failures

Failed audit attempts — auditor couldn't generate tests, fix bugs, or
ran out of time. These are pointers for human review.
Newest entries appended at bottom by `agent_skills/nightly_code_auditor.py`.

## 2026-05-09 01:00 — jane_web/jane_v2/classes/greeting/handler.py
Test generation failed.

## 2026-05-13 01:00 — jane_web/jane_v2/classes/shopping_list/handler.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/classes/shopping_list/handler.py', '--no-verify']' returned non-zero exit status 1.

