from mcp.server import MCPServer

from ado_work_item_mcp import client, roi

mcp = MCPServer("ado_work_item_mcp")


@mcp.tool()
def get_current_sprints(project: str | None = None, team: str | None = None) -> list[dict]:
    """Get the current sprint(s): id, name, path, start/finish dates.

    Pass both `project` and `team` to get a single configured pair's current
    sprint. Omit both to get the current sprint for every configured
    project/team pair (a pair with no active sprint is returned with an
    `error` field instead of failing the whole call)."""
    return client.get_current_sprints(project, team)


@mcp.tool()
def list_my_work_items(sprints: list[str] | None = None) -> list[dict]:
    """List work items assigned to me (PBI, Bug, Tech Debt Item, Spike, SSRD, etc), across all configured projects.

    `sprints` is an optional list of sprint iteration paths to filter by (pass
    multiple to query several sprints at once) — use get_current_sprints()'s
    `path` field to find one. If omitted, returns matching items across all
    sprints, not just the current one."""
    return client.list_my_work_items(sprints)


@mcp.tool()
def get_work_item(work_item_id: int) -> dict:
    """Get a work item's title, state, description, acceptance criteria, effort, and its child tasks."""
    return client.get_work_item_detail(work_item_id)


@mcp.tool()
def set_work_item_state(work_item_id: int, state: str) -> dict:
    """Change a work item's state (e.g. 'Committed', 'Done'). Azure DevOps rejects invalid transitions."""
    return client.set_work_item_state(work_item_id, state)


@mcp.tool()
def add_work_item_comment(work_item_id: int, text: str) -> dict:
    """Add a comment to a work item."""
    return client.add_work_item_comment(work_item_id, text)


@mcp.tool()
def attach_plan(work_item_id: int, content: str, filename: str = "PLAN.md") -> dict:
    """Attach a markdown implementation plan (or other text file) to a work item."""
    return client.attach_plan(work_item_id, content, filename)


@mcp.tool()
def create_task(
    work_item_id: int,
    title: str,
    description: str = "",
    effort: float | None = None,
    assigned_to: str | None = None,
) -> dict:
    """Create a new child task under a work item. `effort` is a human-estimate (e.g. hours).

    `assigned_to` is the owner's email or display name — omit to assign it to
    whoever the server's PAT belongs to (you)."""
    return client.create_task(
        work_item_id, title, description, effort=effort, assigned_to=assigned_to
    )


@mcp.tool()
def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    state: str | None = None,
    effort: float | None = None,
    assigned_to: str | None = None,
) -> dict:
    """Update a task's title, description, state, effort, and/or owner. Only provided fields are changed."""
    return client.update_task(
        task_id,
        title=title,
        description=description,
        state=state,
        effort=effort,
        assigned_to=assigned_to,
    )


@mcp.tool()
def delete_task(task_id: int) -> dict:
    """Delete a task (soft delete to the recycle bin)."""
    return client.delete_task(task_id)


@mcp.tool()
def list_tasks(work_item_id: int) -> list[dict]:
    """List the child tasks of a work item: id, title, state."""
    return client.list_tasks(work_item_id)


@mcp.tool()
def log_roi_checkpoint(work_item_id: int, event: str, phase: str | None = None) -> dict:
    """Log a timestamped ROI checkpoint for a work item's implement_work_item run.

    Raises `ValueError` if `event` isn't one of run_started/awaiting_human/
    human_responded/run_finished, or if `phase` is missing/invalid for a
    phased event (awaiting_human/human_responded need one of plan/code/pr;
    run_started/run_finished must not have a phase).

    When `event="run_finished"`, this also computes the final ROI report and
    attaches it to the work item as `ROI_REPORT.json` — best-effort, so a
    failure there is reported via `report_attached`/`attach_error` in the
    return value rather than raised.
    """
    return roi.append_checkpoint(work_item_id, event, phase)


@mcp.tool()
def get_roi_report(work_item_id: int) -> dict:
    """Get the ROI report (time saved vs. doing it manually) for one work item.

    Built from that work item's logged checkpoints and its child tasks'
    effort estimates. Returns `complete: False` and `time_saved_minutes:
    None` if the run hasn't logged a `run_finished` checkpoint yet."""
    return roi.build_roi_report(work_item_id)


@mcp.tool()
def list_roi_reports() -> list[dict]:
    """List ROI reports for every work item that has at least one logged checkpoint.

    Returns an empty list if nothing has been logged yet."""
    return roi.list_roi_reports()


def main():
    mcp.run()


if __name__ == "__main__":
    main()
