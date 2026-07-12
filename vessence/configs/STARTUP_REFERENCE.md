# Startup Operations Reference

Use this file as the canonical location for startup, restart, and bootstrap
entry points referenced across the docs.

## Live process startup

- **Core launcher:** `$VESSENCE_HOME/startup_code/start_all_bots.sh`
  - Starts Amber ADK (`localhost:8000`), Amber Discord bridge, and Jane bridge.
  - Run this after restore or environment rebuild.
- **Watchdog:** `$VESSENCE_HOME/startup_code/bot_watchdog.sh`
  - Legacy process supervisor for bot/service recovery checks.
  - Current status: documented as disabled in cron notes since Discord
    disconnected on 2026-03-22.

## Bootstrap and recovery entry points

- **Identity/bootstrap sequence:** [JANE_INITIALIZATION_SEQUENCE.md](JANE_INITIALIZATION_SEQUENCE.md)
- **Bootstrap digest:** `JANE_BOOTSTRAP_TTL_SECONDS=1200 PYTHONPATH="$VESSENCE_HOME" "$VESSENCE_HOME/startup_code/jane_bootstrap.py"`
- **Bootstrap cache policy:** 20-minute default (`JANE_BOOTSTRAP_TTL_SECONDS`) for startup identity retention.
- **System restart (zero-downtime):** `bash "$VESSENCE_HOME/startup_code/graceful_restart.sh"`
- **Restart design spec:** `configs/specs/zero_downtime_restart.md`
- **Agent restore bootstrap:** `bash "$VESSENCE_HOME/startup_code/restore_agent.sh"`

## Cron wrappers used by automation

- **Daily harvester:** `bash $VESSENCE_HOME/startup_code/run_marketplace_cron.sh`
- **Facebook marketplace cleanup:** `bash $VESSENCE_HOME/startup_code/run_facebook_marketplace_message_cleanup.sh`

## Notes

- `start_all_bots.sh` and `graceful_restart.sh` are the command-level sources of truth for
  local process boot and zero-downtime rollout behavior.
