from datetime import datetime, timedelta, timezone

from ado_work_item_mcp.roi import compute_roi

CAPS = {"plan": 20, "code": 30, "pr": 10}
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _events(*rows: tuple[str, str | None, float]) -> list[dict]:
    """Build an event list from (event, phase, minutes_since_previous) rows."""
    events = []
    ts = T0
    for event, phase, offset_minutes in rows:
        ts = ts + timedelta(minutes=offset_minutes)
        events.append({"event": event, "phase": phase, "ts": ts})
    return events


def test_single_round_per_phase():
    events = _events(
        ("run_started", None, 0),
        ("awaiting_human", "plan", 5),
        ("human_responded", "plan", 5),
        ("awaiting_human", "code", 30),
        ("human_responded", "code", 10),
        ("awaiting_human", "pr", 5),
        ("human_responded", "pr", 5),
        ("run_finished", None, 1),
    )

    report = compute_roi(events, task_effort_total=10, caps=CAPS)

    assert report["complete"] is True
    assert report["human_review_minutes"] == {"plan": 5, "code": 10, "pr": 5, "total": 20}
    assert report["idle_excess_minutes"] == 0
    assert report["claude_active_minutes"] == 41
    assert report["time_saved_minutes"] == 539
    assert report["time_saved_hours"] == 8.98


def test_multi_round_revision_loop():
    events = _events(
        ("run_started", None, 0),
        ("awaiting_human", "plan", 2),
        ("human_responded", "plan", 3),
        ("awaiting_human", "code", 5),
        ("human_responded", "code", 4),  # round 1: requests changes
        ("awaiting_human", "code", 6),  # round 2: reworked, re-presented
        ("human_responded", "code", 2),  # approved
        ("awaiting_human", "pr", 3),
        ("human_responded", "pr", 1),
        ("run_finished", None, 1),
    )

    report = compute_roi(events, task_effort_total=5, caps=CAPS)

    assert report["complete"] is True
    assert report["human_review_minutes"] == {"plan": 3, "code": 6, "pr": 1, "total": 10}
    assert report["idle_excess_minutes"] == 0
    assert report["claude_active_minutes"] == 17
    assert report["time_saved_minutes"] == 273
    assert report["time_saved_hours"] == 4.55


def test_gap_beyond_cap_is_excluded_as_idle():
    events = _events(
        ("run_started", None, 0),
        ("awaiting_human", "plan", 1),
        ("human_responded", "plan", 50),  # raw gap 50 > 20-minute cap
        ("run_finished", None, 1),
    )

    report = compute_roi(events, task_effort_total=1, caps=CAPS)

    assert report["human_review_minutes"]["plan"] == 20
    assert report["idle_excess_minutes"] == 30
    assert report["claude_active_minutes"] == 2
    assert report["time_saved_minutes"] == 38


def test_incomplete_run_has_no_time_saved():
    events = _events(
        ("run_started", None, 0),
        ("awaiting_human", "plan", 1),
    )

    report = compute_roi(events, task_effort_total=10, caps=CAPS)

    assert report["complete"] is False
    assert report["time_saved_minutes"] is None
    assert report["time_saved_hours"] is None
    assert report["human_review_minutes"]["total"] == 0


def test_no_run_started_returns_zeroed_report():
    report = compute_roi([], task_effort_total=10, caps=CAPS)

    assert report["complete"] is False
    assert report["claude_active_minutes"] == 0.0
    assert report["human_review_minutes"] == {"plan": 0.0, "code": 0.0, "pr": 0.0, "total": 0.0}
    assert report["time_saved_minutes"] is None
