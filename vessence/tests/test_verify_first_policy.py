from jane_web.verify_first_policy import needs_verification
from jane_web.jane_v2.pipeline import _evidence_correction_for_stream


def test_write_access_verification_requires_tool_evidence():
    assert needs_verification("can you verify that you have right access to the education project")
    assert needs_verification("check write access for /home/chieh/code/chieh_class_v2")
    assert needs_verification("test read and write access to the waterlily project")


def test_non_system_verify_phrase_does_not_trigger():
    assert not needs_verification("can you verify that dinner is at seven")


def test_stream_correction_when_required_tool_evidence_missing():
    correction = _evidence_correction_for_stream(
        {
            "flagged": True,
            "requires_code": True,
            "tool_calls": 0,
            "requires_memory": False,
        }
    )

    assert "code/log tool result" in correction
    assert "should not claim it is verified" in correction
