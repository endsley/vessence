"""HTML rendering helpers for RA research reports."""

from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")


def inline_report_markdown_html(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", lambda m: f"<strong>{m.group(1)}</strong>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
        escaped,
    )
    return escaped


def report_paragraph_html(lines: list[str]) -> str:
    return f"<p>{inline_report_markdown_html(' '.join(lines))}</p>" if lines else ""


def report_list_html(list_lines: list[tuple[str, str]]) -> str:
    if not list_lines:
        return ""
    tag = "ol" if list_lines[0][0] == "ol" else "ul"
    items = "".join(f"<li>{inline_report_markdown_html(item)}</li>" for _, item in list_lines)
    return f"<{tag}>{items}</{tag}>"


def markdown_to_report_html(markdown: str) -> str:
    """Small Markdown subset renderer for app-facing research reports."""
    blocks: list[str] = []
    list_lines: list[tuple[str, str]] = []
    para_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal para_lines
        paragraph_html = report_paragraph_html(para_lines)
        if paragraph_html:
            blocks.append(paragraph_html)
            para_lines = []

    def flush_list() -> None:
        nonlocal list_lines
        list_html = report_list_html(list_lines)
        if list_html:
            blocks.append(list_html)
            list_lines = []

    for raw in markdown.splitlines():
        stripped = raw.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            flush_list()
            level = min(len(heading.group(1)), 4)
            blocks.append(f"<h{level}>{html.escape(heading.group(2))}</h{level}>")
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        numbered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if bullet or numbered:
            flush_paragraph()
            kind = "ol" if numbered else "ul"
            text = (numbered or bullet).group(1)
            if list_lines and list_lines[0][0] != kind:
                flush_list()
            list_lines.append((kind, text))
            continue
        flush_list()
        para_lines.append(stripped)

    flush_paragraph()
    flush_list()
    return "\n".join(blocks)


def report_id_from_path(report_path: Path) -> str:
    return report_path.stem.removeprefix("ra_research_run_")


def build_report_html(
    report_markdown: str,
    report_id: str,
    source_count: int,
    new_count: int,
    *,
    generated: str | None = None,
) -> str:
    generated = generated or dt.datetime.now(TZ).strftime("%B %-d, %Y at %-I:%M %p %Z")
    title = "RA remission research update"
    body_html = markdown_to_report_html(report_markdown)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #637086;
      --line: #d8e2ef;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --accent: #0f7b75;
      --accent-soft: #dff4f1;
      --warn: #8a4b00;
      --warn-soft: #fff0d9;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 16px/1.58 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ width: min(980px, 100%); margin: 0 auto; padding: 24px 18px 56px; }}
    header {{ padding: 28px 0 20px; border-bottom: 1px solid var(--line); margin-bottom: 22px; }}
    .eyebrow {{ color: var(--accent); font-size: 13px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; margin: 0 0 8px; }}
    h1 {{ font-size: clamp(30px, 7vw, 52px); line-height: 1.04; margin: 0 0 14px; letter-spacing: 0; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 10px; color: var(--muted); font-size: 14px; }}
    .pill {{ background: var(--accent-soft); color: #07534f; border: 1px solid #b9e4df; border-radius: 999px; padding: 5px 10px; font-weight: 650; }}
    .safety {{ background: var(--warn-soft); border: 1px solid #ffd79c; color: var(--warn); padding: 14px 16px; border-radius: 8px; margin: 0 0 24px; font-weight: 600; }}
    article {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: clamp(18px, 4vw, 34px); box-shadow: 0 12px 40px rgba(15, 35, 55, .07); }}
    h1, h2, h3, h4 {{ color: var(--ink); }}
    article h1:first-child {{ display: none; }}
    h2 {{ font-size: 24px; margin: 30px 0 12px; padding-top: 8px; border-top: 1px solid var(--line); }}
    h3 {{ font-size: 19px; margin: 24px 0 8px; }}
    p {{ margin: 0 0 14px; }}
    ul, ol {{ padding-left: 1.35rem; margin: 0 0 16px; }}
    li {{ margin: 6px 0; }}
    code {{ background: #edf2f7; border: 1px solid #d8e2ef; border-radius: 5px; padding: 1px 5px; font-size: .92em; overflow-wrap: anywhere; }}
    a {{ color: var(--accent); }}
    @media (max-width: 640px) {{
      main {{ padding: 18px 12px 42px; }}
      header {{ padding-top: 20px; }}
      article {{ border-radius: 0; margin-inline: -12px; border-left: 0; border-right: 0; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">Rheumatoid Arthritis Research</p>
      <h1>RA remission research update</h1>
      <div class="meta">
        <span class="pill">{new_count} new source{'' if new_count == 1 else 's'}</span>
        <span class="pill">{source_count} cached source{'' if source_count == 1 else 's'}</span>
        <span>{html.escape(generated)}</span>
        <span>Report {html.escape(report_id)}</span>
      </div>
    </header>
    <div class="safety">Research support only. Use this to prepare discussion with Kathia and her rheumatologist; do not change medication, supplements, or treatment from this report alone.</div>
    <article>
      {body_html}
    </article>
  </main>
</body>
</html>
"""
