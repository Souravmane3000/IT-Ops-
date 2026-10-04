from backend.browser.portal_actions import _is_ui_granted


def test_not_granted_is_not_treated_as_granted():
    assert _is_ui_granted("Not granted") is False
    assert _is_ui_granted("not granted") is False
    assert _is_ui_granted("Granted") is True
    assert _is_ui_granted("granted") is True
    assert _is_ui_granted("  GRANTED  ") is True
