# Job #6: Investigate Jane Web Server Crash

Priority: 1
Status: pending
Created: 2026-04-04

## Description
The jane-web.service went down again. Investigate root cause and fix.

### Steps:
1. Check `journalctl --user -u jane-web.service` for crash/kill logs
2. Check `jane_request_timing.log` for the last request before crash
3. Check `healthcheck.log` for auto-restart events
4. Check memory usage — was it OOM killed?
5. Check if gemma4:e4b Ollama timeout caused the event loop to hang
6. Check if standing brain subprocess leaked

### Previous crashes:
- Earlier today: server hung (not crashed), returned empty responses. Memory peak was 6.4GB. Healthcheck timer auto-restarted it.
- Pattern: seems to happen after extended usage or when gemma4 router times out repeatedly.

### Fix candidates:
- Ensure gemma router timeout doesn't block the event loop
- Add memory limit to the service (MemoryMax in systemd)
- Improve the healthcheck to detect hung (not just down) states
