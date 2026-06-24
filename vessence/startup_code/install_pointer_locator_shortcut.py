#!/usr/bin/env python3
"""Install Chieh's MATE Ctrl+M pointer locator shortcut."""

from __future__ import annotations

import argparse
import ast
import shlex
import subprocess
import sys
from pathlib import Path


VESSENCE_HOME = Path(__file__).resolve().parents[1]
POINTER_LOCATOR = VESSENCE_HOME / "startup_code" / "pointer_locator.py"

MATE_KEYBINDING_SCHEMA = (
    "org.mate.control-center.keybinding:"
    "/org/mate/desktop/keybindings/jane-pointer-locator/"
)
MATE_MOUSE_SCHEMA = "org.mate.peripherals-mouse"
MARCO_GLOBAL_SCHEMA = "org.mate.Marco.global-keybindings"
MARCO_COMMAND_SCHEMA = "org.mate.Marco.keybinding-commands"


def run_gsettings(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gsettings", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def gsettings_get(schema: str, key: str) -> object:
    output = run_gsettings("get", schema, key).stdout.strip()
    return ast.literal_eval(output)


def gsettings_set(schema: str, key: str, value: str) -> None:
    run_gsettings("set", schema, key, value)


def dependency_check(python: Path) -> None:
    code = (
        "import gi, cairo; "
        "gi.require_version('Gtk', '3.0'); "
        "gi.require_version('Gdk', '3.0'); "
        "from gi.repository import Gtk, Gdk, GLib"
    )
    try:
        subprocess.run(
            [str(python), "-c", code],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        print(
            f"{python} cannot import GTK bindings required by pointer_locator.py.",
            file=sys.stderr,
        )
        if details:
            print(details, file=sys.stderr)
        print(
            "Install python3-gi, python3-cairo, and gir1.2-gtk-3.0, "
            "or pass --python to a Python that has them.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc


def cleanup_legacy_marco_shortcut() -> None:
    try:
        legacy_binding = gsettings_get(MARCO_GLOBAL_SCHEMA, "run-command-9")
        legacy_action = gsettings_get(MARCO_COMMAND_SCHEMA, "command-9")
    except Exception:
        return

    if not isinstance(legacy_binding, str) or not isinstance(legacy_action, str):
        return

    action_looks_managed = any(
        marker in legacy_action
        for marker in ("pointer_locator.py", "Gtk.WindowType.POPUP", "locate-pointer")
    )
    binding_looks_managed = legacy_binding in {"<Control>m", "<Primary>m", "disabled"}
    if action_looks_managed and binding_looks_managed:
        gsettings_set(MARCO_GLOBAL_SCHEMA, "run-command-9", "disabled")
        gsettings_set(MARCO_COMMAND_SCHEMA, "command-9", " ")


def install_shortcut(binding: str, python: Path) -> None:
    action = shlex.join([str(python), str(POINTER_LOCATOR)])
    gsettings_set(MATE_MOUSE_SCHEMA, "locate-pointer", "false")
    gsettings_set(MATE_KEYBINDING_SCHEMA, "name", "Jane pointer locator")
    gsettings_set(MATE_KEYBINDING_SCHEMA, "action", action)
    gsettings_set(MATE_KEYBINDING_SCHEMA, "binding", binding)
    cleanup_legacy_marco_shortcut()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--binding",
        default="<Control>m",
        help="MATE accelerator for the pointer locator",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=Path("/usr/bin/python3"),
        help="Python executable with GTK 3 bindings",
    )
    parser.add_argument(
        "--skip-dependency-check",
        action="store_true",
        help="install the shortcut without validating Python GTK imports",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    python = args.python
    if not python.exists():
        print(f"Python executable not found: {python}", file=sys.stderr)
        return 2
    if not POINTER_LOCATOR.exists():
        print(f"Pointer locator script not found: {POINTER_LOCATOR}", file=sys.stderr)
        return 2
    if not args.skip_dependency_check:
        dependency_check(python)

    install_shortcut(args.binding, python)
    print(f"Installed pointer locator shortcut: {args.binding}")
    print(f"Action: {shlex.join([str(python), str(POINTER_LOCATOR)])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
