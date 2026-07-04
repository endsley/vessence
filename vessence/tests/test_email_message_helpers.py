import base64

from agent_skills import email_tools
from agent_skills.email_message_helpers import (
    decode_body_data,
    extract_attachments,
    extract_plain_body,
    parse_headers,
    strip_html_tags,
)


def _encoded(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_email_tools_uses_extracted_payload_helpers():
    assert email_tools._parse_headers is parse_headers
    assert email_tools._extract_plain_body is extract_plain_body
    assert email_tools._extract_attachments is extract_attachments


def test_email_tools_mime_builder_preserves_headers_and_plain_body() -> None:
    message = email_tools._build_mime_email(
        body="Hello Bob",
        sender="sender@example.com",
        to="bob@example.com",
        subject="Meeting",
        cc="cc@example.com",
        bcc="bcc@example.com",
    )

    assert message["from"] == "sender@example.com"
    assert message["to"] == "bob@example.com"
    assert message["subject"] == "Meeting"
    assert message["cc"] == "cc@example.com"
    assert message["bcc"] == "bcc@example.com"
    assert message.get_payload(decode=True).decode() == "Hello Bob"


def test_email_tools_mime_builder_omits_empty_optional_headers() -> None:
    message = email_tools._build_mime_email(
        body="Hello",
        sender="",
        to="bob@example.com",
        subject="Meeting",
    )

    assert "from" not in message
    assert "cc" not in message
    assert "bcc" not in message


def test_parse_headers_keeps_common_headers_case_insensitively():
    headers = [
        {"name": "From", "value": "a@example.com"},
        {"name": "SUBJECT", "value": "Hello"},
        {"name": "X-Trace", "value": "ignored"},
    ]

    assert parse_headers(headers) == {
        "from": "a@example.com",
        "subject": "Hello",
    }


def test_extract_plain_body_returns_first_body_in_recursive_part_order():
    plain = {"mimeType": "text/plain", "body": {"data": _encoded("plain body")}}
    html = {"mimeType": "text/html", "body": {"data": _encoded("<b>html body</b>")}}

    assert decode_body_data(_encoded("hello")) == "hello"
    assert strip_html_tags("<p>Hello</p><br>World") == "HelloWorld"
    assert extract_plain_body({"mimeType": "multipart/alternative", "parts": [html, plain]}) == "html body"
    assert extract_plain_body({"mimeType": "multipart/alternative", "parts": [plain, html]}) == "plain body"
    assert extract_plain_body(html) == "html body"
    assert extract_plain_body({"mimeType": "text/plain", "body": {}}) == ""


def test_extract_attachments_recurses_nested_parts():
    payload = {
        "parts": [
            {
                "filename": "a.pdf",
                "mimeType": "application/pdf",
                "body": {"size": 12, "attachmentId": "att-a"},
            },
            {
                "parts": [
                    {
                        "filename": "b.txt",
                        "mimeType": "text/plain",
                        "body": {"size": 3, "attachmentId": "att-b"},
                    }
                ]
            },
        ]
    }

    assert extract_attachments(payload) == [
        {
            "filename": "a.pdf",
            "mime_type": "application/pdf",
            "size": 12,
            "attachment_id": "att-a",
        },
        {
            "filename": "b.txt",
            "mime_type": "text/plain",
            "size": 3,
            "attachment_id": "att-b",
        },
    ]
