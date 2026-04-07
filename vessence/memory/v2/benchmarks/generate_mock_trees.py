"""Generate mock tree indexes at varying scales for benchmarking.

Creates tree indexes in two formats (compact path, flat list) at
50, 100, 200, and 300 leaf counts. Each leaf has a realistic path
and one-line description.
"""

import json
import os
import random

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Realistic top-level branches
BRANCHES = {
    "user_info": {
        "personal": [
            ("background", "age, location, family details"),
            ("preferences", "communication style, work habits"),
            ("health", "medical info, fitness goals"),
            ("hobbies", "interests, activities, sports"),
            ("daily_routine", "schedule patterns, sleep habits"),
        ],
        "work": [
            ("role", "current job title, responsibilities"),
            ("colleagues", "coworkers, team members"),
            ("projects", "active work projects and status"),
            ("skills", "technical and professional skills"),
            ("meetings", "recurring meetings, schedules"),
        ],
        "relationships": [
            ("family", "family members, relationships"),
            ("friends", "close friends, social circle"),
            ("contacts", "professional contacts, networking"),
        ],
        "finances": [
            ("accounts", "bank accounts, investments"),
            ("budget", "spending patterns, goals"),
            ("subscriptions", "recurring payments, services"),
        ],
    },
    "vessence": {
        "architecture": [
            ("web_server", "jane-web service, endpoints, config"),
            ("llm_brain", "standing brain, provider routing"),
            ("memory_system", "ChromaDB, vector search, retrieval"),
            ("tool_loader", "dynamic tool discovery, hooks"),
            ("android_app", "mobile client, APK build process"),
        ],
        "features": [
            ("essences", "essence builder, runtime, loader"),
            ("voice", "TTS, wake word, speech recognition"),
            ("browser", "playwright, omniparser, web skills"),
            ("notifications", "push, discord, email alerts"),
            ("scheduling", "cron jobs, job queue, auto-continue"),
        ],
        "deployment": [
            ("docker", "container setup, docker bundle"),
            ("marketing_site", "landing page, download links"),
            ("updates", "version bumping, release process"),
        ],
        "config": [
            ("environment", "env vars, paths, API keys"),
            ("models", "LLM model selection, tiers"),
            ("permissions", "auth, session management"),
        ],
    },
    "conversations": {
        "topics": [
            ("recent_discussions", "latest conversation themes"),
            ("decisions_made", "architectural and design choices"),
            ("pending_questions", "unresolved topics, open items"),
        ],
        "patterns": [
            ("common_requests", "frequently asked task types"),
            ("workflow_prefs", "how user prefers to work"),
        ],
    },
    "external": {
        "services": [
            ("apis", "third-party APIs, integrations"),
            ("tools", "dev tools, CLI utilities"),
            ("platforms", "cloud services, hosting"),
        ],
        "links": [
            ("documentation", "reference docs, guides"),
            ("repos", "GitHub repos, codebases"),
            ("dashboards", "monitoring, analytics URLs"),
        ],
    },
    "knowledge": {
        "technical": [
            ("python", "Python patterns, libraries, tips"),
            ("javascript", "JS/TS frontend knowledge"),
            ("devops", "CI/CD, deployment, infrastructure"),
            ("databases", "SQL, NoSQL, vector DBs"),
            ("networking", "HTTP, APIs, protocols"),
        ],
        "domain": [
            ("ai_ml", "machine learning, LLM concepts"),
            ("security", "auth, encryption, best practices"),
            ("design", "UI/UX patterns, accessibility"),
        ],
    },
}


def _generate_extra_leaves(count: int) -> list[tuple[str, str, str]]:
    """Generate additional realistic leaves to reach target count."""
    extras = []
    adjectives = ["recent", "archived", "important", "draft", "reviewed",
                   "updated", "legacy", "new", "core", "experimental"]
    nouns = ["notes", "summary", "details", "overview", "reference",
             "guide", "log", "tracker", "config", "spec"]
    topics = ["meeting", "project", "feature", "bug", "review",
              "release", "migration", "refactor", "test", "deploy"]

    for i in range(count):
        branch = random.choice(list(BRANCHES.keys()))
        sub = random.choice(list(BRANCHES[branch].keys()))
        adj = random.choice(adjectives)
        noun = random.choice(nouns)
        topic = random.choice(topics)
        name = f"{adj}_{topic}_{noun}_{i}"
        desc = f"{adj} {topic} {noun} - auto-generated leaf {i}"
        extras.append((f"{branch}/{sub}/{name}", name, desc))
    return extras


def _collect_base_leaves() -> list[tuple[str, str, str]]:
    """Collect all base leaves from BRANCHES structure.
    Returns list of (full_path, filename, description)."""
    leaves = []
    for branch, subs in BRANCHES.items():
        for sub, items in subs.items():
            for filename, desc in items:
                path = f"{branch}/{sub}/{filename}"
                leaves.append((path, filename, desc))
    return leaves


def generate_tree_compact(leaves: list[tuple[str, str, str]]) -> str:
    """Generate compact path format tree index."""
    # Group by branch/sub
    tree = {}
    for path, filename, desc in leaves:
        parts = path.split("/")
        if len(parts) == 3:
            branch, sub, _ = parts
        else:
            branch = parts[0]
            sub = parts[1] if len(parts) > 1 else "misc"

        tree.setdefault(branch, {}).setdefault(sub, []).append(
            (filename, desc)
        )

    lines = []
    for branch in sorted(tree):
        lines.append(f"{branch}/")
        subs = tree[branch]
        for sub in sorted(subs):
            lines.append(f"  {sub}/")
            for filename, desc in sorted(subs[sub]):
                lines.append(f"    - {filename}.md -- {desc}")
    return "\n".join(lines)


def generate_tree_flat(leaves: list[tuple[str, str, str]]) -> str:
    """Generate flat numbered list format."""
    lines = []
    for i, (path, filename, desc) in enumerate(sorted(leaves), 1):
        lines.append(f"{i}. {path}.md -- {desc}")
    return "\n".join(lines)


def generate_mock_trees():
    """Generate mock trees at 50, 100, 200, 300 leaf scales."""
    base_leaves = _collect_base_leaves()
    print(f"Base leaves from template: {len(base_leaves)}")

    targets = [50, 100, 200, 300]

    manifest = {}

    for target in targets:
        if target <= len(base_leaves):
            leaves = random.sample(base_leaves, target)
        else:
            extra_needed = target - len(base_leaves)
            extras = _generate_extra_leaves(extra_needed)
            leaves = base_leaves + extras

        # Compact format
        compact = generate_tree_compact(leaves)
        compact_file = f"tree_index_compact_{target}.txt"
        compact_path = os.path.join(OUTPUT_DIR, compact_file)
        with open(compact_path, "w") as f:
            f.write(compact)

        # Flat format
        flat = generate_tree_flat(leaves)
        flat_file = f"tree_index_flat_{target}.txt"
        flat_path = os.path.join(OUTPUT_DIR, flat_file)
        with open(flat_path, "w") as f:
            f.write(flat)

        manifest[target] = {
            "compact": {
                "file": compact_file,
                "chars": len(compact),
                "lines": compact.count("\n") + 1,
            },
            "flat": {
                "file": flat_file,
                "chars": len(flat),
                "lines": flat.count("\n") + 1,
            },
            "leaf_count": len(leaves),
        }

        print(f"\n--- {target} leaves ---")
        print(f"  Compact: {len(compact)} chars, {compact.count(chr(10))+1} lines")
        print(f"  Flat:    {len(flat)} chars, {flat.count(chr(10))+1} lines")

    # Save manifest
    manifest_path = os.path.join(OUTPUT_DIR, "mock_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest saved to {manifest_path}")


if __name__ == "__main__":
    random.seed(42)  # Reproducible
    generate_mock_trees()
