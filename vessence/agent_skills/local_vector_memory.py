# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import os
import sys
import time as _time

class silence_stderr_fd:
    def __enter__(self):
        self.stdout_fd = os.dup(1)
        self.stderr_fd = os.dup(2)
        self.null_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.null_fd, 1)
        os.dup2(self.null_fd, 2)

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.dup2(self.stdout_fd, 1)
        os.dup2(self.stderr_fd, 2)
        os.close(self.null_fd)
        os.close(self.stdout_fd)
        os.close(self.stderr_fd)

# Silence onnxruntime noise
os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')
with silence_stderr_fd():
    import chromadb
import uuid
import logging
import datetime
import ollama
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
from typing import Sequence, Optional
from google.genai import types
from google.adk.memory.base_memory_service import BaseMemoryService
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.memory.base_memory_service import SearchMemoryResponse

logger = logging.getLogger('discord_agent.memory.local_vector')

FORGETTABLE_TTL_DAYS = 7  # Forgettable memories expire after this many days


class LocalVectorMemoryService(BaseMemoryService):
    """
    A local memory service using ChromaDB for vector storage and 
    Qwen 2.5 Coder as a 'Librarian' to summarize the Top 200 results.
    """

    def __init__(self, uri: str, **kwargs):
        # uri format: localvector:///path/to/db
        path = uri.replace("localvector://", "")
        if path.startswith("/"):
            self._db_path = path
        else:
            self._db_path = os.path.abspath(path)
        
        logger.info(f"Initializing LocalVectorMemoryService at {self._db_path}")
        self._client = chromadb.PersistentClient(path=self._db_path)
        # Use Cosine similarity for better semantic matching
        with silence_stderr_fd():
            self._collection = self._client.get_or_create_collection(
                name="user_memories",
                metadata={"hnsw:space": "cosine"}
            )

    def _user_filter(self, user_id: str):
        return {"user_id": user_id}

    async def add_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        memories: Sequence[MemoryEntry],
        custom_metadata: Optional[dict] = None,
    ) -> None:
        for entry in memories:
            fact_text = self._extract_text(entry.content)
            if not fact_text:
                continue

            memory_type = (custom_metadata or {}).get("memory_type", "long_term")
            metadata = {
                "user_id": user_id,
                "app_name": app_name,
                "author": entry.author or "user",
                "timestamp": entry.timestamp or datetime.datetime.utcnow().isoformat(),
                "memory_type": memory_type,
            }
            if memory_type == "forgettable":
                expires_at = (
                    datetime.datetime.utcnow() +
                    datetime.timedelta(days=FORGETTABLE_TTL_DAYS)
                ).isoformat()
                metadata["expires_at"] = expires_at
            if custom_metadata:
                metadata.update(custom_metadata)

            self._collection.add(
                ids=[str(uuid.uuid4())],
                documents=[fact_text],
                metadatas=[metadata]
            )

    async def search_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        query: str,
    ) -> SearchMemoryResponse:
        """
        Fetches Top 100 raw results and uses local Qwen to provide a single summarized response.
        """
        # 1. Fetch Top 100 from Chroma (capped to collection size to avoid ChromaDB error)
        # NOTE: No user_id filter — this is a single-user system. Jane's memories (saved without
        # user_id metadata) must be visible to Amber, so we search the full collection.
        with silence_stderr_fd():
            n_results = min(100, self._collection.count())
            if n_results == 0:
                return SearchMemoryResponse(memories=[])
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )

        if not results["documents"] or not results["documents"][0]:
            return SearchMemoryResponse(memories=[])

        # 2. Bucket results into tiers, filtering expired forgettable entries
        now_iso = datetime.datetime.utcnow().isoformat()
        permanent_facts, long_term_facts, forgettable_facts = [], [], []

        def _is_expired(meta):
            exp = meta.get("expires_at", "")
            if not exp:
                return False
            try:
                return str(exp) < now_iso  # ISO strings compare lexicographically
            except Exception:
                return False

        def _fmt(doc, meta):
            ts = meta.get("timestamp", meta.get("created_at", "Unknown Time"))
            topic = meta.get("topic", "General")
            exp = meta.get("expires_at", "")
            expiry_str = f", expires {str(exp)[:10]}" if exp else ""
            return f"[{str(ts)[:19]}] ({topic}{expiry_str}): {doc}"

        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            mtype = meta.get("memory_type", "long_term")
            if mtype == "forgettable":
                if not _is_expired(meta):
                    forgettable_facts.append(_fmt(doc, meta))
            elif mtype == "permanent":
                permanent_facts.append(_fmt(doc, meta))
            else:
                long_term_facts.append(_fmt(doc, meta))

        sections = []
        if permanent_facts:
            sections.append("## Permanent Memory\n" + "\n".join(permanent_facts))
        if long_term_facts:
            sections.append("## Long-Term Memory\n" + "\n".join(long_term_facts))
        if forgettable_facts:
            sections.append(
                "## Recent/Forgettable Memory  ← highest recency, treat as most current\n"
                + "\n".join(forgettable_facts)
            )

        if not sections:
            return SearchMemoryResponse(memories=[])

        facts_block = "\n\n".join(sections)

        # 3. Call Qwen 'The Librarian' locally to synthesize
        system_instr = (
            f"You are the Memory Librarian for {os.environ.get('USER_NAME', 'the user')}'s assistant. "
            "Your task is to analyze the provided tiered memories relative to the user's query. "
            "Synthesize a single, high-fidelity, and concise summary of all relevant facts. "
            "Rules:\n"
            "1. Recency priority: Recent/Forgettable > Long-Term > Permanent. "
            "When facts contradict, the more recent tier wins.\n"
            "2. 'Recent/Forgettable Memory' captures recent work, changes, and discoveries — "
            "always surface these if even tangentially relevant.\n"
            "3. Ignore noise that is clearly irrelevant to the query.\n"
            "4. If no memories are relevant, respond with 'No relevant context found.'\n"
            "5. Respond only with the synthesized summary."
        )

        user_prompt = f"User Query: {query}\n\nMemory Tiers:\n{facts_block}"

        try:
            response = ollama.chat(
                model=LOCAL_LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_instr},
                    {"role": "user", "content": user_prompt}
                ]
            )
            summary = response['message']['content'].strip()
        except Exception as e:
            logger.error(f"Librarian Error: {e}")
            summary = "Error: Local memory librarian was unable to process results."

        # 4. Return as a single summarized MemoryEntry
        summarized_entry = MemoryEntry(
            author="librarian",
            content=types.Content(
                parts=[types.Part(text=summary)],
                role="user"
            ),
            custom_metadata={"type": "summary", "source": "qwen-librarian"}
        )

        return SearchMemoryResponse(memories=[summarized_entry])

    async def delete_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        memory_ids: Sequence[str],
    ) -> None:
        """Deletes specific memories from ChromaDB by ID."""
        if not memory_ids:
            return
        
        # Verify ownership before deleting
        results = self._collection.get(ids=list(memory_ids))
        valid_ids = []
        for i, meta in enumerate(results["metadatas"]):
            if meta.get("user_id") == user_id:
                valid_ids.append(results["ids"][i])
        
        if valid_ids:
            self._collection.delete(ids=valid_ids)
            logger.info(f"Deleted {len(valid_ids)} memories for user {user_id}")

    def _extract_text(self, content: types.Content) -> str:
        if not content or not content.parts:
            return ""
        return "\n".join([p.text for p in content.parts if p.text])

    def list_all_for_reorg(self, user_id: str):
        return self._collection.get(
            where=self._user_filter(user_id),
            include=["documents", "metadatas"]
        )

    async def add_session_to_memory(self, session) -> None:
        """
        Required abstract method for ADK 1.26.0.
        Adds an entire session's events to the memory.
        """
        # For now, we rely on Amber's callback to add facts individually.
        # We can implement full session archival here later if needed.
        pass
