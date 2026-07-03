from pathlib import Path

from agent_skills.ra_research_html import build_report_html, markdown_to_report_html, report_id_from_path


def test_markdown_to_report_html_renders_supported_blocks_and_inline_markup():
    markdown = """## Care & Safety

Line **bold** and `code` with [link](https://example.com/path).
continued here.

- one
- two

1. first
2. second
"""

    html = markdown_to_report_html(markdown)

    assert "<h2>Care &amp; Safety</h2>" in html
    assert (
        '<p>Line <strong>bold</strong> and <code>code</code> with '
        '<a href="https://example.com/path">link</a>. continued here.</p>'
    ) in html
    assert "<ul><li>one</li><li>two</li></ul>" in html
    assert "<ol><li>first</li><li>second</li></ol>" in html


def test_markdown_to_report_html_escapes_raw_html():
    html = markdown_to_report_html("# <script>alert(1)</script>\n\nRaw <b>tag</b>")

    assert "<h1>&lt;script&gt;alert(1)&lt;/script&gt;</h1>" in html
    assert "<p>Raw &lt;b&gt;tag&lt;/b&gt;</p>" in html


def test_report_id_from_path_removes_cron_prefix():
    assert report_id_from_path(Path("/tmp/ra_research_run_20260702_120000.md")) == "20260702_120000"
    assert report_id_from_path(Path("/tmp/manual_report.md")) == "manual_report"


def test_build_report_html_wraps_body_and_escapes_metadata():
    html = build_report_html(
        "## Bottom Line\n\n- Keep clinician-led plan.",
        "run<&>",
        source_count=2,
        new_count=1,
        generated="July 2, 2026 at 9:00 AM EDT",
    )

    assert html.startswith("<!doctype html>")
    assert "<title>RA remission research update</title>" in html
    assert '<span class="pill">1 new source</span>' in html
    assert '<span class="pill">2 cached sources</span>' in html
    assert "<span>July 2, 2026 at 9:00 AM EDT</span>" in html
    assert "<span>Report run&lt;&amp;&gt;</span>" in html
    assert "<h2>Bottom Line</h2>" in html
    assert "<li>Keep clinician-led plan.</li>" in html
