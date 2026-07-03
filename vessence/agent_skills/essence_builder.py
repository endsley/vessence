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

from agent_skills.essence_builder_parsing import (
    credentials_from_answer as _credentials_from_answer,
    extract_list_from_answer as _extract_list_from_answer,
    extract_model_id as _extract_model_id,
    extract_quoted_strings as _extract_quoted_strings,
    extract_role_title as _extract_role_title,
    extract_section_fragment as _extract_section_fragment,
    sanitize_essence_folder_name as _sanitize_essence_folder_name,
    select_permissions as _select_permissions,
    select_shared_skills as _select_shared_skills,
    select_ui_type as _select_ui_type,
    trigger_list_from_answer as _trigger_list_from_answer,
)
from agent_skills.essence_builder_interview import (
    extract_essence_name as _extract_essence_name_helper,
    format_questions as _format_questions_from_config,
    progress_summary as _progress_summary,
    section_display_name as _section_display_name_helper,
    section_intro as _section_intro_from_config,
    spec_document as _spec_document,
)
from agent_skills.essence_builder_manifest import manifest_from_answers as _manifest_from_answers
from agent_skills.essence_builder_outputs import (
    custom_tools_stub as _custom_tools_stub,
    essence_layout_payload as _essence_layout_payload,
    onboarding_payload as _onboarding_payload,
    should_write_custom_functions as _should_write_custom_functions,
)

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
    return _section_display_name_helper(index)


def _format_questions(section_index: int, include_optional: bool = False) -> str:
    """Format the questions for a section into a numbered list."""
    return _format_questions_from_config(INTERVIEW_QUESTIONS, section_index, include_optional)


def _section_intro(section_index: int) -> str:
    """Opening message for a section."""
    return _section_intro_from_config(SECTION_NAMES, INTERVIEW_QUESTIONS, section_index)


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
    return _extract_essence_name_helper(answer)


def get_progress(state: EssenceInterviewState) -> str:
    """
    Human-readable progress summary.

    Example: "Sections completed: 3/12 — Identity ✓, Knowledge ✓, Functions ✓, next: Shared Skills"
    """
    return _progress_summary(SECTION_NAMES, state.completed_sections, state.current_section)


# ---------------------------------------------------------------------------
# Spec generation
# ---------------------------------------------------------------------------


def generate_spec_document(state: EssenceInterviewState) -> str:
    """Compile all interview answers into a human-readable markdown spec."""
    return _spec_document(SECTION_NAMES, state.answers, state.essence_name)


def generate_manifest(state: EssenceInterviewState) -> dict:
    """
    Compile answers into a valid manifest.json dict.

    Extracts structured data from free-text answers where possible,
    falling back to sensible defaults.
    """
    return _manifest_from_answers(state.essence_name, state.answers)


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

    folder_name = _sanitize_essence_folder_name(state.essence_name)
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
    if _should_write_custom_functions(custom_funcs):
        funcs_path = os.path.join(essence_path, "functions", "custom_tools.py")
        os.makedirs(os.path.dirname(funcs_path), exist_ok=True)
        with open(funcs_path, "w") as f:
            f.write(_custom_tools_stub(state.essence_name, custom_funcs))

    # Write UI layout stub
    ui_answer = state.answers.get("ui_paradigm", "")
    ui_type = generate_manifest(state)["ui"]["type"]
    layout_path = os.path.join(essence_path, "ui", "layout.json")
    os.makedirs(os.path.dirname(layout_path), exist_ok=True)
    layout = _essence_layout_payload(ui_type, ui_answer)
    with open(layout_path, "w") as f:
        json.dump(layout, f, indent=2)

    # Write onboarding workflow stub
    interaction_answer = state.answers.get("interaction_patterns", "")
    starters = generate_manifest(state)["interaction_patterns"]["conversation_starters"]
    workflows_path = os.path.join(essence_path, "workflows", "onboarding.json")
    os.makedirs(os.path.dirname(workflows_path), exist_ok=True)
    onboarding = _onboarding_payload(starters, interaction_answer)
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
# Text extraction helpers live in `essence_builder_parsing.py` and are imported
# above under their legacy private names for compatibility.


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
