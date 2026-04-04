FROM chromadb/chroma:1.0.10

LABEL org.opencontainers.image.title="Vessence ChromaDB"
LABEL org.opencontainers.image.description="Pinned ChromaDB image for Vessence local memory"
LABEL org.opencontainers.image.source="https://github.com/vessence/vessence"

USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
USER chroma
