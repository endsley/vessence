"""
essence_runtime.py — Multi-essence runtime for Amber.

Manages loading/unloading essences, orchestration (Mode A & Mode C),
capability routing, and memory porting on deletion.
"""

import json
import os
import shutil
import time
import logging
from dataclasses import dataclass, field
from typing import Any

import chromadb

from jane.config import (
    get_chroma_client,
    TOOLS_DIR,
    ESSENCES_DIR,
    VESSENCE_DATA_HOME,
    VECTOR_DB_USER_MEMORIES,
    CHROMA_COLLECTION_USER_MEMORIES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EssenceState — per-loaded-essence bookkeeping
# ---------------------------------------------------------------------------

@dataclass
class EssenceState:
    """Runtime state for a single loaded essence."""
    name: str
    manifest: dict = field(default_factory=dict)
    personality: str = ""
    capabilities_provides: list[str] = field(default_factory=list)
    capabilities_consumes: list[str] = field(default_factory=list)
    chromadb_client: Any = None       # chromadb.PersistentClient for this essence
    essence_dir: str = ""


# ---------------------------------------------------------------------------
# EssenceRuntime — singleton managing all loaded essences
# ---------------------------------------------------------------------------

class EssenceRuntime:
    """Loads, unloads, and manages essences for Amber."""

    _instance: "EssenceRuntime | None" = None

    def __new__(cls, essences_dir: str | None = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, essences_dir: str | None = None):
        if self._initialized:
            return
        self._essences_dir = essences_dir or TOOLS_DIR
        self._loaded: dict[str, EssenceState] = {}
        data_dir = os.path.join(VESSENCE_DATA_HOME, "data")
        os.makedirs(data_dir, exist_ok=True)
        self._active_essence_file = os.path.join(data_dir, "active_essence.json")
        self._initialized = True

    # ── Loading / unloading ───────────────────────────────────────────────

    def load_essence(self, essence_name: str) -> EssenceState:
        """Load an essence from disk into the runtime."""
        if essence_name in self._loaded:
            logger.info("Essence '%s' already loaded", essence_name)
            return self._loaded[essence_name]

        essence_dir = os.path.join(self._essences_dir, essence_name)
        manifest_path = os.path.join(essence_dir, "manifest.json")
        personality_path = os.path.join(essence_dir, "personality.md")

        if not os.path.isfile(manifest_path):
            raise FileNotFoundError(
                f"No manifest.json found for essence '{essence_name}' at {manifest_path}"
            )

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        personality = ""
        if os.path.isfile(personality_path):
            with open(personality_path, "r", encoding="utf-8") as f:
                personality = f.read()

        caps = manifest.get("capabilities", {})
        provides = caps.get("provides", [])
        consumes = caps.get("consumes", [])

        # Open a per-essence ChromaDB (knowledge/chromadb inside the essence folder)
        chroma_path = os.path.join(essence_dir, "knowledge", "chromadb")
        os.makedirs(chroma_path, exist_ok=True)
        chroma_client = get_chroma_client(path=chroma_path)

        state = EssenceState(
            name=essence_name,
            manifest=manifest,
            personality=personality,
            capabilities_provides=provides,
            capabilities_consumes=consumes,
            chromadb_client=chroma_client,
            essence_dir=essence_dir,
        )
        self._loaded[essence_name] = state
        logger.info("Loaded essence '%s' with capabilities: %s", essence_name, provides)
        return state

    def unload_essence(self, essence_name: str) -> None:
        """Deactivate an essence without deleting its data."""
        if essence_name not in self._loaded:
            logger.warning("Essence '%s' is not loaded", essence_name)
            return
        del self._loaded[essence_name]
        # If this was the active essence, clear that too
        if self.get_active_essence() == essence_name:
            self.set_active_essence(None)
        logger.info("Unloaded essence '%s'", essence_name)

    def delete_essence(self, essence_name: str, port_memory: bool = False) -> None:
        """Delete an essence permanently. Optionally port its memory first."""
        essence_dir = os.path.join(self._essences_dir, essence_name)
        if not os.path.isdir(essence_dir):
            raise FileNotFoundError(f"Essence folder not found: {essence_dir}")

        if port_memory:
            self._port_memory(essence_name, essence_dir)

        # Unload if currently loaded
        if essence_name in self._loaded:
            self.unload_essence(essence_name)

        shutil.rmtree(essence_dir)
        logger.info("Deleted essence folder '%s'", essence_dir)

    # ── Queries ──────────────────────────────────────────────────────────

    def get_loaded(self) -> dict[str, EssenceState]:
        """Return all currently loaded essences."""
        return dict(self._loaded)

    def list_available(self) -> list[dict]:
        """Scan the essences directory and return metadata for each."""
        available: list[dict] = []
        if not os.path.isdir(self._essences_dir):
            return available

        for entry in sorted(os.listdir(self._essences_dir)):
            manifest_path = os.path.join(self._essences_dir, entry, "manifest.json")
            if not os.path.isfile(manifest_path):
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                available.append({
                    "name": entry,
                    "essence_name": manifest.get("essence_name", entry),
                    "role_title": manifest.get("role_title", ""),
                    "description": manifest.get("description", ""),
                    "version": manifest.get("version", ""),
                    "loaded": entry in self._loaded,
                })
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Skipping '%s': %s", entry, exc)
        return available

    def get_capabilities_map(self) -> dict[str, list[str]]:
        """Build capability -> [essence_names] map from loaded essences."""
        cap_map: dict[str, list[str]] = {}
        for name, state in self._loaded.items():
            for cap in state.capabilities_provides:
                cap_map.setdefault(cap, []).append(name)
        return cap_map

    def route_to_essence(self, query: str) -> str | None:
        """Return the best essence name for a query based on capabilities.

        Simple keyword matching against capability names and manifest
        descriptions. Returns None if no match is found.
        """
        query_lower = query.lower()
        best_name: str | None = None
        best_score = 0

        for name, state in self._loaded.items():
            score = 0
            # Score based on capability keyword overlap
            for cap in state.capabilities_provides:
                for word in cap.lower().replace("_", " ").split():
                    if word in query_lower:
                        score += 2
            # Score based on role_title / description
            role = state.manifest.get("role_title", "").lower()
            desc = state.manifest.get("description", "").lower()
            for word in query_lower.split():
                if len(word) > 2:
                    if word in role:
                        score += 3
                    if word in desc:
                        score += 1
            if score > best_score:
                best_score = score
                best_name = name

        return best_name

    # ── Active essence persistence ───────────────────────────────────────

    def set_active_essence(self, essence_name: str | None) -> None:
        """Write the currently-active essence name to disk."""
        payload = {"active_essence": essence_name, "updated_at": time.time()}
        with open(self._active_essence_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def get_active_essence(self) -> str | None:
        """Read the currently-active essence name from disk."""
        if not os.path.isfile(self._active_essence_file):
            return None
        try:
            with open(self._active_essence_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("active_essence")
        except (json.JSONDecodeError, OSError):
            return None

    # ── Memory porting (private) ─────────────────────────────────────────

    def _port_memory(self, essence_name: str, essence_dir: str) -> None:
        """Copy all ChromaDB entries from an essence into user_memories."""
        chroma_path = os.path.join(essence_dir, "knowledge", "chromadb")
        if not os.path.isdir(chroma_path):
            logger.info("No ChromaDB to port for '%s'", essence_name)
            return

        src_client = get_chroma_client(path=chroma_path)
        dst_client = get_chroma_client(path=VECTOR_DB_USER_MEMORIES)
        dst_collection = dst_client.get_or_create_collection(
            name=CHROMA_COLLECTION_USER_MEMORIES
        )

        ported_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        total_ported = 0

        for col_info in src_client.list_collections():
            col_name = col_info if isinstance(col_info, str) else col_info.name
            src_col = src_client.get_collection(name=col_name)
            results = src_col.get(include=["documents", "metadatas", "embeddings"])
            if not results["ids"]:
                continue

            # Re-key IDs to avoid collisions and tag with source metadata
            new_ids: list[str] = []
            new_metadatas: list[dict] = []
            for i, original_id in enumerate(results["ids"]):
                new_ids.append(f"ported_{essence_name}_{col_name}_{original_id}")
                meta = dict(results["metadatas"][i]) if results["metadatas"] and results["metadatas"][i] else {}
                meta["source"] = f"essence:{essence_name}"
                meta["ported_at"] = ported_at
                meta["original_collection"] = col_name
                new_metadatas.append(meta)

            add_kwargs: dict[str, Any] = {
                "ids": new_ids,
                "documents": results["documents"],
                "metadatas": new_metadatas,
            }
            if results.get("embeddings") is not None:
                add_kwargs["embeddings"] = results["embeddings"]

            dst_collection.add(**add_kwargs)
            total_ported += len(new_ids)

        logger.info(
            "Ported %d entries from essence '%s' into %s",
            total_ported, essence_name, CHROMA_COLLECTION_USER_MEMORIES,
        )


# ---------------------------------------------------------------------------
# JaneOrchestrator — Mode A: Jane as Project Manager (top-down)
# ---------------------------------------------------------------------------

class JaneOrchestrator:
    """Decomposes tasks and delegates subtasks to the right essences."""

    def __init__(self, runtime: EssenceRuntime):
        self.runtime = runtime

    def decompose_task(self, user_request: str) -> list[dict]:
        """Break a user request into subtasks mapped to loaded essences.

        Returns a list of dicts:
            [{"subtask": str, "target_essence": str, "capability_needed": str}, ...]
        """
        caps_map = self.runtime.get_capabilities_map()
        request_lower = user_request.lower()
        plan: list[dict] = []

        # Match each capability that has keyword overlap with the request
        for capability, providers in caps_map.items():
            cap_words = set(capability.lower().replace("_", " ").split())
            request_words = set(request_lower.split())
            overlap = cap_words & request_words
            if overlap:
                plan.append({
                    "subtask": f"Handle '{capability}' aspect of the request",
                    "target_essence": providers[0],  # pick first provider
                    "capability_needed": capability,
                })

        # If nothing matched, try routing the whole request
        if not plan:
            best = self.runtime.route_to_essence(user_request)
            if best:
                plan.append({
                    "subtask": user_request,
                    "target_essence": best,
                    "capability_needed": "general",
                })

        return plan

    def execute_plan(self, plan: list[dict]) -> dict:
        """Send each subtask to its target essence and collect results.

        This is a framework stub — actual LLM invocation depends on the
        Amber runtime loop. Returns a summary dict.
        """
        results: list[dict] = []
        for step in plan:
            essence_name = step["target_essence"]
            loaded = self.runtime.get_loaded()
            if essence_name not in loaded:
                results.append({
                    "subtask": step["subtask"],
                    "essence": essence_name,
                    "status": "error",
                    "detail": f"Essence '{essence_name}' is not loaded",
                })
                continue

            # Placeholder: in production the Amber runtime would invoke the
            # essence's LLM with the subtask and the essence's personality +
            # memory context.  Here we record the dispatch.
            results.append({
                "subtask": step["subtask"],
                "essence": essence_name,
                "capability": step["capability_needed"],
                "status": "dispatched",
                "detail": "Subtask queued for essence execution",
            })

        return {
            "plan_size": len(plan),
            "results": results,
            "completed": all(r["status"] == "dispatched" for r in results),
        }


# ---------------------------------------------------------------------------
# CapabilityRegistry — Mode C: peer-to-peer collaboration
# ---------------------------------------------------------------------------

class CapabilityRegistry:
    """Tracks which essences provide which capabilities and routes
    service requests between them."""

    def __init__(self):
        self._providers: dict[str, list[str]] = {}  # capability -> [essence_names]

    def register(self, essence_name: str, capabilities: list[str]) -> None:
        """Register an essence as a provider of the given capabilities."""
        for cap in capabilities:
            self._providers.setdefault(cap, [])
            if essence_name not in self._providers[cap]:
                self._providers[cap].append(essence_name)

    def unregister(self, essence_name: str) -> None:
        """Remove an essence from all capability registrations."""
        for cap in list(self._providers):
            if essence_name in self._providers[cap]:
                self._providers[cap].remove(essence_name)
            if not self._providers[cap]:
                del self._providers[cap]

    def find_provider(self, capability: str) -> str | None:
        """Return the first registered provider for a capability, or None."""
        providers = self._providers.get(capability, [])
        return providers[0] if providers else None

    def request_service(
        self,
        requesting_essence: str,
        capability: str,
        payload: dict,
    ) -> dict:
        """Route a service request to the best provider.

        Returns a result dict. In production the Amber runtime would
        actually invoke the provider essence; here we return dispatch info.
        """
        provider = self.find_provider(capability)
        if provider is None:
            return {
                "status": "error",
                "detail": f"No provider registered for capability '{capability}'",
            }
        if provider == requesting_essence:
            return {
                "status": "error",
                "detail": "Cannot request a service from self",
            }
        return {
            "status": "dispatched",
            "provider": provider,
            "requester": requesting_essence,
            "capability": capability,
            "payload": payload,
            "detail": f"Request forwarded to '{provider}'",
        }
