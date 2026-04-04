# Job: Docker Slim-Down — Remove Amber, Pull ChromaDB, Install CLIs at Boot

Status: complete
Completed: 2026-03-24 19:00 UTC
Notes: Removed Amber service from docker-compose.yml. Changed ChromaDB from build to image pull (chromadb/chroma:1.0.10). Removed Node.js + 3 CLIs from Jane Dockerfile — replaced with first-boot install_brain.sh that installs only the chosen brain. Pip trimming added (sympy, kubernetes, pygments, pillow, opentelemetry, pip). Onboarding switched to Alpine. ADK_SERVER_URL and AMBER_URL removed from env.
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
Reduce the Docker download package from 1.3 GB to ~470 MB by removing Amber, pulling ChromaDB from Docker Hub, and installing CLIs at first boot instead of baking them into the image.

## Changes

### 1. Remove Amber container
- Delete `docker/amber/Dockerfile`
- Remove `amber` service from `docker-compose.yml`
- Remove `configs/requirements_adk.txt` from Docker context
- Saves: 3.31 GB uncompressed

### 2. Pull ChromaDB at install time
- Remove `docker/chromadb/Dockerfile`
- Remove `chromadb` build section from `docker-compose.yml`
- Change to `image: chromadb/chroma:1.0.10` (pulled from Docker Hub)
- Update install.sh/install.bat to include `docker pull chromadb/chroma:1.0.10`
- Saves: 785 MB from download

### 3. Install CLI brains at first boot
- Remove the `npm install -g` layer from Jane Dockerfile (saves 623 MB)
- Remove Node.js install from Jane Dockerfile (saves 270 MB)
- Add a first-boot script (`/app/install_brain.sh`) that:
  - Reads `JANE_BRAIN` from .env
  - Installs only the chosen CLI: `npm install -g @google/gemini-cli` OR `@anthropic-ai/claude-code` OR `openai-cli`
  - Installs Node.js only if needed
  - Marks installation complete with a flag file
  - Runs automatically on container start before uvicorn
- Onboarding wizard sets `JANE_BRAIN` in .env during setup
- Saves: ~893 MB from image

### 4. Update install scripts
- `install.sh` / `install.bat`:
  ```
  docker load -i vessence-images.tar.gz       # Jane + Onboarding only (~470 MB compressed)
  docker pull chromadb/chroma:1.0.10          # From Docker Hub (~350 MB)
  docker compose up -d                         # First boot installs chosen CLI
  ```

### 5. Update docker-compose.yml
- Remove amber service
- Change chromadb to use `image:` instead of `build:`
- Add entrypoint wrapper for Jane that runs install_brain.sh before uvicorn

### 6. Trim unused pip packages from Jane image (~162 MB saved)
Add to Dockerfile after pip install:
```dockerfile
RUN pip uninstall -y sympy kubernetes pygments pillow pip \
    opentelemetry-api opentelemetry-sdk opentelemetry-exporter-gcp-logging \
    opentelemetry-exporter-gcp-monitoring opentelemetry-exporter-gcp-trace \
    opentelemetry-exporter-otlp-proto-common opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-exporter-otlp-proto-http opentelemetry-proto \
    opentelemetry-resourcedetector-gcp opentelemetry-semantic-conventions \
    2>/dev/null; true
```

Packages confirmed safe to remove (tested):
| Package | Size | Why safe |
|---|---|---|
| sympy | 74 MB | Optional onnxruntime dep, not used at runtime |
| kubernetes | 35 MB | ChromaDB k8s deployment mode, not used (tested: ChromaDB works without it) |
| opentelemetry-* | ~15 MB | Observability/tracing, not needed for local use |
| pygments | 10 MB | Terminal syntax highlighting via rich, not needed in Docker |
| pillow | 19 MB | Orphan — nothing requires it |
| pip | 11 MB | Not needed after install |

Packages that MUST stay:
| Package | Size | Why |
|---|---|---|
| onnxruntime | 53 MB | ChromaDB embedding model |
| numpy | 70 MB | Core math for onnxruntime/chromadb |
| tokenizers | 11 MB | Embedding tokenization |
| hf_xet | 11 MB | HuggingFace model download |
| chromadb + rust bindings | 60 MB | Core memory system |

Also test: can grpcio (17 MB) be removed? ChromaDB PersistentClient may not need it. Test by uninstalling and running a query.

## Expected sizes

| Component | Before | After |
|---|---|---|
| Download package | 1.3 GB | **~350-400 MB** |
| Jane image | 2.01 GB | ~390 MB (Python + trimmed deps only) |
| Onboarding image | 265 MB | 265 MB (unchanged) |
| ChromaDB | Bundled (785 MB) | Pulled at install (~350 MB from Docker Hub) |
| Amber | 3.31 GB | Gone |
| CLI install | Baked in (893 MB) | First boot (~200-400 MB depending on choice) |
| Pip trimming | — | Saves 162 MB from Jane image |

## Verification
- `docker compose up` starts without Amber
- ChromaDB pulls from Docker Hub on first run
- CLI installs on first boot based on JANE_BRAIN setting
- Jane responds to messages after first-boot install completes
- Package zip is under 500 MB

## Files Involved
- `docker-compose.yml` — remove amber, change chromadb to image pull
- `docker/amber/` — delete entirely
- `docker/chromadb/` — delete (use upstream image)
- `docker/jane/Dockerfile` — remove Node.js and npm install layers
- `docker/jane/install_brain.sh` — new first-boot CLI installer
- `install.sh` / `install.bat` — add docker pull for chromadb
- `jane_web/main.py` — remove Amber-related routes if any

## Notes
- First boot will take ~2-3 min longer (CLI install) but subsequent boots are instant (flag file check)
- Users without internet after initial install can't switch brains (need npm for new CLI)
- The Onboarding wizard should show a progress bar during first-boot CLI installation
