from jane_web.contact_search import aggregate_contact_rows


def test_aggregate_contact_rows_merges_by_contact_id_and_dedupes_values():
    rows = [
        {
            "display_name": "Mia W",
            "phone_number": "+155501",
            "email": "mia@example.com",
            "is_primary": 1,
            "contact_id": "c1",
        },
        {
            "display_name": "Mia Work",
            "phone_number": "+155501",
            "email": "mia.work@example.com",
            "is_primary": 0,
            "contact_id": "c1",
        },
        {
            "display_name": "Mia W",
            "phone_number": "+155502",
            "email": "mia@example.com",
            "is_primary": 0,
            "contact_id": "c1",
        },
    ]

    assert aggregate_contact_rows(rows) == [
        {
            "display_name": "Mia W",
            "phones": ["+155501", "+155502"],
            "emails": ["mia@example.com", "mia.work@example.com"],
        }
    ]


def test_aggregate_contact_rows_falls_back_to_display_name_without_contact_id():
    rows = [
        {
            "display_name": "Home",
            "phone_number": "+155501",
            "email": "",
            "is_primary": 1,
            "contact_id": "",
        },
        {
            "display_name": "Home",
            "phone_number": "",
            "email": "home@example.com",
            "is_primary": 0,
            "contact_id": None,
        },
    ]

    assert aggregate_contact_rows(rows) == [
        {"display_name": "Home", "phones": ["+155501"], "emails": ["home@example.com"]}
    ]


def test_aggregate_contact_rows_preserves_person_order():
    rows = [
        {"display_name": "B", "phone_number": "+2", "email": "", "is_primary": 1, "contact_id": "b"},
        {"display_name": "A", "phone_number": "+1", "email": "", "is_primary": 1, "contact_id": "a"},
    ]

    assert [person["display_name"] for person in aggregate_contact_rows(rows)] == ["B", "A"]
