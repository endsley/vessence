from agent_skills import chat_error_audit
from agent_skills.chat_error_audit_helpers import (
    chat_error_job_filename,
    chat_error_job_markdown,
    first_android_frame,
    slugify_chat_error,
)


def test_chat_error_audit_uses_extracted_helpers():
    assert chat_error_audit._slugify_chat_error is slugify_chat_error
    assert chat_error_audit._parse_first_android_frame is first_android_frame
    assert chat_error_audit._chat_error_job_filename is chat_error_job_filename
    assert chat_error_audit._chat_error_job_markdown is chat_error_job_markdown


def test_first_android_frame_parses_topmost_vessences_frame():
    stack = "\n".join([
        "at okhttp3.RealCall.execute(RealCall.kt:100)",
        "    at com.vessences.android.chat.StreamClient.read(StreamClient.kt:42)",
        "    at com.vessences.android.MainActivity.onCreate(MainActivity.kt)",
    ])

    assert first_android_frame(stack) == {
        "class_method": "com.vessences.android.chat.StreamClient.read",
        "file": "StreamClient.kt",
        "line": 42,
    }
    assert first_android_frame("") is None
    assert first_android_frame("at example.Other.run(File.kt:1)") is None


def test_chat_error_slug_and_filename_preserve_existing_shape():
    assert slugify_chat_error("Chat Error: java.net.SocketException") == "chat_error_java_net_socketexception"
    assert slugify_chat_error("!!!") == "chat_error"
    assert chat_error_job_filename(7, "java.net.SocketException") == "job_007_chat_error_socketexception.md"
    assert chat_error_job_filename(8, "") == "job_008_chat_error_unknownexception.md"


def test_chat_error_job_markdown_renders_metadata_and_truncates_payload():
    payload = {
        "exception_class": "java.net.SocketException",
        "message": "m" * 405,
        "stack_trace": "s" * 1805,
        "app_version": "1.2.3",
        "version_code": 44,
        "from_voice": True,
    }
    frame = {
        "class_method": "com.vessences.android.chat.StreamClient.read",
        "file": "StreamClient.kt",
        "line": 42,
    }

    markdown = chat_error_job_markdown(
        payload,
        frame=frame,
        source_hint="android/app/src/main/java/com/vessences/android/chat/StreamClient.kt",
        created_date="2026-07-02",
        timestamp="2026-07-02T12:00:00Z",
    )

    assert markdown.startswith("---\nTitle: Audit Android chat_error: SocketException")
    assert "Created: 2026-07-02" in markdown
    assert "- **Timestamp:** 2026-07-02T12:00:00Z" in markdown
    assert "- **Exception:** `java.net.SocketException`" in markdown
    assert f"- **Message:** `{'m' * 400}`" in markdown
    assert "m" * 401 not in markdown
    assert "- **APK:** v1.2.3 (code 44)" in markdown
    assert "- **From voice:** True" in markdown
    assert (
        "- **First app frame:** `com.vessences.android.chat.StreamClient.read` "
        "at `android/app/src/main/java/com/vessences/android/chat/StreamClient.kt:42`"
    ) in markdown
    assert "s" * 1800 in markdown
    assert "s" * 1801 not in markdown
