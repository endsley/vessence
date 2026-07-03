from jane_web.sms_classification import classify_synced_message


def test_contact_messages_are_personal_regardless_of_body_keywords():
    assert classify_synced_message("Reply STOP for a free deal", is_contact=True) == "personal"


def test_reminder_keywords_take_precedence_over_spam_and_notification_keywords():
    body = "Payment due today for your shipped promo order"

    assert classify_synced_message(body, is_contact=False) == "reminder"


def test_spam_keywords_take_precedence_over_notification_keywords():
    body = "Flash sale on your package tracking updates"

    assert classify_synced_message(body, is_contact=False) == "spam"


def test_notification_and_unknown_messages():
    assert classify_synced_message("Your package has shipped", is_contact=False) == "notification"
    assert classify_synced_message("See you later", is_contact=False) == "unknown"
