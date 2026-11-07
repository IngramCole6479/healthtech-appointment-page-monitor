from src.page_monitor import decide


def test_changed_appointment_page_requires_one_review_alert() -> None:
    first = decide(None, "Bring an ID to your appointment.")
    second = decide(first.current_fingerprint, "Bring an ID and arrive 15 minutes early.")
    stable = decide(second.current_fingerprint, "Bring an ID and arrive 15 minutes early.")

    assert first.changed is False
    assert second.changed is True
    assert stable.changed is False
    assert second.previous_fingerprint == first.current_fingerprint
