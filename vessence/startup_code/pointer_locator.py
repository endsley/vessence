#!/usr/bin/env python3
"""Flash a pointer locator ring at the current mouse position.

This is intended for Chieh's MATE/X11 desktop shortcut. It uses the system
Python GTK bindings because the Vessence virtualenv does not include PyGObject.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass


DEFAULT_COLOR = (0.05, 0.35, 1.0)


def parse_color(value: str) -> tuple[float, float, float]:
    """Parse #RRGGBB into cairo RGB float components."""
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        raise argparse.ArgumentTypeError("color must be #RRGGBB")
    try:
        red = int(value[0:2], 16) / 255
        green = int(value[2:4], 16) / 255
        blue = int(value[4:6], 16) / 255
    except ValueError as exc:
        raise argparse.ArgumentTypeError("color must be #RRGGBB") from exc
    return red, green, blue


def load_gtk():
    try:
        import cairo
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gtk, Gdk, GLib
    except Exception as exc:
        print(
            "pointer_locator.py requires python3-gi, python3-cairo, and GTK 3 "
            f"bindings: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    return cairo, Gdk, GLib, Gtk


@dataclass(frozen=True)
class LocatorConfig:
    size: int
    duration: float
    color: tuple[float, float, float]
    rings: tuple[float, ...]


class PointerLocator:
    def __init__(self, config: LocatorConfig) -> None:
        self.config = config
        self.cairo, self.Gdk, self.GLib, self.Gtk = load_gtk()
        self.start_us = 0
        self.window = self._build_window()

    def _build_window(self):
        window = self.Gtk.Window(type=self.Gtk.WindowType.POPUP)
        window.set_decorated(False)
        window.set_app_paintable(True)
        window.set_keep_above(True)
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_accept_focus(False)
        window.set_type_hint(self.Gdk.WindowTypeHint.NOTIFICATION)

        screen = window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            window.set_visual(visual)

        window.set_default_size(self.config.size, self.config.size)
        window.connect("draw", self._draw)
        return window

    def _position_at_pointer(self) -> None:
        display = self.Gdk.Display.get_default()
        if display is None:
            raise RuntimeError("no default GDK display")

        seat = display.get_default_seat()
        pointer = seat.get_pointer()
        _screen, x_pos, y_pos = pointer.get_position()
        half_size = self.config.size // 2
        self.window.move(x_pos - half_size, y_pos - half_size)

    def _draw(self, _widget, cr) -> bool:
        elapsed = (self.GLib.get_monotonic_time() - self.start_us) / 1_000_000
        cr.set_operator(self.cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(self.cairo.OPERATOR_OVER)
        cr.set_line_cap(self.cairo.LINE_CAP_ROUND)

        red, green, blue = self.config.color
        for offset in self.config.rings:
            denominator = max(self.config.duration - offset, 0.01)
            progress = (elapsed - offset) / denominator
            if 0 <= progress <= 1:
                radius = 24 + 76 * progress
                alpha = 0.9 * (1 - progress)
                cr.set_source_rgba(red, green, blue, alpha)
                cr.set_line_width(5)
                cr.arc(
                    self.config.size / 2,
                    self.config.size / 2,
                    radius,
                    0,
                    2 * math.pi,
                )
                cr.stroke()
        return False

    def _tick(self) -> bool:
        elapsed = (self.GLib.get_monotonic_time() - self.start_us) / 1_000_000
        if elapsed >= self.config.duration:
            self.Gtk.main_quit()
            return False
        self.window.queue_draw()
        return True

    def run(self) -> int:
        try:
            self._position_at_pointer()
        except Exception as exc:
            print(f"pointer_locator.py failed to find pointer: {exc}", file=sys.stderr)
            return 1

        self.start_us = self.GLib.get_monotonic_time()
        self.window.show_all()
        self.GLib.timeout_add(16, self._tick)
        self.Gtk.main()
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=220, help="overlay window size in pixels")
    parser.add_argument("--duration", type=float, default=0.7, help="animation duration in seconds")
    parser.add_argument(
        "--color",
        type=parse_color,
        default=DEFAULT_COLOR,
        help="ring color as #RRGGBB",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = LocatorConfig(
        size=max(args.size, 80),
        duration=max(args.duration, 0.1),
        color=args.color,
        rings=(0.0, 0.18, 0.36),
    )
    return PointerLocator(config).run()


if __name__ == "__main__":
    raise SystemExit(main())
