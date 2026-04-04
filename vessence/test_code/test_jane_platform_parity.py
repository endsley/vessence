from scripts import check_jane_platform_parity as parity


def test_classify_paths_detects_web_only_changes():
    web, android = parity.classify_paths([
        "vessence/vault_web/templates/jane.html",
        "vessence/jane_web/main.py",
    ])
    assert web is True
    assert android is False


def test_classify_paths_detects_android_only_changes():
    web, android = parity.classify_paths([
        "vessence/android/app/src/main/java/com/vessences/android/ui/chat/ChatScreen.kt",
    ])
    assert web is False
    assert android is True


def test_parity_message_is_none_when_both_platforms_changed():
    assert parity.parity_message(True, True) is None
