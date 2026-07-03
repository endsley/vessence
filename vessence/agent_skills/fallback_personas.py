"""Pure persona builders for fallback_query.py."""

from __future__ import annotations


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

    for cap in manifest["capabilities"]:
        persona += (
            f"- {cap['name']}: {cap['description']} "
            f"(Tools: {', '.join(cap['tools'])})\n"
        )
        if "fallback_tag" in cap:
            persona += (
                f"  IMPORTANT: To use this, say '{cap['fallback_tag']}' "
                "on a new line.\n"
            )

    persona += "\nIDENTITY RULES:\n"
    for rule in manifest.get("identity_rules", []):
        persona += f"- {rule}\n"

    persona += (
        f"\nVISUALS: Your photo is '{manifest['visuals']['self']}'. "
        f"Jane is '{manifest['visuals']['colleague']}'. "
        "Never say you cannot perform a task that falls within these capabilities. "
        f"Be warm, efficient, and stay in character as {user_name}'s assistant Amber."
    )

    if amber_essay:
        persona += f"\n\n## YOUR IDENTITY (Amber):\n{amber_essay}"
    if user_essay:
        persona += f"\n\n## ABOUT {(essay_user_name or user_name).upper()} (your user):\n{user_essay}"
    if jane_essay:
        persona += f"\n\n## ABOUT JANE (your colleague):\n{jane_essay}"

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
    if jane_essay:
        base += f"\n\n## YOUR IDENTITY (Jane):\n{jane_essay}"
    if user_essay:
        base += f"\n\n## ABOUT {(essay_user_name or user_name).upper()} (your user):\n{user_essay}"
    return base
