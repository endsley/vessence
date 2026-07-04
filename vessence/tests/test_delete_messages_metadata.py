from jane_web.jane_v2.classes.delete_messages import metadata


def test_delete_messages_instruction_lines_preserve_tool_and_confirmation_contract() -> None:
    text = "\n".join(metadata._delete_messages_instruction_lines())

    assert '[[CLIENT_TOOL:messages.dismiss:{"addresses":["<num1>","<num2>"]}]]' in text
    assert "Confirm BEFORE deleting if the user was vague" in text
    assert "Skip confirmation only when the user was explicit" in text
    assert "DO NOT delete contact messages without explicit confirmation" in text
    assert "Don't quote the deleted bodies" in text
