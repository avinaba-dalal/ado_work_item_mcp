import json
from datetime import datetime, timezone

from ado_work_item_mcp import client, config

VALID_EVENTS = {"run_started", "awaiting_human", "human_responded", "run_finished"}
VALID_PHASES = {"plan", "code", "pr"}
PHASED_EVENTS = {"awaiting_human", "human_responded"}


def append_checkpoint(work_item_id: int, event: str, phase: str | None = None) -> dict:
    """Log a timestamped ROI checkpoint for a work item's implement_work_item run.

    Raises `ValueError` if `event` isn't one of run_started/awaiting_human/
    human_responded/run_finished, or if `phase` is missing/invalid for a
    phased event (awaiting_human/human_responded need one of plan/code/pr;
    run_started/run_finished must not have a phase). Appends one JSON line to
    the local checkpoint log (`config.CHECKPOINT_LOG_PATH`), creating its
    parent directory if needed.

    When `event == "run_finished"`, also best-effort computes the final ROI
    report and attaches it to the work item as `ROI_REPORT.json` (via
    `client.attach_plan`) — a failure here is caught and reported through
    `report_attached`/`attach_error` rather than raised, since by this point
    the actual implementation work is already done and shouldn't be blocked.

    Returns a dict with `logged: True` and, for `run_finished`, the computed
    `report` plus `report_attached` (bool) and `attach_error` (str, if any).
    """
    if event not in VALID_EVENTS:
        raise ValueError(f"event must be one of {sorted(VALID_EVENTS)}, got {event!r}")
    if event in PHASED_EVENTS:
        if phase not in VALID_PHASES:
            raise ValueError(f"phase must be one of {sorted(VALID_PHASES)} for event {event!r}")
    elif phase is not None:
        raise ValueError(f"event {event!r} must not have a phase")

    entry = {
        "work_item_id": work_item_id,
        "event": event,
        "phase": phase,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    config.CHECKPOINT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with config.CHECKPOINT_LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")

    result = {"logged": True}
    if event == "run_finished":
        try:
            report = build_roi_report(work_item_id)
            client.attach_plan(work_item_id, json.dumps(report, indent=2), "ROI_REPORT.json")
            result["report"] = report
            result["report_attached"] = True
        except Exception as exc:
            result["report_attached"] = False
            result["attach_error"] = str(exc)
    return result


def _read_events(work_item_id: int) -> list[dict]:
    if not config.CHECKPOINT_LOG_PATH.is_file():
        return []
    events = []
    for line in config.CHECKPOINT_LOG_PATH.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("work_item_id") == work_item_id:
            entry["ts"] = datetime.fromisoformat(entry["ts"])
            events.append(entry)
    return sorted(events, key=lambda e: e["ts"])


def compute_roi(events: list[dict], task_effort_total: float, caps: dict[str, float]) -> dict:
    """Compute the ROI report from a work item's checkpoint events and task-effort baseline.

    Does not raise for malformed/incomplete input: an event list with no
    `run_started` returns a zeroed-out report with `complete: False`; one
    with no `run_finished` returns `complete: False` and `time_saved_minutes:
    None`, using the last event as a provisional cutoff for the time-in-
    progress fields. `events` need not be pre-sorted. Each event dict must
    have `event`, an optional `phase`, and a timezone-aware `ts` (datetime).

    Returns a dict with `human_review_minutes` (per phase + `total`, each
    capped per `caps[phase]`), `idle_excess_minutes` (review gaps beyond the
    cap — excluded from both human and Claude time), `claude_active_minutes`,
    `task_effort_total_hours`, `time_saved_minutes`/`time_saved_hours`
    (`None` while incomplete), and `complete`.
    """
    events = sorted(events, key=lambda e: e["ts"])

    run_started = next((e for e in events if e["event"] == "run_started"), None)
    run_finished = next((e for e in events if e["event"] == "run_finished"), None)
    complete = run_finished is not None

    if run_started is None:
        return {
            "complete": False,
            "task_effort_total_hours": task_effort_total,
            "claude_active_minutes": 0.0,
            "human_review_minutes": {"plan": 0.0, "code": 0.0, "pr": 0.0, "total": 0.0},
            "idle_excess_minutes": 0.0,
            "time_saved_minutes": None,
            "time_saved_hours": None,
        }

    end_ts = run_finished["ts"] if run_finished else events[-1]["ts"]
    total_span_minutes = (end_ts - run_started["ts"]).total_seconds() / 60

    human_review = {"plan": 0.0, "code": 0.0, "pr": 0.0}
    raw_gaps_total = 0.0
    pending_awaiting: dict[str, datetime] = {}

    for event in events:
        phase = event.get("phase")
        if event["event"] == "awaiting_human" and phase in VALID_PHASES:
            pending_awaiting[phase] = event["ts"]
        elif event["event"] == "human_responded" and phase in VALID_PHASES:
            start = pending_awaiting.pop(phase, None)
            if start is None:
                continue
            raw_gap_minutes = (event["ts"] - start).total_seconds() / 60
            raw_gaps_total += raw_gap_minutes
            human_review[phase] += min(raw_gap_minutes, caps.get(phase, raw_gap_minutes))

    human_review_total = sum(human_review.values())
    idle_excess = raw_gaps_total - human_review_total
    claude_active = total_span_minutes - raw_gaps_total

    result = {
        "complete": complete,
        "task_effort_total_hours": task_effort_total,
        "claude_active_minutes": round(claude_active, 2),
        "human_review_minutes": {
            **{phase: round(minutes, 2) for phase, minutes in human_review.items()},
            "total": round(human_review_total, 2),
        },
        "idle_excess_minutes": round(idle_excess, 2),
    }

    if complete:
        time_saved_minutes = task_effort_total * 60 - (human_review_total + claude_active)
        result["time_saved_minutes"] = round(time_saved_minutes, 2)
        result["time_saved_hours"] = round(time_saved_minutes / 60, 2)
    else:
        result["time_saved_minutes"] = None
        result["time_saved_hours"] = None

    return result


def build_roi_report(work_item_id: int) -> dict:
    """Build the ROI report for one work item from its logged checkpoints and child-task effort.

    Does not raise for a work item with no logged events or no child tasks —
    both degrade to a zeroed-out/`complete: False` report via `compute_roi`
    rather than erroring. Returns `compute_roi`'s output augmented with
    `work_item_id`.
    """
    events = _read_events(work_item_id)
    tasks = client.list_tasks(work_item_id)
    task_effort_total = sum(t["effort"] for t in tasks if t.get("effort") is not None)
    report = compute_roi(events, task_effort_total, config.ROI_TIME_CAPS)
    report["work_item_id"] = work_item_id
    return report


def list_roi_reports() -> list[dict]:
    """List ROI reports for every work item that has at least one logged checkpoint.

    Returns an empty list if the checkpoint log doesn't exist yet or is
    empty. Each entry is `build_roi_report`'s output for that work item id.
    """
    if not config.CHECKPOINT_LOG_PATH.is_file():
        return []
    work_item_ids = set()
    for line in config.CHECKPOINT_LOG_PATH.read_text().splitlines():
        if line.strip():
            work_item_ids.add(json.loads(line)["work_item_id"])
    return [build_roi_report(work_item_id) for work_item_id in sorted(work_item_ids)]
