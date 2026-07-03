from xml.etree import ElementTree as ET

from agent_skills import ra_research_cron
from agent_skills.ra_research_pubmed import (
    parse_article_ids,
    parse_authors,
    parse_pub_date,
    parse_pubmed_article,
    text_of,
)


def article_from_xml(xml: str) -> ET.Element:
    return ET.fromstring(xml)


def test_ra_research_cron_uses_extracted_pubmed_parser():
    assert ra_research_cron.parse_pubmed_article is parse_pubmed_article


def test_text_of_collapses_nested_text_and_missing_nodes():
    node = ET.fromstring("<Title>Alpha <i> beta </i>\n gamma</Title>")

    assert text_of(node) == "Alpha beta gamma"
    assert text_of(None) == ""


def test_parse_pub_date_prefers_article_date_and_pads_missing_parts():
    article = article_from_xml(
        """
        <PubmedArticle>
          <Article>
            <ArticleDate><Year>2026</Year><Month>7</Month></ArticleDate>
            <Journal><JournalIssue><PubDate><Year>2025</Year></PubDate></JournalIssue></Journal>
          </Article>
        </PubmedArticle>
        """
    )

    assert parse_pub_date(article) == "2026-07-01"


def test_parse_pub_date_handles_month_names_and_fallback_text():
    assert parse_pub_date(article_from_xml(
        """
        <PubmedArticle>
          <Journal><JournalIssue><PubDate><Year>2025</Year><Month>Feb</Month><Day>3</Day></PubDate></JournalIssue></Journal>
        </PubmedArticle>
        """
    )) == "2025-02-03"
    assert parse_pub_date(article_from_xml(
        """
        <PubmedArticle>
          <Journal><JournalIssue><PubDate><MedlineDate>Winter 2025</MedlineDate></PubDate></JournalIssue></Journal>
        </PubmedArticle>
        """
    )) == "Winter 2025"


def test_parse_authors_uses_collective_or_fore_last_and_limit():
    article = article_from_xml(
        """
        <PubmedArticle>
          <AuthorList>
            <Author><ForeName>Ada</ForeName><LastName>Lovelace</LastName></Author>
            <Author><CollectiveName>RA Study Group</CollectiveName></Author>
            <Author><LastName>Hidden</LastName></Author>
          </AuthorList>
        </PubmedArticle>
        """
    )

    assert parse_authors(article, limit=2) == ["Ada Lovelace", "RA Study Group"]


def test_parse_article_ids_lowercases_id_types_and_skips_empty_values():
    article = article_from_xml(
        """
        <PubmedArticle>
          <ArticleIdList>
            <ArticleId IdType="doi">10.1/example</ArticleId>
            <ArticleId IdType="pmc"> PMC123 </ArticleId>
            <ArticleId IdType=""></ArticleId>
          </ArticleIdList>
        </PubmedArticle>
        """
    )

    assert parse_article_ids(article) == {"doi": "10.1/example", "pmc": "PMC123"}


def test_parse_pubmed_article_preserves_record_shape():
    article = article_from_xml(
        """
        <PubmedArticle>
          <MedlineCitation>
            <PMID>12345</PMID>
            <Article>
              <ArticleTitle>RA remission <i>study</i></ArticleTitle>
              <Journal>
                <Title>Journal of RA</Title>
                <JournalIssue><PubDate><Year>2024</Year><Month>Dec</Month></PubDate></JournalIssue>
              </Journal>
              <AuthorList>
                <Author><ForeName>Jane</ForeName><LastName>Doe</LastName></Author>
              </AuthorList>
              <Abstract>
                <AbstractText Label="Background">First part.</AbstractText>
                <AbstractText NlmCategory="RESULTS">Second part.</AbstractText>
              </Abstract>
              <PublicationTypeList>
                <PublicationType>Clinical Trial</PublicationType>
                <PublicationType></PublicationType>
              </PublicationTypeList>
            </Article>
            <MeshHeadingList>
              <MeshHeading><DescriptorName>Arthritis, Rheumatoid</DescriptorName></MeshHeading>
            </MeshHeadingList>
          </MedlineCitation>
          <PubmedData>
            <ArticleIdList>
              <ArticleId IdType="doi">10.1/example</ArticleId>
              <ArticleId IdType="pmc">PMC123</ArticleId>
            </ArticleIdList>
          </PubmedData>
        </PubmedArticle>
        """
    )

    assert parse_pubmed_article(article) == {
        "source_type": "pubmed",
        "source_id": "pubmed_12345",
        "pmid": "12345",
        "pmcid": "PMC123",
        "doi": "10.1/example",
        "title": "RA remission study",
        "journal": "Journal of RA",
        "published": "2024-12-01",
        "authors": ["Jane Doe"],
        "abstract": "Background: First part.\nRESULTS: Second part.",
        "publication_types": ["Clinical Trial"],
        "mesh_terms": ["Arthritis, Rheumatoid"],
        "url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
    }


def test_parse_pubmed_article_returns_none_without_pmid():
    assert parse_pubmed_article(article_from_xml("<PubmedArticle />")) is None
