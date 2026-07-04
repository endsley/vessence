"""Pure persona builders for fallback_query.py."""

from __future__ import annotations


def amber_capability_text(capabilities: list[dict]) -> str:
    text = ""
    for cap in capabilities:
        text += (
            f"- {cap['name']}: {cap['description']} "
            f"(Tools: {', '.join(cap['tools'])})\n"
        )
        if "fallback_tag" in cap:
            text += (
                f"  IMPORTANT: To use this, say '{cap['fallback_tag']}' "
                "on a new line.\n"
            )
    return text


def persona_essay_section(title: str, essay: str) -> str:
    return f"\n\n## {title}:\n{essay}" if essay else ""


def user_essay_title(user_name: str, essay_user_name: str | None = None) -> str:
    return f"ABOUT {(essay_user_name or user_name).upper()} (your user)"


def build_amber_persona(
    manifest: dict,
    *,
    user_name: str,
    essay_user_name: str | None = None,
    amber_essay: str = "",
    user_essay: str = "",
    jane_essay: str = "",
) -> str:
    persona = (
        f"You are {manifest['identity']}, {manifest['role']} "
        f"Family: {manifest['family_context']}. "
        "You are currently an emergency fallback brain. "
        "Your physical body and tools are still active. "
        "CAPABILITIES:\n"
    )

    persona += amber_capability_text(manifest["capabilities"])

    persona += "\nIDENTITY RULES:\n"
    for rule in manifest.get("identity_rules", []):
        persona += f"- {rule}\n"

    persona += (
        f"\nVISUALS: Your photo is '{manifest['visuals']['self']}'. "
        f"Jane is '{manifest['visuals']['colleague']}'. "
        "Never say you cannot perform a task that falls within these capabilities. "
        f"Be warm, efficient, and stay in character as {user_name}'s assistant Amber."
    )

    persona += persona_essay_section("YOUR IDENTITY (Amber)", amber_essay)
    persona += persona_essay_section(user_essay_title(user_name, essay_user_name), user_essay)
    persona += persona_essay_section("ABOUT JANE (your colleague)", jane_essay)

    return persona


def amber_fallback_persona(user_name: str) -> str:
    return (
        f"You are Amber, {user_name}'s assistant. "
        "You are currently in fallback mode."
    )


def build_jane_persona(
    *,
    user_name: str,
    essay_user_name: str | None = None,
    jane_essay: str = "",
    user_essay: str = "",
) -> str:
    base = (
        f"You are Jane, {user_name}'s technical expert and friend. "
        "You are currently acting as an emergency fallback because the primary model is unavailable. "
        "Keep your expert persona and help the user as much as you can with your knowledge."
    )
    base += persona_essay_section("YOUR IDENTITY (Jane)", jane_essay)
    base += persona_essay_section(user_essay_title(user_name, essay_user_name), user_essay)
    return base
