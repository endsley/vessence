from pathlib import Path

from jane_web.briefing_media import (
    briefing_archive_path,
    briefing_image_candidates,
    daily_briefing_audio_dir,
    daily_briefing_image_dir,
    is_archive_date,
    is_briefing_identifier,
    select_briefing_audio,
)


def test_briefing_identifier_preserves_existing_regex_contract():
    assert is_briefing_identifier("article_123-ABC")
    assert not is_briefing_identifier("article.123")
    assert not is_briefing_identifier("../article")
    assert not is_briefing_identifier("")


def test_archive_date_validation_uses_existing_shape_only_contract():
    assert is_archive_date("2026-07-02")
    assert is_archive_date("2026-99-99")
    assert not is_archive_date("2026-7-2")
    assert not is_archive_date("../2026-07-02")


def test_briefing_audio_dir_and_selection_prefer_ogg_over_wav():
    existing = {
        "/tools/daily_briefing/essence_data/audio/a1_brief.ogg",
        "/tools/daily_briefing/essence_data/audio/a1_brief.wav",
    }

    assert daily_briefing_audio_dir("/tools") == "/tools/daily_briefing/essence_data/audio"
    assert select_briefing_audio(
        "/tools/daily_briefing/essence_data/audio",
        "a1",
        "brief",
        is_file=existing.__contains__,
    ) == ("/tools/daily_briefing/essence_data/audio/a1_brief.ogg", "audio/ogg")
    assert select_briefing_audio(
        "/tools/daily_briefing/essence_data/audio",
        "missing",
        "brief",
        is_file=existing.__contains__,
    ) is None


def test_briefing_audio_selection_falls_back_to_wav():
    existing = {"/tools/daily_briefing/essence_data/audio/a1_brief.wav"}

    assert select_briefing_audio(
        "/tools/daily_briefing/essence_data/audio",
        "a1",
        "brief",
        is_file=existing.__contains__,
    ) == ("/tools/daily_briefing/essence_data/audio/a1_brief.wav", "audio/wav")


def test_image_candidates_and_archive_path_match_existing_layouts():
    image_dir = daily_briefing_image_dir("/tools")

    assert image_dir == Path("/tools/daily_briefing/essence_data/images")
    assert briefing_image_candidates(image_dir, "a1") == [
        image_dir / "a1.jpg",
        image_dir / "a1.jpeg",
        image_dir / "a1.png",
        image_dir / "a1.webp",
        image_dir / "a1.gif",
    ]
    assert briefing_archive_path(Path("/data/briefings"), "2026-07-02") == Path(
        "/data/briefings/2026-07-02.json"
    )
