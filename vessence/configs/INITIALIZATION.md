# Amber System Initialization Manifest

This document tracks all system-level dependencies, Python environments, and local model assets required to run Amber with her full capability suite (Vision, Motor, Speech, and Memory).

## 1. System Dependencies (Apt)
- `espeak-ng`: Phoneme processing for Kokoro TTS.
- `xclip`: Clipboard automation for URL extraction.
- `ffmpeg`: (Recommended) For audio processing and conversion.
- `software-properties-common`: For repository management.

## 2. Python Environments
| Name | Type | Location | Primary Purpose |
| :--- | :--- | :--- | :--- |
| **Amber Brain** | Venv (3.13) | `$HOME/google-adk-env` | Core ADK Agent, Discord Bridge, and Reasoning. |
| **Kokoro Voice**| Conda (3.12)| `$HOME/miniconda3/envs/kokoro` | Local GPU-accelerated Text-to-Speech. |
| **OmniParser Eyes** | Venv (3.13) | `$VESSENCE_HOME/omniparser_venv` | Semantic UI parsing and element detection. |

## 3. Local Model Assets (Weights)
### Kokoro TTS
- **Model:** `$VESSENCE_HOME/models/kokoro/model.onnx`
- **Voices:** `$VESSENCE_HOME/models/kokoro/voices.json`

### OmniParser V2
- **Icon Detect (YOLOv8):** `$VESSENCE_HOME/omniparser/weights/icon_detect/model.pt`
- **Icon Caption (Florence-2):** `$VESSENCE_HOME/omniparser/weights/icon_caption_florence/`

## 4. Key Configuration Files
- **Discord Token:** `$VESSENCE_HOME/configs/katie_token.txt`
- **Environment:** `$VESSENCE_HOME/.env` (Gemini API keys, Channel IDs)
- **Service Files:** `~/.config/systemd/user/` (jane-web, jane-voice, jane-healthcheck, vault-tunnel, vessence-relay, vessence-tunnel-client). As of v0.1.71, amber-brain and amber-bridge were removed when Amber was retired.

## 5. Startup & Watchdogs
- See [Startup Operations Reference](STARTUP_REFERENCE.md) for the canonical launcher/watchdog commands and startup policy.

## 6. Maintenance Tasks (Crontab)
- **2:00 AM:** Identity Essay generation (`generate_identity_essay.py`)
- **3:00 AM:** Memory Janitor - Merges redundant facts (`janitor_memory.py`)
- **Hourly:** Check for system updates (`check_for_updates.py`)
