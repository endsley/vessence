# Job: Verify Gemma Pre-warm on Startup

Status: complete
Completed: 2026-03-24 14:20 UTC
Notes: Pre-warm confirmed working. First request after cold restart: classification gap is 0-2ms (was 29s). Total greeting response time: 9.3s (was 62s). Gemma stays loaded between requests. Pre-warm log shows "pre-warmed successfully" on each startup.
Priority: 2
Model: sonnet
Created: 2026-03-24

## Objective
Verify the gemma3:4b pre-warm added to jane-web startup actually reduces first-classification latency. Compare timing logs before and after.

## Steps
1. Restart jane-web service
2. Check logs for "Pre-warming Ollama model: gemma3:4b" and "pre-warmed successfully"
3. Send a test message via web Jane immediately after startup
4. Check `jane_request_timing.log` — the gap between `start` and `session_summary_load` should be <2s (not 29s like before)
5. If pre-warm failed or didn't help, investigate: is Ollama unloading the model between the warm-up and first real request?
6. If Ollama unloads after idle, add `ollama keep_alive` or send periodic pings

## Verification
- First classification after cold restart completes in <3s
- Timing log confirms no 29s gap

## Files Involved
- `jane_web/main.py` (_prewarm_ollama function)
- `vessence-data/logs/jane_web.log`
- `vessence-data/logs/jane_request_timing.log`
