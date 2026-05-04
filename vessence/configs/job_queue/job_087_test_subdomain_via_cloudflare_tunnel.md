# Job #087 — Set up test.waterlilywellness.com via Cloudflare Tunnel

Priority: 2
Status: pending
Created: 2026-05-03
Estimated effort: Small (1-2 hours, mostly waiting for DNS propagation)

## Summary

Stand up `test.waterlilywellness.com` as a public hostname that points at the local
static mirror of the Waterlily Wellness site (`~/code/waterlily`, served by
`python3 -m http.server 8088 --bind 127.0.0.1`). Localhost is behind NAT/router,
so traversal must go through a Cloudflare Tunnel — no port forwarding, no exposing
home IP. Domain is registered at GoDaddy; tunnel + DNS will be managed at Cloudflare.

This job was scoped in a prior session but blocked at step 1 because the existing
Cloudflare API token can't create new zones. Picking this up requires either a
manual zone-add in the Cloudflare dashboard OR a new API token with zone-create
permission. Everything after that is automatable.

---

## Context Captured From Prior Session (2026-05-03)

### Domain state at GoDaddy

- Domain: `waterlilywellness.com` (owned by Chieh; GoDaddy domainId 153956666)
- Expires: 2026-09-11, renewable, locked, transfer-protected = false
- Current nameservers: `NS51.DOMAINCONTROL.COM`, `NS52.DOMAINCONTROL.COM` (GoDaddy default)
- Live `A` records resolve to Squarespace IPs: `198.185.159.144`, `198.185.159.145`,
  `198.49.23.144`, `198.49.23.145`
- The live www site is hosted on Squarespace and must keep working after we move DNS

### Cloudflare account state

- Existing CF account: `7447e4e400ff76c6c9b6792a353c3d15` (Juliusctw@gmail.com's Account)
- The account already runs `vessences.com` and a named tunnel for it
  (`vault-tunnel.service`) — so `cloudflared` 2026.3.0 is installed at
  `/usr/local/bin/cloudflared` and the user knows the workflow
- Two CF tokens stored in `$VESSENCE_DATA_HOME/.env`:
  `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_DNS_TOKEN` (also `CLOUDFLARE_TUNNEL_TOKEN`,
  `CLOUDFLARE_DOMAIN`)
- Both API tokens are valid and account-scoped, but **neither has
  `Account → Zone : Edit` (zone create) permission.** Verified via
  `POST /zones`, which returns:
  > Requires permission "com.cloudflare.api.account.zone.create" to create zones
  > for the selected account
- Tokens DO appear to have DNS-edit on existing zones (which is why the existing
  vessences.com tunnel works) — so once the zone exists, the existing tokens
  should be enough to manage DNS records and the new tunnel

### Local site state

- Path: `~/code/waterlily/`
- Run command: `python3 -m http.server 8088 --bind 127.0.0.1`
- Entry point: `http://127.0.0.1:8088/www.waterlilywellness.com/index.html`
- It's a wget mirror of the live Squarespace site plus custom additions
  (`local-assets/calendar.css`, `calendar.js`, `auth.css`, `auth.js`).
- See `~/code/waterlily/PROPRIETARY_TODO.md` for proprietary features the static
  mirror cannot reproduce (booking, cart, search, gift cards, forms, OAuth wiring).

### Credentials saved

- `~/ambient/vault/private/credentials/godaddy.json` (chmod 600)
  - Key: `9EGJhPhqCwj_3DCY32aL1sYXNJytGt5hc5`
  - Secret: `6iVykX58S36e4kgwZrg3ei`
  - Verified working via `GET /v1/domains` → 200
  - **Sensitive note:** during prior-session investigation, the GoDaddy
    `GET /v1/domains/waterlilywellness.com` response leaked the registrant
    contact info AND the EPP `authCode` into the conversation transcript.
    Consider rotating the authCode in the GoDaddy control panel before
    continuing this job.

---

## Architecture Decision

Cloudflare Tunnel requires Cloudflare to manage DNS for the hostname.
Subdomain-only delegation isn't viable on the free plan. Therefore we move the
**entire `waterlilywellness.com` zone** to Cloudflare. The risk is that any
existing record we don't replicate will go dark when nameservers flip — so we
inventory the GoDaddy zone first and mirror it before flipping.

Path NOT taken: A-record at GoDaddy → home public IP + port-forward. Rejected
because it exposes the home IP and skips Cloudflare entirely (user explicitly
said "use cloudflare").

---

## Implementation Plan

### Step 0 — Unblock zone creation (USER ACTION REQUIRED)

Pick one of:

**Option A (recommended, manual):**
1. Open https://dash.cloudflare.com/?to=/:account/add-site
2. Add `waterlilywellness.com` on the **Free** plan
3. Tell the agent the assigned NS pair (or just say "done" — the agent can
   look them up via `GET /zones?name=waterlilywellness.com` once the zone
   exists, which the existing token CAN do)

**Option B (fully API-driven, requires new token):**
1. Create a new API token at https://dash.cloudflare.com/profile/api-tokens
   with these permissions:
   - `Account → Zone : Edit` (grants zone create)
   - `Zone → DNS : Edit`
   - `Account → Cloudflare Tunnel : Edit`
2. Account resources: include the Juliusctw@gmail.com account
3. Save the new token to `~/ambient/vault/private/credentials/cloudflare.json`
   alongside the GoDaddy creds, then ChromaDB-log the location

### Step 1 — Inventory existing GoDaddy DNS

```bash
KEY=$(jq -r .key ~/ambient/vault/private/credentials/godaddy.json)
SEC=$(jq -r .secret ~/ambient/vault/private/credentials/godaddy.json)
curl -s -H "Authorization: sso-key $KEY:$SEC" \
  "https://api.godaddy.com/v1/domains/waterlilywellness.com/records" \
  | python3 -m json.tool > /tmp/godaddy_records.json
```

Save this output verbatim. Expect at minimum:
- `A` records at apex pointing to Squarespace IPs
- `CNAME` for `www` → Squarespace endpoint
- Possibly `MX` records (email — DO NOT break)
- Possibly `TXT` records (SPF, DKIM, DMARC, domain verification)

### Step 2 — Create / locate the zone in Cloudflare

If user did Option A, fetch the zone ID:
```bash
CF_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' ~/ambient/vessence-data/.env | cut -d= -f2-)
ZONE_ID=$(curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?name=waterlilywellness.com" \
  | jq -r '.result[0].id')
NS=$(curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID" \
  | jq -r '.result.name_servers[]')
echo "Zone: $ZONE_ID, NS: $NS"
```

If user did Option B, POST to /zones first, then capture the same fields.

### Step 3 — Replicate every GoDaddy record into Cloudflare

For each record from Step 1, create the equivalent in Cloudflare:
```bash
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CF_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"type":"A","name":"@","content":"198.185.159.144","ttl":1,"proxied":false}'
# repeat for every record
```

**Important:** keep `proxied: false` for records that point at Squarespace.
Squarespace requires direct DNS to its edge — proxying through Cloudflare
will break TLS/cert provisioning.

After populating, double-check by `dig @<one-of-CF-NS> waterlilywellness.com any`
matches what `dig +short waterlilywellness.com any` returned before the move.

### Step 4 — Flip GoDaddy nameservers (DESTRUCTIVE — confirm with user)

```bash
curl -s -X PUT "https://api.godaddy.com/v1/domains/waterlilywellness.com" \
  -H "Authorization: sso-key $KEY:$SEC" \
  -H "Content-Type: application/json" \
  --data '{"nameServers":["<cf-ns-1>","<cf-ns-2>"]}'
```

Propagation: typically 5-60 minutes; sometimes hours. Cloudflare will email
when the zone goes "active". Monitor with:
```bash
watch -n 30 'dig +short NS waterlilywellness.com'
```

### Step 5 — Create the tunnel and route the subdomain

Reuse the same approach as the existing `vault-tunnel.service`. Either:

**5a — using `cloudflared tunnel create` (preferred, generates credentials file):**
```bash
cloudflared tunnel login   # only if not already authenticated
cloudflared tunnel create waterlily-test
# Captures the tunnel UUID and writes ~/.cloudflared/<UUID>.json
cloudflared tunnel route dns waterlily-test test.waterlilywellness.com
```

Then write `~/.cloudflared/waterlily-test-config.yml`:
```yaml
tunnel: <UUID>
credentials-file: /home/chieh/.cloudflared/<UUID>.json
ingress:
  - hostname: test.waterlilywellness.com
    service: http://127.0.0.1:8088
  - service: http_status:404
```

**5b — install as a user systemd service** (mirror `vault-tunnel.service`):
```ini
# ~/.config/systemd/user/waterlily-tunnel.service
[Unit]
Description=Cloudflare Tunnel — test.waterlilywellness.com
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/cloudflared tunnel --config /home/chieh/.cloudflared/waterlily-test-config.yml run
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable --now waterlily-tunnel.service
```

### Step 6 — Make sure the local server is actually running

The tunnel only works if `python3 -m http.server 8088 --bind 127.0.0.1` is up.
Either:
- Run it under a `tmux`/`screen` session manually, OR
- Add a second user systemd service: `waterlily-static.service` that runs the
  python http.server in `~/code/waterlily/`

Recommend the systemd option for parity with how Jane and the vault are
managed:

```ini
# ~/.config/systemd/user/waterlily-static.service
[Unit]
Description=Waterlily local static mirror (port 8088)
After=network-online.target

[Service]
WorkingDirectory=/home/chieh/code/waterlily
ExecStart=/usr/bin/python3 -m http.server 8088 --bind 127.0.0.1
Restart=on-failure

[Install]
WantedBy=default.target
```

### Step 7 — End-to-end verify

```bash
curl -sI https://test.waterlilywellness.com | head -20
# Expect HTTP/2 200, server: cloudflare, content-type: text/html

# And in a browser, the index page should redirect or 404 gracefully —
# the working URL is:
# https://test.waterlilywellness.com/www.waterlilywellness.com/index.html
```

If the entry point is awkward, consider adding a small `index.html` redirector
at `~/code/waterlily/index.html` that JS-redirects to
`/www.waterlilywellness.com/index.html`.

### Step 8 — Update configs

- `configs/Jane_architecture.md` — add `test.waterlilywellness.com` to the
  Cloudflare tunnels section (alongside vault.vessences.com / jane.vessences.com)
- `configs/CRON_JOBS.md` — N/A (no cron, but document the systemd services if
  the doc covers user services)
- ChromaDB memory — log a `(infrastructure)` fact recording the new tunnel,
  domain status (zone moved to CF on YYYY-MM-DD), and the local port mapping

---

## Acceptance Criteria

- [ ] `dig +short NS waterlilywellness.com` returns Cloudflare nameservers
- [ ] `dig +short test.waterlilywellness.com` returns a Cloudflare anycast IP
- [ ] `curl -sI https://test.waterlilywellness.com` returns HTTP 200 via cloudflare
- [ ] Live `www.waterlilywellness.com` (Squarespace) STILL WORKS — no regression
- [ ] Email delivery to `@waterlilywellness.com` (if any MX records existed)
      still works — verify by sending a test email if applicable
- [ ] `waterlily-tunnel.service` and `waterlily-static.service` both
      `active (running)` and survive a reboot
- [ ] Tunnel credentials file (`~/.cloudflared/<UUID>.json`) is `chmod 600`
- [ ] `configs/Jane_architecture.md` updated
- [ ] ChromaDB logged with topic=`infrastructure`, subtopic=`waterlily`

---

## Risks and Watch-outs

1. **Squarespace site goes dark after nameserver flip.** Mitigation: replicate
   every record verbatim in Step 3 BEFORE flipping in Step 4. Test with
   `dig @<cf-ns> waterlilywellness.com` before flipping.
2. **Email breaks.** If MX records exist, they MUST be replicated. Don't
   proxy MX through Cloudflare — Cloudflare doesn't proxy SMTP.
3. **TLS cert provisioning.** Cloudflare auto-provisions a Universal SSL cert
   once the zone is active. The tunnel uses Cloudflare's edge cert
   automatically — no Let's Encrypt setup needed. But the FIRST request after
   activation may fail until the cert is issued (usually <15 minutes).
4. **GoDaddy authCode exposure.** See "Credentials saved" note above — rotate
   the EPP authCode if there's any concern.
5. **Free plan zone limit.** Cloudflare Free allows unlimited zones, but the
   Juliusctw@gmail.com account already has at least vessences.com — no issue
   expected, but worth noting.
6. **The static mirror has CDN absolute URLs** (`assets.squarespace.com`,
   `static1.squarespace.com`, `images.squarespace-cdn.com`) — those will still
   resolve to Squarespace's CDN over the public internet, so the test page
   should render fully even when proxied through our tunnel.

---

## Useful one-liners for the next session

```bash
# Read GoDaddy creds
KEY=$(jq -r .key ~/ambient/vault/private/credentials/godaddy.json)
SEC=$(jq -r .secret ~/ambient/vault/private/credentials/godaddy.json)
GD="Authorization: sso-key $KEY:$SEC"

# Read CF token
CF=$(grep '^CLOUDFLARE_API_TOKEN=' ~/ambient/vessence-data/.env | cut -d= -f2-)
CFH="Authorization: Bearer $CF"

# Inventory GoDaddy
curl -s -H "$GD" https://api.godaddy.com/v1/domains/waterlilywellness.com/records | jq

# After zone exists, fetch CF zone id + NS
curl -s -H "$CFH" "https://api.cloudflare.com/client/v4/zones?name=waterlilywellness.com" | jq

# List tunnels
cloudflared tunnel list
```
