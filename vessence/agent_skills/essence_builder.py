"""
Essence Builder Interview System

Guides users through a structured interview to build a complete Vessence essence.
Jane uses this to force spec-first, code-second essence creation.

Usage:
    from agent_skills.essence_builder import (
        start_interview, process_answer, get_progress,
        generate_spec_document, generate_manifest,
        generate_personality_md, build_essence_from_spec,
        save_state, load_state
    )
"""

import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

VESSENCE_DATA_HOME = os.environ.get(
    "VESSENCE_DATA_HOME",
    os.path.join(os.path.expanduser("~"), "ambient", "vessence-data"),
)
STATE_PATH = os.path.join(VESSENCE_DATA_HOME, "data", "essence_interview_state.json")

TEMPLATE_DIR = os.path.join(
    os.path.expanduser("~"),
    "ambient", "vessence", "configs", "templates", "essence_template",
)

# ---------------------------------------------------------------------------
# Section definitions
# ---------------------------------------------------------------------------

SECTION_NAMES = [
    "identity_personality",
    "knowledge_base",
    "custom_functions",
    "shared_skills",
    "ui_paradigm",
    "interaction_patterns",
    "triggers_automations",
    "capabilities_declaration",
    "preferred_model",
    "permissions_credentials",
    "user_data_layer",
    "review_approve",
]

INTERVIEW_QUESTIONS: dict[int, dict] = {
    0: {
        "section_name": "identity_personality",
        "required_questions": [
            "What role should Amber take on? Give me a role title (e.g. 'the accountant', 'the tutor').",
            "What is the essence's name? (e.g. 'Tax Accountant 2025', 'Fitness Coach')",
            "Describe the communication style. Should Amber be formal or casual? Verbose or concise? What tone?",
            "What domain expertise should Amber have in this role?",
        ],
        "optional_questions": [
            "Any specific behavioral rules or boundaries for this role?",
            "Should Amber reference a particular background or persona backstory?",
        ],
        "summary_template": (
            "**Identity & Personality**\n"
            "- Role title: {role_title}\n"
            "- Essence name: {essence_name}\n"
            "- Style: {communication_style}\n"
            "- Expertise: {domain_expertise}\n"
        ),
    },
    1: {
        "section_name": "knowledge_base",
        "required_questions": [
            "What should this essence know on day one? Describe the domain knowledge to pre-fill.",
            "Are there specific sources, documents, or datasets to include?",
        ],
        "optional_questions": [
            "Should the knowledge base be structured (categories/topics) or flat?",
            "Any facts or reference data that must be baked in from the start?",
        ],
        "summary_template": (
            "**Knowledge Base**\n"
            "- Day-one knowledge: {day_one_knowledge}\n"
            "- Sources: {sources}\n"
        ),
    },
    2: {
        "section_name": "custom_functions",
        "required_questions": [
            "What can this essence DO that the Vessence platform doesn't already provide? List any custom tools or functions.",
            "For each custom function, describe its inputs and expected outputs.",
        ],
        "optional_questions": [
            "Do any of these functions require external libraries or services?",
            "Should any functions run on a schedule or only on demand?",
        ],
        "summary_template": (
            "**Custom Functions**\n"
            "- Tools: {tools_list}\n"
        ),
    },
    3: {
        "section_name": "shared_skills",
        "required_questions": [
            "Which Vessence platform skills does this essence need? Options: memory_read_write, file_handling, tts, web_search, screen_control, microphone, clipboard.",
        ],
        "optional_questions": [
            "Any platform skills you're unsure about? I can explain what each one provides.",
        ],
        "summary_template": (
            "**Shared Skills**\n"
            "- Selected: {selected_skills}\n"
        ),
    },
    4: {
        "section_name": "ui_paradigm",
        "required_questions": [
            "What UI type fits best? Options: chat, card_grid, form_wizard, dashboard, hybrid.",
            "Describe the layout — what components should be visible and where?",
        ],
        "optional_questions": [
            "Any specific data bindings between UI components and essence functions?",
            "Does the essence need custom icons or visual assets?",
        ],
        "summary_template": (
            "**UI Paradigm**\n"
            "- Type: {ui_type}\n"
            "- Layout: {layout_description}\n"
        ),
    },
    5: {
        "section_name": "interaction_patterns",
        "required_questions": [
            "What conversation starters should greet the user? List 2-4 example prompts.",
            "Are there any multi-step workflows or guided sequences the essence should offer?",
        ],
        "optional_questions": [
            "Should the essence have an onboarding flow for first-time users?",
        ],
        "summary_template": (
            "**Interaction Patterns**\n"
            "- Starters: {conversation_starters}\n"
            "- Workflows: {workflows}\n"
        ),
    },
    6: {
        "section_name": "triggers_automations",
        "required_questions": [
            "What should this essence do proactively? Describe any triggers (date-based, event-based, condition-based).",
        ],
        "optional_questions": [
            "Should triggers produce notifications, messages, or automated actions?",
            "Any recurring schedules (daily, weekly, monthly)?",
        ],
        "summary_template": (
            "**Triggers & Automations**\n"
            "- Triggers: {triggers}\n"
        ),
    },
    7: {
        "section_name": "capabilities_declaration",
        "required_questions": [
            "What capabilities does this essence PROVIDE to other essences? (e.g. 'tax_preparation', 'document_analysis')",
            "What capabilities does this essence CONSUME from other essences? (e.g. 'document_retrieval', 'file_storage')",
        ],
        "optional_questions": [
            "Should this essence be able to work with other essences in Mode A (Jane-orchestrated) or Mode C (peer-to-peer)?",
        ],
        "summary_template": (
            "**Capabilities**\n"
            "- Provides: {provides}\n"
            "- Consumes: {consumes}\n"
        ),
    },
    8: {
        "section_name": "preferred_model",
        "required_questions": [
            "Which LLM model should this essence use? (e.g. claude-sonnet-4-6, gpt-4o, gemini-flash, a local model via Ollama)",
            "Why is this model the best fit? (reasoning, cost, speed, capability)",
        ],
        "optional_questions": [
            "Should users be able to override the model choice easily?",
        ],
        "summary_template": (
            "**Preferred Model**\n"
            "- Model: {model_id}\n"
            "- Reasoning: {model_reasoning}\n"
        ),
    },
    9: {
        "section_name": "permissions_credentials",
        "required_questions": [
            "What permissions does this essence need? Options: internet, file_system, clipboard, microphone, camera, screen_control.",
            "Does the essence require any external API keys or credentials? For each, is it required or optional?",
        ],
        "optional_questions": [
            "Any sensitive data handling considerations?",
        ],
        "summary_template": (
            "**Permissions & Credentials**\n"
            "- Permissions: {permissions}\n"
            "- Credentials: {credentials}\n"
        ),
    },
    10: {
        "section_name": "user_data_layer",
        "required_questions": [
            "What user-specific data will this essence accumulate over time?",
            "How should this data be organized and stored within the essence folder?",
        ],
        "optional_questions": [
            "If the user deletes this essence, what data should be offered for porting to Jane's universal memory?",
        ],
        "summary_template": (
            "**User Data Layer**\n"
            "- Accumulated data: {accumulated_data}\n"
            "- Organization: {data_organization}\n"
        ),
    },
    11: {
        "section_name": "review_approve",
        "required_questions": [
            "Please review the complete spec above. Type 'approve' to proceed with building, or describe what needs to change.",
        ],
        "optional_questions": [],
        "summary_template": (
            "**Review & Approval**\n"
            "- Status: {approval_status}\n"
        ),
    },
}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class EssenceInterviewState:
    """Tracks progress through the essence builder interview."""

    current_section: int = 0
    completed_sections: set[int] = field(default_factory=set)
    answers: dict[str, str] = field(default_factory=dict)
    spec_approved: bool = False
    essence_name: str = ""

    # -- serialization helpers -----------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d["completed_sections"] = sorted(d["completed_sections"])
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "EssenceInterviewState":
        d = dict(d)  # shallow copy
        d["completed_sections"] = set(d.get("completed_sections", []))
        return cls(**d)


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def save_state(state: EssenceInterviewState) -> None:
    """Persist interview state to disk so it survives session restarts."""
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state.to_dict(), f, indent=2)


def load_state() -> Optional[EssenceInterviewState]:
    """Load a previously saved interview state, or None if none exists."""
    if not os.path.exists(STATE_PATH):
        return None
    with open(STATE_PATH, "r") as f:
        return EssenceInterviewState.from_dict(json.load(f))


def clear_state() -> None:
    """Remove saved interview state."""
    if os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)


# ---------------------------------------------------------------------------
# Interview helpers
# ---------------------------------------------------------------------------


def _section_display_name(index: int) -> str:
    """Human-readable name for a section index."""
    names = [
        "Identity & Personality",
        "Knowledge Base",
        "Custom Functions",
        "Shared Skills",
        "UI Paradigm",
        "Interaction Patterns",
        "Triggers & Automations",
        "Capabilities Declaration",
        "Preferred Model",
        "Permissions & Credentials",
        "User Data Layer",
        "Review & Approve",
    ]
    return names[index] if 0 <= index < len(names) else f"Section {index}"


def _format_questions(section_index: int, include_optional: bool = False) -> str:
    """Format the questions for a section into a numbered list."""
    q = INTERVIEW_QUESTIONS[section_index]
    lines = []
    for i, question in enumerate(q["required_questions"], 1):
        lines.append(f"{i}. {question}")
    if include_optional and q["optional_questions"]:
        lines.append("\nOptional — answer these if relevant:")
        for i, question in enumerate(q["optional_questions"], len(q["required_questions"]) + 1):
            lines.append(f"{i}. {question}")
    return "\n".join(lines)


def _section_intro(section_index: int) -> str:
    """Opening message for a section."""
    name = _section_display_name(section_index)
    total = len(SECTION_NAMES)
    return (
        f"--- **Section {section_index + 1}/{total}: {name}** ---\n\n"
        f"{_format_questions(section_index, include_optional=True)}"
    )


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def start_interview() -> tuple[EssenceInterviewState, str]:
    """
    Begin a new essence builder interview.

    Returns the initial state and an opening message with the first question.
    """
    state = EssenceInterviewState()
    opening = (
        "Welcome to the **Vessence Essence Builder**.\n\n"
        "I'll walk you through 12 sections that define everything about your new essence. "
        "Every section matters — we do spec-first, code-second. No skipping.\n\n"
        "You can answer all questions for a section in one message, or we can go "
        "back and forth. When you've covered everything, I'll summarize and move on.\n\n"
        f"{_section_intro(0)}"
    )
    save_state(state)
    return state, opening


def process_answer(
    state: EssenceInterviewState, user_answer: str
) -> tuple[EssenceInterviewState, str]:
    """
    Record the user's answer for the current section and advance.

    Returns the updated state and the next message (summary + next section
    intro, or full spec for review if all content sections are done).
    """
    section_index = state.current_section
    section_name = SECTION_NAMES[section_index]

    # Handle the review/approve section specially
    if section_index == 11:
        approved = user_answer.strip().lower() in ("approve", "approved", "yes", "lgtm")
        if approved:
            state.spec_approved = True
            state.completed_sections.add(section_index)
            state.answers[section_name] = "Approved"
            save_state(state)
            return state, (
                "Spec **approved**. The essence is ready to build.\n\n"
                "Call `build_essence_from_spec()` to generate the essence folder."
            )
        else:
            # User wants changes — record feedback but stay on review
            state.answers[section_name] = user_answer
            save_state(state)
            return state, (
                "Got it — I'll incorporate your feedback. "
                "Please describe all changes needed, then I'll regenerate the spec for re-review."
            )

    # Record the answer
    state.answers[section_name] = user_answer

    # Capture essence name from the identity section
    if section_index == 0:
        state.essence_name = _extract_essence_name(user_answer)

    state.completed_sections.add(section_index)

    # Build the section summary
    summary = f"**{_section_display_name(section_index)}** — recorded.\n\n"

    # Advance to next section
    next_section = section_index + 1
    state.current_section = next_section

    if next_section == 11:
        # All content sections done — show full spec for review
        spec = generate_spec_document(state)
        reply = (
            f"{summary}"
            "All sections complete. Here is your full essence spec:\n\n"
            "---\n\n"
            f"{spec}\n\n"
            "---\n\n"
            f"{_section_intro(11)}"
        )
    else:
        reply = f"{summary}{_section_intro(next_section)}"

    save_state(state)
    return state, reply


def _extract_essence_name(answer: str) -> str:
    """Best-effort extraction of the essence name from the identity answer."""
    # Look for a quoted name or the first capitalized phrase
    for line in answer.split("\n"):
        lower = line.lower()
        if "name" in lower or "called" in lower or "essence" in lower:
            # Try to grab a quoted string
            for quote in ('"', "'"):
                if quote in line:
                    parts = line.split(quote)
                    if len(parts) >= 3:
                        return parts[1].strip()
            # Fallback: use the part after the colon
            if ":" in line:
                return line.split(":", 1)[1].strip()
    # Final fallback: first 60 chars
    return answer[:60].strip()


def get_progress(state: EssenceInterviewState) -> str:
    """
    Human-readable progress summary.

    Example: "Sections completed: 3/12 — Identity ✓, Knowledge ✓, Functions ✓, next: Shared Skills"
    """
    total = len(SECTION_NAMES)
    done = len(state.completed_sections)
    parts = []
    for i in range(total):
        name = _section_display_name(i)
        if i in state.completed_sections:
            parts.append(f"{name} done")
    next_name = _section_display_name(state.current_section) if state.current_section < total else "None"
    done_str = ", ".join(parts) if parts else "None yet"
    return f"Sections completed: {done}/{total} — {done_str}, next: {next_name}"


# ---------------------------------------------------------------------------
# Spec generation
# ---------------------------------------------------------------------------


def generate_spec_document(state: EssenceInterviewState) -> str:
    """Compile all interview answers into a human-readable markdown spec."""
    lines = [
        f"# Essence Spec: {state.essence_name}",
        "",
    ]
    for i, section_name in enumerate(SECTION_NAMES):
        if section_name == "review_approve":
            continue
        display = _section_display_name(i)
        answer = state.answers.get(section_name, "_Not yet answered._")
        lines.append(f"## {i + 1}. {display}")
        lines.append("")
        lines.append(answer)
        lines.append("")
    return "\n".join(lines)


def generate_manifest(state: EssenceInterviewState) -> dict:
    """
    Compile answers into a valid manifest.json dict.

    Extracts structured data from free-text answers where possible,
    falling back to sensible defaults.
    """
    answers = state.answers

    # Parse shared skills
    skills_answer = answers.get("shared_skills", "")
    known_skills = [
        "memory_read_write", "file_handling", "tts",
        "web_search", "screen_control", "microphone", "clipboard",
    ]
    selected_skills = [s for s in known_skills if s in skills_answer.lower().replace(" ", "_")]

    # Parse UI type
    ui_answer = answers.get("ui_paradigm", "").lower()
    ui_type = "chat"
    for candidate in ("hybrid", "dashboard", "form_wizard", "card_grid", "chat"):
        if candidate.replace("_", " ") in ui_answer or candidate in ui_answer:
            ui_type = candidate
            break

    # Parse permissions
    perms_answer = answers.get("permissions_credentials", "").lower()
    known_perms = ["internet", "file_system", "clipboard", "microphone", "camera", "screen_control"]
    permissions = [p for p in known_perms if p.replace("_", " ") in perms_answer or p in perms_answer]

    # Parse capabilities
    caps_answer = answers.get("capabilities_declaration", "")
    provides = _extract_list_from_answer(caps_answer, "provide")
    consumes = _extract_list_from_answer(caps_answer, "consume")

    # Parse model
    model_answer = answers.get("preferred_model", "")
    model_id = "claude-sonnet-4-6"  # sensible default
    model_reasoning = model_answer
    for known_model in [
        "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku",
        "gpt-4o", "gpt-4", "gemini-flash", "gemini-pro",
    ]:
        if known_model in model_answer.lower().replace(" ", "-"):
            model_id = known_model
            break

    # Parse conversation starters
    interaction_answer = answers.get("interaction_patterns", "")
    starters = _extract_quoted_strings(interaction_answer)

    # Parse triggers
    triggers_answer = answers.get("triggers_automations", "")
    trigger_list = []
    if triggers_answer.strip() and triggers_answer.strip().lower() not in ("none", "n/a", "no"):
        trigger_list.append({
            "condition": "custom",
            "description": triggers_answer.strip(),
        })

    # Parse credentials
    creds_answer = answers.get("permissions_credentials", "")
    credentials = []
    if "api" in creds_answer.lower() or "key" in creds_answer.lower() or "credential" in creds_answer.lower():
        credentials.append({
            "name": "CUSTOM_API_KEY",
            "description": creds_answer.strip(),
            "required": "required" in creds_answer.lower(),
        })

    # Identity fields
    identity_answer = answers.get("identity_personality", "")
    role_title = _extract_role_title(identity_answer)
    description = answers.get("knowledge_base", state.essence_name)

    manifest = {
        "essence_name": state.essence_name,
        "role_title": role_title,
        "version": "1.0",
        "author": "user",
        "description": description[:200] if len(description) > 200 else description,
        "preferred_model": {
            "model_id": model_id,
            "reasoning": model_reasoning[:300] if len(model_reasoning) > 300 else model_reasoning,
        },
        "permissions": permissions,
        "external_credentials": credentials,
        "capabilities": {
            "provides": provides,
            "consumes": consumes,
        },
        "ui": {
            "type": ui_type,
            "entry_layout": "ui/layout.json",
        },
        "shared_skills": selected_skills,
        "interaction_patterns": {
            "conversation_starters": starters,
            "proactive_triggers": trigger_list,
        },
    }
    return manifest


def generate_personality_md(state: EssenceInterviewState) -> str:
    """Generate personality.md content from the identity section answers."""
    identity = state.answers.get("identity_personality", "")
    role_title = _extract_role_title(identity)

    return (
        f"# {state.essence_name} — Personality Definition\n"
        f"\n"
        f"## Identity\n"
        f"\n"
        f"You are **Amber {role_title}** — a specialized AI persona within the Vessence platform.\n"
        f"\n"
        f"{identity}\n"
        f"\n"
        f"## Communication Style\n"
        f"\n"
        f"Defined during the essence spec interview:\n"
        f"{_extract_section_fragment(identity, 'style')}\n"
        f"\n"
        f"## Domain Expertise\n"
        f"\n"
        f"Defined during the essence spec interview:\n"
        f"{_extract_section_fragment(identity, 'expert')}\n"
        f"\n"
        f"## Behavioral Rules\n"
        f"\n"
        f"Defined during the essence spec interview:\n"
        f"{_extract_section_fragment(identity, 'rule')}\n"
    )


# ---------------------------------------------------------------------------
# Build essence from spec
# ---------------------------------------------------------------------------


def build_essence_from_spec(
    state: EssenceInterviewState,
    essences_dir: str,
) -> str:
    """
    Create the full essence folder structure from the completed interview.

    Uses the template at configs/templates/essence_template/ if it exists,
    otherwise creates everything from scratch.

    Args:
        state: Completed and approved EssenceInterviewState.
        essences_dir: Parent directory where the essence folder will be created.

    Returns:
        Absolute path to the created essence folder.
    """
    if not state.spec_approved:
        raise ValueError("Spec must be approved before building. Complete the review section first.")

    # Sanitize folder name
    folder_name = (
        state.essence_name
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )
    # Remove non-alphanumeric chars except underscores
    folder_name = "".join(c for c in folder_name if c.isalnum() or c == "_")
    if not folder_name:
        folder_name = "new_essence"

    essence_path = os.path.join(essences_dir, folder_name)

    # Copy from template if available, otherwise create from scratch
    if os.path.isdir(TEMPLATE_DIR):
        shutil.copytree(TEMPLATE_DIR, essence_path, dirs_exist_ok=True)
    else:
        _create_folder_structure(essence_path)

    # Write manifest.json
    manifest = generate_manifest(state)
    with open(os.path.join(essence_path, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    # Write personality.md
    personality = generate_personality_md(state)
    with open(os.path.join(essence_path, "personality.md"), "w") as f:
        f.write(personality)

    # Write spec document for reference
    spec_doc = generate_spec_document(state)
    with open(os.path.join(essence_path, "SPEC.md"), "w") as f:
        f.write(spec_doc)

    # Write custom functions stub if custom functions were described
    custom_funcs = state.answers.get("custom_functions", "")
    if custom_funcs.strip() and custom_funcs.strip().lower() not in ("none", "n/a", "no"):
        funcs_path = os.path.join(essence_path, "functions", "custom_tools.py")
        os.makedirs(os.path.dirname(funcs_path), exist_ok=True)
        with open(funcs_path, "w") as f:
            f.write(
                f'"""\nCustom tools for {state.essence_name}\n\n'
                f"Based on spec:\n{custom_funcs}\n\n"
                f'TODO: Implement the functions described above.\n"""\n'
            )

    # Write UI layout stub
    ui_answer = state.answers.get("ui_paradigm", "")
    ui_type = generate_manifest(state)["ui"]["type"]
    layout_path = os.path.join(essence_path, "ui", "layout.json")
    os.makedirs(os.path.dirname(layout_path), exist_ok=True)
    layout = {
        "type": ui_type,
        "components": [
            {
                "id": "main",
                "type": f"{ui_type}_panel",
                "position": "main",
            }
        ],
        "notes": ui_answer[:500] if len(ui_answer) > 500 else ui_answer,
    }
    with open(layout_path, "w") as f:
        json.dump(layout, f, indent=2)

    # Write onboarding workflow stub
    interaction_answer = state.answers.get("interaction_patterns", "")
    starters = generate_manifest(state)["interaction_patterns"]["conversation_starters"]
    workflows_path = os.path.join(essence_path, "workflows", "onboarding.json")
    os.makedirs(os.path.dirname(workflows_path), exist_ok=True)
    onboarding = {
        "onboarding": {
            "conversation_starters": starters,
            "steps": [],
            "notes": interaction_answer[:500] if len(interaction_answer) > 500 else interaction_answer,
        }
    }
    with open(workflows_path, "w") as f:
        json.dump(onboarding, f, indent=2)

    # Ensure remaining directories exist
    for subdir in ("knowledge/chromadb", "working_files", "user_data", "ui/assets", "workflows/sequences"):
        os.makedirs(os.path.join(essence_path, subdir), exist_ok=True)

    # Clear interview state now that the build is complete
    clear_state()

    return os.path.abspath(essence_path)


def _create_folder_structure(essence_path: str) -> None:
    """Create the essence folder structure from scratch (no template)."""
    dirs = [
        "",
        "knowledge/chromadb",
        "functions",
        "ui/assets",
        "workflows/sequences",
        "working_files",
        "user_data",
    ]
    for d in dirs:
        os.makedirs(os.path.join(essence_path, d), exist_ok=True)

    # Create empty tool manifest
    with open(os.path.join(essence_path, "functions", "tool_manifest.json"), "w") as f:
        json.dump({"tools": []}, f, indent=2)


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _extract_role_title(text: str) -> str:
    """Try to extract a role title like 'the accountant' from free-text."""
    lower = text.lower()
    # Look for "the <role>" pattern
    for marker in ("role title:", "role:", "title:"):
        if marker in lower:
            idx = lower.index(marker) + len(marker)
            fragment = text[idx:].strip().split("\n")[0].strip().rstrip(".")
            if fragment:
                frag = fragment.strip("'\"")
                if not frag.lower().startswith("the "):
                    frag = f"the {frag}"
                return frag
    # Look for "the <word>" pattern
    import re
    match = re.search(r"\bthe\s+(\w+)", lower)
    if match:
        return f"the {match.group(1)}"
    return "the specialist"


def _extract_list_from_answer(text: str, keyword: str) -> list[str]:
    """Extract a comma-separated or bullet list of items near a keyword."""
    items = []
    for line in text.split("\n"):
        lower = line.lower()
        if keyword in lower:
            # Try comma-separated
            after = line.split(":", 1)[-1] if ":" in line else line
            parts = [p.strip().strip("-•*").strip() for p in after.split(",")]
            items.extend(p for p in parts if p and len(p) < 80)
    # Also grab bullet items
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("-", "*", "•")):
            item = stripped.lstrip("-*• ").strip()
            if item and len(item) < 80 and item not in items:
                items.append(item)
    return items if items else []


def _extract_quoted_strings(text: str) -> list[str]:
    """Extract strings enclosed in quotes, or bullet items."""
    import re
    # Quoted strings
    quoted = re.findall(r'["\']([^"\']{5,})["\']', text)
    if quoted:
        return quoted[:6]
    # Bullet items
    items = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("-", "*", "•", "1", "2", "3", "4")):
            item = stripped.lstrip("-*•0123456789. ").strip()
            if item and len(item) > 4:
                items.append(item)
    return items[:6] if items else []


def _extract_section_fragment(text: str, keyword: str) -> str:
    """Extract lines from text that relate to a keyword."""
    lines = []
    for line in text.split("\n"):
        if keyword in line.lower():
            lines.append(f"- {line.strip()}")
    if lines:
        return "\n".join(lines)
    return "- (To be refined based on interview answers)"


# ---------------------------------------------------------------------------
# CLI entry point (for testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        s = load_state()
        if s:
            print(get_progress(s))
        else:
            print("No active interview.")
    elif len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_state()
        print("Interview state cleared.")
    else:
        print("Usage: essence_builder.py [status|clear]")
        print("  Primarily used as a library by Jane's interview system.")
