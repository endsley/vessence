"""Pure PubMed XML parsing helpers for RA research."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET


def text_of(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def parse_pub_date(article: ET.Element) -> str:
    article_date = article.find(".//ArticleDate")
    if article_date is not None:
        year = text_of(article_date.find("Year"))
        month = text_of(article_date.find("Month")) or "01"
        day = text_of(article_date.find("Day")) or "01"
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}" if year else ""

    pub_date = article.find(".//JournalIssue/PubDate")
    if pub_date is None:
        return ""
    year = text_of(pub_date.find("Year"))
    month = text_of(pub_date.find("Month"))
    day = text_of(pub_date.find("Day")) or "01"
    month_map = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
        "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
    }
    if month and not month.isdigit():
        month = month_map.get(month[:3], "01")
    month = (month or "01").zfill(2)
    return f"{year}-{month}-{day.zfill(2)}" if year else text_of(pub_date)


def parse_authors(article: ET.Element, limit: int = 12) -> list[str]:
    authors = []
    for author in article.findall(".//AuthorList/Author")[:limit]:
        last = text_of(author.find("LastName"))
        fore = text_of(author.find("ForeName"))
        collective = text_of(author.find("CollectiveName"))
        name = collective or " ".join(part for part in (fore, last) if part)
        if name:
            authors.append(name)
    return authors


def parse_article_ids(article: ET.Element) -> dict[str, str]:
    ids: dict[str, str] = {}
    for node in article.findall(".//ArticleIdList/ArticleId"):
        id_type = (node.attrib.get("IdType") or "").lower()
        value = text_of(node)
        if id_type and value:
            ids[id_type] = value
    return ids


def parse_pubmed_article(article: ET.Element) -> dict[str, Any] | None:
    pmid = text_of(article.find(".//PMID"))
    if not pmid:
        return None
    ids = parse_article_ids(article)
    abstract_parts = []
    for node in article.findall(".//Abstract/AbstractText"):
        label = node.attrib.get("Label") or node.attrib.get("NlmCategory") or ""
        content = text_of(node)
        if content:
            abstract_parts.append(f"{label}: {content}" if label else content)
    title = text_of(article.find(".//ArticleTitle"))
    journal = text_of(article.find(".//Journal/Title")) or text_of(article.find(".//Journal/ISOAbbreviation"))
    publication_types = [text_of(node) for node in article.findall(".//PublicationTypeList/PublicationType")]
    mesh_terms = [text_of(node.find("DescriptorName")) for node in article.findall(".//MeshHeadingList/MeshHeading")]
    return {
        "source_type": "pubmed",
        "source_id": f"pubmed_{pmid}",
        "pmid": pmid,
        "pmcid": ids.get("pmc", ""),
        "doi": ids.get("doi", ""),
        "title": title,
        "journal": journal,
        "published": parse_pub_date(article),
        "authors": parse_authors(article),
        "abstract": "\n".join(abstract_parts),
        "publication_types": [p for p in publication_types if p],
        "mesh_terms": [m for m in mesh_terms if m],
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }
