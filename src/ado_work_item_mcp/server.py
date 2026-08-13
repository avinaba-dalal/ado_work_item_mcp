from mcp.server import MCPServer

from ado_work_item_mcp import client

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
    work_item_id: int, title: str, description: str = "", effort: float | None = None
) -> dict:
    """Create a new child task under a work item. `effort` is a human-estimate (e.g. hours)."""
    return client.create_task(work_item_id, title, description, effort=effort)


@mcp.tool()
def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    state: str | None = None,
    effort: float | None = None,
) -> dict:
    """Update a task's title, description, state, and/or effort. Only provided fields are changed."""
    return client.update_task(
        task_id, title=title, description=description, state=state, effort=effort
    )


@mcp.tool()
def delete_task(task_id: int) -> dict:
    """Delete a task (soft delete to the recycle bin)."""
    return client.delete_task(task_id)


@mcp.tool()
def list_tasks(work_item_id: int) -> list[dict]:
    """List the child tasks of a work item: id, title, state."""
    return client.list_tasks(work_item_id)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
