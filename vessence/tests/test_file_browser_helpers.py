import pytest

from jane_web.file_browser_helpers import (
    FILE_TYPE_EXTENSIONS,
    MIME_TO_SUBDIR,
    byte_range_bounds,
    detect_file_type,
    paginate_listing,
    range_response,
    route_subdir,
)


def test_route_subdir_maps_mime_types_to_upload_subdirs():
    assert route_subdir("application/pdf") == "pdf"
    assert route_subdir("image/png") == "images"
    assert route_subdir("audio/mpeg") == "audio"
    assert route_subdir("video/mp4") == "video"
    assert route_subdir("text/plain") == "documents"
    assert route_subdir("") == "documents"
    assert MIME_TO_SUBDIR["image"] == "images"


def test_paginate_listing_preserves_full_listing_without_limit_or_on_error():
    listing = {"folders": ["a"], "files": ["one", "two"]}
    assert paginate_listing(listing, offset=1, limit=0) is listing
    assert listing == {"folders": ["a"], "files": ["one", "two"]}

    error_listing = {"error": "nope", "files": ["one", "two"]}
    assert paginate_listing(error_listing, offset=1, limit=1) is error_listing
    assert error_listing == {"error": "nope", "files": ["one", "two"]}


def test_paginate_listing_mutates_file_slice_and_metadata():
    listing = {"folders": ["a"], "files": ["one", "two", "three"]}

    result = paginate_listing(listing, offset=1, limit=1)

    assert result is listing
    assert result["folders"] == ["a"]
    assert result["files"] == ["two"]
    assert result["total_files"] == 3
    assert result["offset"] == 1
    assert result["limit"] == 1


def test_detect_file_type_uses_extension_sets_case_insensitively():
    assert detect_file_type("Song.MP3") == "audio"
    assert detect_file_type("photo.JPEG") == "image"
    assert detect_file_type("clip.webm") == "video"
    assert detect_file_type("notes.md") == "document"
    assert detect_file_type("archive.zip") == "other"
    assert ".pdf" in FILE_TYPE_EXTENSIONS["document"]


def test_byte_range_bounds_preserves_existing_permissive_parsing():
    assert byte_range_bounds("bytes=2-4", 6) == (2, 4, 3)
    assert byte_range_bounds("bytes=2-", 6) == (2, 5, 4)
    assert byte_range_bounds("bytes=-4", 6) == (0, 4, 5)
    assert byte_range_bounds("not-a-range", 6) == (0, 5, 6)


@pytest.mark.asyncio
async def test_range_response_parses_range_header_and_streams_bytes(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"abcdef")

    response = range_response(path, "text/plain", "bytes=2-4")
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 2-4/6"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "3"
    assert b"".join(chunks) == b"cde"


def test_range_response_falls_back_to_full_file_for_invalid_header(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"abcdef")

    response = range_response(path, "text/plain", "not-a-range")

    assert response.headers["content-range"] == "bytes 0-5/6"
    assert response.headers["content-length"] == "6"
