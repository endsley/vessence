from pathlib import Path

from agent_skills import ra_research_cron
from agent_skills.ra_research_artifacts import (
    html_to_text,
    is_jats_article_xml,
    pmc_xml_to_text,
    pubmed_abstract_text,
    raw_source_suffix,
    slugify,
    source_folder,
    web_source_folder,
    web_source_record,
)


def test_ra_research_cron_uses_artifact_helpers():
    assert ra_research_cron.slugify is slugify
    assert ra_research_cron.html_to_text is html_to_text
    assert ra_research_cron.pmc_xml_to_text is pmc_xml_to_text
    assert ra_research_cron.is_jats_article_xml is is_jats_article_xml
    assert ra_research_cron._source_folder is source_folder
    assert ra_research_cron.pubmed_abstract_text is pubmed_abstract_text
    assert ra_research_cron.web_source_folder is web_source_folder
    assert ra_research_cron.web_source_record is web_source_record
    assert ra_research_cron.raw_source_suffix is raw_source_suffix


def test_slugify_preserves_source_fallback_truncation_and_allowed_chars():
    assert slugify("  RA remission / Treat-to-target!  ") == "ra-remission-treat-to-target"
    assert slugify("!!!") == "source"
    assert slugify("Abc.Def_123", max_len=7) == "abc.def"


def test_html_to_text_removes_page_chrome_and_cleans_whitespace():
    html = """
    <html><body>
      <header>Header</header><nav>Nav</nav>
      <main><h1>Title</h1><p>Useful   text</p></main>
      <script>bad()</script><footer>Footer</footer>
    </body></html>
    """

    assert html_to_text(html) == "Title Useful text"


def test_pmc_xml_to_text_removes_reference_table_and_permission_noise():
    xml = """
    <article><body><sec>Body text</sec><fig>Figure caption</fig>
    <table-wrap>Table</table-wrap><permissions>Copyright</permissions>
    <ref-list>References</ref-list></body></article>
    """

    assert pmc_xml_to_text(xml) == "Body text"


def test_is_jats_article_xml_rejects_html_wrappers():
    assert is_jats_article_xml("<article><body>Body</body></article>") is True
    assert is_jats_article_xml("<html><body>Body</body></html>") is False


def test_source_folder_uses_record_title_or_source_id():
    assert source_folder(Path("/papers"), {"source_id": "pmid_1", "title": "RA Study!"}) == Path(
        "/papers/pmid_1_ra-study"
    )
    assert source_folder(Path("/papers"), {"source_id": "pmid_2", "title": ""}) == Path(
        "/papers/pmid_2_pmid_2"
    )


def test_pubmed_abstract_text_preserves_saved_metadata_format():
    text = pubmed_abstract_text(
        {
            "title": "Title",
            "pmid": "123",
            "doi": "10.1/example",
            "pmcid": "PMC123",
            "journal": "Journal",
            "published": "2026",
            "url": "https://example.test",
            "abstract": "Abstract body.",
        }
    )

    assert text == (
        "Title: Title\n"
        "PMID: 123\n"
        "DOI: 10.1/example\n"
        "PMCID: PMC123\n"
        "Journal: Journal\n"
        "Published: 2026\n"
        "URL: https://example.test\n"
        "\n"
        "Abstract:\n"
        "Abstract body.\n"
    )


def test_web_source_helpers_preserve_metadata_and_suffix_rules():
    source = {
        "id": "acr_page",
        "title": "ACR RA Guideline",
        "url": "https://example.test/guideline",
        "kind": "guideline",
    }

    assert web_source_folder(Path("/papers"), source) == Path("/papers/web_acr_page_acr-ra-guideline")
    assert web_source_record(source, fetched_at="now") == {
        "source_type": "web_guideline",
        "source_id": "web_acr_page",
        "title": "ACR RA Guideline",
        "url": "https://example.test/guideline",
        "kind": "guideline",
        "fetched_at": "now",
    }
    assert raw_source_suffix("application/xml; charset=utf-8") == ".xml"
    assert raw_source_suffix("text/html") == ".html"
