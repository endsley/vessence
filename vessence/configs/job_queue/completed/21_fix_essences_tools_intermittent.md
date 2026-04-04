# Job: Fix Intermittent Essences & Tools Not Loading on Web Jane

Status: done
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
On web Jane, clicking "Essences" and "Tools" sometimes shows nothing. The issue is intermittent — sometimes it works, sometimes it doesn't. Investigate root cause and fix.

## Investigation steps
1. Check the API endpoint that serves essences/tools list:
   - `GET /api/essences` — does it always return data?
   - Test with `curl http://localhost:8081/api/essences` multiple times
   - Check for race conditions (data not loaded yet on some requests)
2. Check frontend code in `jane.html` or `app.html`:
   - How does the essences/tools section fetch data?
   - Is it fetched on page load or on click?
   - Is there a timing issue (fetch fires before Alpine component is ready)?
   - Check browser console for JS errors when it fails
3. Check `_auto_load_essences()` in `main.py`:
   - Does it always complete before requests arrive?
   - Is there a race condition between startup and first request?
4. Check if the essences directory is accessible:
   - `ls ~/ambient/essences/` — are all essence folders intact?
   - Is there a permission issue?
5. Check server logs for errors around the time of failure

## Likely causes
- Race condition: essences not loaded yet when user clicks (startup timing)
- Alpine.js reactivity issue: data updates but template doesn't re-render
- API returns empty list on error but doesn't show error message
- Caching: stale response from browser or Cloudflare tunnel

## Verification
- Click Essences/Tools 10 times rapidly — should show every time
- Hard refresh + click immediately — should show
- Check API returns consistent data: `for i in {1..10}; do curl -s http://localhost:8081/api/essences | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('essences',[])))"; done`

## Files Involved
- `jane_web/main.py` — essences API endpoint, `_auto_load_essences()`
- `vault_web/templates/jane.html` — essences/tools UI section
- `vault_web/templates/app.html` — may also have essences section
