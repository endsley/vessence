# JANE_BOOTSTRAP.md — Vessence Installation

## Quick Start

From the repo root (e.g. `~/ambient`):

```bash
bash vessence/setup.sh
```

That's it. The script handles everything:

1. **Prerequisites** — checks Python 3.11+ and Git
2. **Python environment** — creates venv, installs all dependencies
3. **Data directories** — creates `vessence-data/`, `vault/`, `essences/`
4. **Memory seed** — copies Jane's starter memory database
5. **Config file** — generates `.env` with session secret
6. **Your info** — asks your name, detects/selects AI brain, collects API keys
7. **Agent linking** — symlinks the right config (CLAUDE.md / GEMINI.md / AGENTS.md)
8. **Test run** — starts the server briefly to verify it works
9. **Auto-start** — registers systemd (Linux) or launchd (macOS) service
10. **Remote access** — optional relay setup for phone/external access
11. **Get to know you** — optional quick questions so Jane knows you from day one

After setup, open **http://localhost:8081** in your browser.

## Windows

WSL2 is required. Run `wsl --install` in PowerShell as Administrator, reboot, then run the setup script inside the WSL terminal.

## Updating

```bash
cd ~/ambient/vessence && git pull
cd ~/ambient && ./venv/bin/pip install -r vessence/requirements.txt
# Linux: systemctl --user restart jane-web.service
# macOS: launchctl unload ~/Library/LaunchAgents/com.vessence.jane-web.plist && launchctl load ~/Library/LaunchAgents/com.vessence.jane-web.plist
```

## Troubleshooting

- **Port 8081 in use**: Another service is on that port. Stop it or change the port in the service config.
- **Server won't start**: Check `journalctl --user -u jane-web.service -f` (Linux) or `tail -f vessence-data/logs/jane-web.log` (macOS).
- **No AI CLI found**: Install one — `npm install -g @anthropic-ai/claude-code` or `npm install -g @google/gemini-cli`.
- **Bug?** Open an issue at https://github.com/endsley/vessence/issues
