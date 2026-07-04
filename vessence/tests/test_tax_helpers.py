from jane_web.tax_helpers import (
    is_safe_tax_form_name,
    latest_tax_form_file,
    tax_interview_answer_args,
    tax_output_dir,
    tax_result_path,
    tax_tool_command,
    tax_tool_result_payload,
    tax_upload_document_args,
    tax_upload_path,
    tax_uploads_dir,
)


def test_safe_tax_form_name_uses_existing_identifier_rule():
    assert is_safe_tax_form_name("schedule_c")
    assert is_safe_tax_form_name("Form-1040")
    assert not is_safe_tax_form_name("../1040")
    assert not is_safe_tax_form_name("form.1040")


def test_tax_interview_answer_args_preserves_defaults():
    assert tax_interview_answer_args({}) == {"step_id": "filing_status", "user_response": {}}
    assert tax_interview_answer_args({"step_id": "income", "response": {"w2": True}}) == {
        "step_id": "income",
        "user_response": {"w2": True},
    }


def test_tax_tool_command_serializes_non_empty_args_only():
    assert tax_tool_command("/python", "/tools.py", "calculate_tax") == [
        "/python",
        "/tools.py",
        "calculate_tax",
    ]
    assert tax_tool_command("/python", "/tools.py", "interview_step", {"step_id": "filing_status"}) == [
        "/python",
        "/tools.py",
        "interview_step",
        '{"step_id": "filing_status"}',
    ]


def test_tax_tool_result_payload_preserves_error_json_and_plain_stdout_shapes():
    assert tax_tool_result_payload(2, "", "x" * 600) == {
        "status": "error",
        "message": "x" * 500,
    }
    assert tax_tool_result_payload(0, '{"status": "ok", "value": 3}', "") == {
        "status": "ok",
        "value": 3,
    }
    assert tax_tool_result_payload(0, "  generated file  \n", "") == {
        "status": "ok",
        "output": "generated file",
    }


def test_tax_paths_match_existing_route_layout():
    root = "/essences/tax_accountant_2025"

    assert tax_output_dir(root) == "/essences/tax_accountant_2025/working_files/output"
    assert tax_result_path(root) == "/essences/tax_accountant_2025/working_files/calculations/tax_result.json"
    assert tax_uploads_dir(root) == "/essences/tax_accountant_2025/user_data/uploads"
    assert tax_upload_path("/uploads", "../w2.pdf") == "/uploads/w2.pdf"
    assert tax_upload_path("/uploads", None) == "/uploads/upload"
    assert tax_upload_document_args("/uploads/w2.pdf", "w2") == {
        "file_path": "/uploads/w2.pdf",
        "doc_type": "w2",
    }


def test_latest_tax_form_file_uses_reverse_sorted_prefix_match():
    files = [
        "1040_20260324.pdf",
        "1040_20260415.pdf",
        "schedule_c_20260415.pdf",
    ]

    assert latest_tax_form_file(
        "/output",
        "1040",
        is_dir=lambda path: path == "/output",
        list_dir=lambda path: files,
    ) == ("/output/1040_20260415.pdf", "1040_20260415.pdf")
    assert latest_tax_form_file(
        "/missing",
        "1040",
        is_dir=lambda path: False,
        list_dir=lambda path: files,
    ) is None
    assert latest_tax_form_file(
        "/output",
        "schedule_d",
        is_dir=lambda path: True,
        list_dir=lambda path: files,
    ) is None
