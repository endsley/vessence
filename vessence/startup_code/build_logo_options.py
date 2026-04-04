#!/usr/bin/env python3
from __future__ import annotations

import html
from pathlib import Path


OUT_DIR = Path("/home/chieh/ambient/vault/images/logo_options")
SIZE = 512
CENTER = 256


PALETTES = [
    ("midnight", "#0f172a", "#e2e8f0"),
    ("sand", "#f6f1e8", "#1f2937"),
    ("teal", "#0f766e", "#ecfeff"),
    ("plum", "#5b21b6", "#f5f3ff"),
    ("charcoal", "#111827", "#f9fafb"),
]


MARKS = [
    ("v_letter", "Minimal V"),
    ("vessel", "Minimal vessel"),
    ("orb", "Single memory orb"),
    ("double_orb", "Two companions"),
    ("ring", "Open memory ring"),
    ("halo_v", "Halo over V"),
    ("bridge", "Bridge mark"),
    ("seed", "Small seed spark"),
    ("split", "Split dual form"),
    ("monogram", "Vessences monogram"),
]


def shell(bg: str, fg: str, body: str, label: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" role="img" aria-label="{html.escape(label)}">
  <rect width="{SIZE}" height="{SIZE}" rx="128" fill="{bg}"/>
  {body}
</svg>
"""


def draw(mark: str, bg: str, fg: str) -> str:
    if mark == "v_letter":
        return f'<path d="M 152 150 L 236 372 Q 246 398 256 398 Q 266 398 276 372 L 360 150" fill="none" stroke="{fg}" stroke-width="30" stroke-linecap="round" stroke-linejoin="round"/>'
    if mark == "vessel":
        return f'<path d="M 164 278 Q 256 372 348 278" fill="none" stroke="{fg}" stroke-width="28" stroke-linecap="round"/><path d="M 196 226 Q 256 208 316 226" fill="none" stroke="{fg}" stroke-width="14" stroke-linecap="round" opacity="0.8"/>'
    if mark == "orb":
        return f'<circle cx="{CENTER}" cy="{CENTER}" r="94" fill="none" stroke="{fg}" stroke-width="26"/><circle cx="{CENTER}" cy="{CENTER}" r="28" fill="{fg}"/>'
    if mark == "double_orb":
        return f'<circle cx="208" cy="256" r="58" fill="{fg}" opacity="0.95"/><circle cx="304" cy="256" r="58" fill="{fg}" opacity="0.55"/>'
    if mark == "ring":
        return f'<path d="M 152 256 A 104 104 0 1 1 360 256" fill="none" stroke="{fg}" stroke-width="28" stroke-linecap="round"/><circle cx="360" cy="256" r="12" fill="{fg}"/>'
    if mark == "halo_v":
        return f'<path d="M 170 188 Q 256 118 342 188" fill="none" stroke="{fg}" stroke-width="18" stroke-linecap="round"/><path d="M 176 236 L 238 372 Q 246 390 256 390 Q 266 390 274 372 L 336 236" fill="none" stroke="{fg}" stroke-width="26" stroke-linecap="round" stroke-linejoin="round"/>'
    if mark == "bridge":
        return f'<circle cx="178" cy="266" r="28" fill="{fg}"/><circle cx="334" cy="266" r="28" fill="{fg}"/><path d="M 206 266 Q 256 204 306 266" fill="none" stroke="{fg}" stroke-width="22" stroke-linecap="round"/>'
    if mark == "seed":
        return f'<path d="M 256 330 C 218 304 214 252 256 212 C 298 252 294 304 256 330 Z" fill="{fg}"/><path d="M 256 310 C 252 270 268 240 302 216" fill="none" stroke="{bg}" stroke-width="12" stroke-linecap="round"/>'
    if mark == "split":
        return f'<path d="M 186 174 L 246 256 L 186 338" fill="none" stroke="{fg}" stroke-width="28" stroke-linecap="round" stroke-linejoin="round"/><path d="M 326 174 L 266 256 L 326 338" fill="none" stroke="{fg}" stroke-width="28" stroke-linecap="round" stroke-linejoin="round"/>'
    if mark == "monogram":
        return f'<path d="M 154 160 L 218 352 Q 228 384 256 384 Q 284 384 294 352 L 358 160" fill="none" stroke="{fg}" stroke-width="28" stroke-linecap="round" stroke-linejoin="round"/><path d="M 222 230 H 290" fill="none" stroke="{fg}" stroke-width="18" stroke-linecap="round"/>'
    raise ValueError(mark)


def write_gallery(records: list[dict[str, str]]) -> None:
    cards = []
    for record in records:
        cards.append(
            f"""
      <a class="card" href="{record['filename']}" target="_blank" rel="noopener">
        <img src="{record['filename']}" alt="{html.escape(record['label'])}" />
        <div class="meta">
          <strong>{html.escape(record['label'])}</strong>
          <span>{html.escape(record['description'])}</span>
        </div>
      </a>"""
        )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Vessences Simple Logo Options</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #08111f;
      --panel: #101a2a;
      --line: #22324a;
      --text: #ecf3fb;
      --muted: #9fb0c6;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--text); }}
    .wrap {{ width: min(1280px, calc(100vw - 32px)); margin: 0 auto; padding: 28px 0 40px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 4vw, 3rem); }}
    p {{ margin: 0 0 24px; color: var(--muted); max-width: 720px; line-height: 1.5; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(176px, 1fr)); gap: 16px; }}
    .card {{ display: block; text-decoration: none; color: inherit; background: var(--panel); border: 1px solid var(--line); border-radius: 22px; overflow: hidden; }}
    .card:hover {{ border-color: #6ee7f9; }}
    img {{ display: block; width: 100%; aspect-ratio: 1 / 1; background: #030712; }}
    .meta {{ padding: 12px 14px 16px; }}
    strong {{ display: block; margin-bottom: 5px; font-size: 0.95rem; }}
    span {{ color: var(--muted); font-size: 0.84rem; line-height: 1.35; }}
  </style>
</head>
<body>
  <main class="wrap">
    <h1>Vessences Simple Logo Options</h1>
    <p>Fifty simpler marks for the website and app: clean silhouettes, minimal strokes, and shapes that can survive favicon and launcher-icon sizes.</p>
    <section class="grid">
      {''.join(cards)}
    </section>
  </main>
</body>
</html>
"""
    (OUT_DIR / "index.html").write_text(html_text, encoding="utf-8")
    (OUT_DIR / "README.md").write_text(
        "\n".join([f"- `{r['label']}` — {r['description']} (`{r['filename']}`)" for r in records]) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, str]] = []
    counter = 1
    for palette_name, bg, fg in PALETTES:
        for mark_key, mark_name in MARKS:
            filename = f"{counter:02d}_{mark_key}_{palette_name}.svg"
            label = f"Option {counter:02d}"
            description = f"{mark_name} in {palette_name}"
            svg = shell(bg, fg, draw(mark_key, bg, fg), f"Vessences {description}")
            (OUT_DIR / filename).write_text(svg, encoding="utf-8")
            records.append({
                "filename": filename,
                "label": label,
                "description": description,
            })
            counter += 1
    write_gallery(records)
    print(f"Wrote {len(records)} simple logo options to {OUT_DIR}")


if __name__ == "__main__":
    main()
