from jane_web.jane_v2.classes.timer import responses
from jane_web.jane_v2.classes.timer.tool_markers import (
    timer_cancel_marker,
    timer_delete_marker,
    timer_list_marker,
    timer_set_marker,
)


def test_timer_marker_helpers_preserve_compact_client_tool_shapes():
    assert timer_set_marker(300000, "pasta") == (
        '[[CLIENT_TOOL:timer.set:{"duration_ms":300000,"label":"pasta"}]]'
    )
    assert timer_list_marker() == "[[CLIENT_TOOL:timer.list:{}]]"
    assert timer_cancel_marker() == "[[CLIENT_TOOL:timer.cancel:{}]]"
    assert timer_delete_marker({"label": "pasta"}) == (
        '[[CLIENT_TOOL:timer.delete:{"label":"pasta"}]]'
    )


def test_timer_responses_use_marker_helpers():
    assert responses._timer_set_marker is timer_set_marker
    assert responses._timer_list_marker is timer_list_marker
    assert responses._timer_cancel_marker is timer_cancel_marker
    assert responses._timer_delete_marker is timer_delete_marker
