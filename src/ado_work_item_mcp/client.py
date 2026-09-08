import io

from azure.devops.connection import Connection
from azure.devops.v7_1.work.models import TeamContext
from azure.devops.v7_1.work_item_tracking.models import (
    CommentCreate,
    JsonPatchOperation,
    Wiql,
)
from msrest.authentication import BasicAuthentication

from ado_work_item_mcp import config

_connection = Connection(
    base_url=config.ORG_URL, creds=BasicAuthentication("", config.PAT)
)
_wit_client = _connection.clients.get_work_item_tracking_client()
_work_client = _connection.clients.get_work_client()
_location_client = _connection.clients.get_location_client()

_current_user_cache: str | None = None

HIERARCHY_FORWARD = "System.LinkTypes.Hierarchy-Forward"
HIERARCHY_REVERSE = "System.LinkTypes.Hierarchy-Reverse"
ATTACHED_FILE = "AttachedFile"


def _patch(op: str, path: str, value):
    operation = JsonPatchOperation()
    operation.op = op
    operation.path = path
    operation.value = value
    return operation


def _work_item_url(work_item_id: int) -> str:
    return f"{config.ORG_URL}/_apis/wit/workItems/{work_item_id}"


def _current_user_identity() -> str:
    global _current_user_cache
    if _current_user_cache is None:
        data = _location_client.get_connection_data()
        user = data.authenticated_user
        account = None
        if user and user.properties:
            account = (user.properties.get("Account") or {}).get("$value")
        _current_user_cache = account or (user.provider_display_name if user else None)
        if not _current_user_cache:
            raise RuntimeError("Could not determine the current user's identity from the PAT.")
    return _current_user_cache


def _work_item_context(work_item_id: int) -> dict:
    item = _wit_client.get_work_item(
        work_item_id,
        fields=["System.TeamProject", "System.IterationPath", "System.AreaPath"],
    )
    return {
        "project": item.fields["System.TeamProject"],
        "iteration_path": item.fields.get("System.IterationPath"),
        "area_path": item.fields.get("System.AreaPath"),
    }


def get_current_sprint(project: str, team: str) -> dict:
    team_context = TeamContext(project=project, team=team)
    iterations = _work_client.get_team_iterations(team_context, timeframe="current")
    if not iterations:
        raise RuntimeError(
            f"No current sprint configured for team '{team}' in project '{project}'."
        )
    iteration = iterations[0]
    return {
        "project": project,
        "team": team,
        "id": str(iteration.id),
        "name": iteration.name,
        "path": iteration.path.lstrip("\\"),
        "start_date": str(iteration.attributes.start_date)
        if iteration.attributes
        else None,
        "finish_date": str(iteration.attributes.finish_date)
        if iteration.attributes
        else None,
    }


def get_current_sprints(project: str | None = None, team: str | None = None) -> list[dict]:
    if project or team:
        if not (project and team):
            raise ValueError("Provide both project and team, or neither to list all configured pairs.")
        if project not in config.PROJECTS or team not in config.PROJECTS[project]:
            raise ValueError(f"Team '{team}' is not configured under project '{project}'.")
        return [get_current_sprint(project, team)]

    sprints = []
    for p, teams in config.PROJECTS.items():
        for t in teams:
            try:
                sprints.append(get_current_sprint(p, t))
            except RuntimeError as exc:
                sprints.append({"project": p, "team": t, "error": str(exc)})
    return sprints


def _wiql_escape(value: str) -> str:
    return value.replace("'", "''")


def list_my_work_items(iteration_paths: list[str] | None = None) -> list[dict]:
    types = ", ".join(f"'{_wiql_escape(t)}'" for t in config.WORK_ITEM_TYPES)
    projects = ", ".join(f"'{_wiql_escape(p)}'" for p in config.PROJECTS)
    conditions = [
        f"[System.TeamProject] IN ({projects})",
        f"[System.WorkItemType] IN ({types})",
        "[System.AssignedTo] = @Me",
        "[System.State] <> 'Removed'",
    ]
    if iteration_paths:
        paths = ", ".join(f"'{_wiql_escape(p)}'" for p in iteration_paths)
        conditions.append(f"[System.IterationPath] IN ({paths})")
    where_clause = "\n      AND ".join(conditions)
    query = f"""
    SELECT [System.Id] FROM WorkItems
    WHERE {where_clause}
    ORDER BY [System.Id]
    """
    result = _wit_client.query_by_wiql(Wiql(query=query))
    ids = [ref.id for ref in result.work_items]
    if not ids:
        return []
    items = _wit_client.get_work_items(
        ids,
        fields=[
            "System.Title",
            "System.State",
            "System.WorkItemType",
            "System.TeamProject",
            "System.IterationPath",
        ],
    )
    return [
        {
            "id": item.id,
            "title": item.fields.get("System.Title"),
            "state": item.fields.get("System.State"),
            "type": item.fields.get("System.WorkItemType"),
            "project": item.fields.get("System.TeamProject"),
            "iteration_path": (item.fields.get("System.IterationPath") or "").lstrip("\\") or None,
        }
        for item in items
    ]


def get_iteration_finish_dates() -> dict[str, object]:
    """Map every configured project/team's iteration path -> finish_date (datetime or None),
    across all iterations (past, current, future) - not just the current sprint."""
    dates: dict[str, object] = {}
    for project, teams in config.PROJECTS.items():
        for team in teams:
            team_context = TeamContext(project=project, team=team)
            try:
                iterations = _work_client.get_team_iterations(team_context)
            except Exception:
                continue
            for iteration in iterations:
                path = iteration.path.lstrip("\\")
                finish = iteration.attributes.finish_date if iteration.attributes else None
                dates[path] = finish
    return dates


def _child_task_ids(work_item_id: int) -> list[int]:
    item = _wit_client.get_work_item(work_item_id, expand="Relations")
    if not item.relations:
        return []
    ids = []
    for relation in item.relations:
        if relation.rel == HIERARCHY_FORWARD:
            ids.append(int(relation.url.rstrip("/").split("/")[-1]))
    return ids


def list_tasks(work_item_id: int) -> list[dict]:
    child_ids = _child_task_ids(work_item_id)
    if not child_ids:
        return []
    items = _wit_client.get_work_items(
        child_ids,
        fields=["System.Title", "System.State", "System.WorkItemType", config.TASK_EFFORT_FIELD],
    )
    return [
        {
            "id": item.id,
            "title": item.fields.get("System.Title"),
            "state": item.fields.get("System.State"),
            "effort": item.fields.get(config.TASK_EFFORT_FIELD),
        }
        for item in items
        if item.fields.get("System.WorkItemType") == config.TASK_TYPE
    ]


def get_work_item_detail(work_item_id: int) -> dict:
    item = _wit_client.get_work_item(work_item_id, expand="Fields")
    fields = item.fields
    return {
        "id": item.id,
        "project": fields.get("System.TeamProject"),
        "title": fields.get("System.Title"),
        "state": fields.get("System.State"),
        "description": fields.get("System.Description", ""),
        "acceptance_criteria": fields.get(config.ACCEPTANCE_CRITERIA_FIELD, ""),
        "effort": fields.get(config.EFFORT_FIELD, ""),
        "child_tasks": list_tasks(work_item_id),
    }


def set_work_item_state(work_item_id: int, state: str) -> dict:
    document = [_patch("add", "/fields/System.State", state)]
    item = _wit_client.update_work_item(document, work_item_id)
    return {"id": item.id, "state": item.fields.get("System.State")}


def add_work_item_comment(work_item_id: int, text: str) -> dict:
    project = _work_item_context(work_item_id)["project"]
    request = CommentCreate(text=text)
    comment = _wit_client.add_comment(request, project, work_item_id)
    return {"id": comment.id, "text": comment.text}


def attach_plan(work_item_id: int, content: str, filename: str = "PLAN.md") -> dict:
    stream = io.BytesIO(content.encode("utf-8"))
    attachment = _wit_client.create_attachment(upload_stream=stream, file_name=filename)
    document = [
        _patch(
            "add",
            "/relations/-",
            {
                "rel": ATTACHED_FILE,
                "url": attachment.url,
                "attributes": {"comment": f"Attached {filename}"},
            },
        )
    ]
    _wit_client.update_work_item(document, work_item_id)
    return {"id": attachment.id, "url": attachment.url, "filename": filename}


def _assigned_to(fields: dict) -> str | None:
    value = fields.get("System.AssignedTo")
    if isinstance(value, dict):
        return value.get("displayName") or value.get("uniqueName")
    return value


def create_task(
    work_item_id: int,
    title: str,
    description: str = "",
    effort: float | None = None,
    assigned_to: str | None = None,
) -> dict:
    parent = _work_item_context(work_item_id)
    document = [
        _patch("add", "/fields/System.Title", title),
        _patch(
            "add",
            "/relations/-",
            {"rel": HIERARCHY_REVERSE, "url": _work_item_url(work_item_id)},
        ),
    ]
    if parent["iteration_path"]:
        document.append(_patch("add", "/fields/System.IterationPath", parent["iteration_path"]))
    if parent["area_path"]:
        document.append(_patch("add", "/fields/System.AreaPath", parent["area_path"]))
    if description:
        document.append(_patch("add", "/fields/System.Description", description))
        document.append(_patch("add", "/multilineFieldsFormat/System.Description", "Markdown"))
    if effort is not None:
        document.append(_patch("add", f"/fields/{config.TASK_EFFORT_FIELD}", effort))
    document.append(
        _patch("add", "/fields/System.AssignedTo", assigned_to or _current_user_identity())
    )
    item = _wit_client.create_work_item(document, project=parent["project"], type=config.TASK_TYPE)
    return {
        "id": item.id,
        "title": item.fields.get("System.Title"),
        "state": item.fields.get("System.State"),
        "assigned_to": _assigned_to(item.fields),
    }


def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    state: str | None = None,
    effort: float | None = None,
    assigned_to: str | None = None,
) -> dict:
    document = []
    if title is not None:
        document.append(_patch("add", "/fields/System.Title", title))
    if description is not None:
        document.append(_patch("add", "/fields/System.Description", description))
        document.append(_patch("add", "/multilineFieldsFormat/System.Description", "Markdown"))
    if state is not None:
        document.append(_patch("add", "/fields/System.State", state))
    if effort is not None:
        document.append(_patch("add", f"/fields/{config.TASK_EFFORT_FIELD}", effort))
    if assigned_to is not None:
        document.append(_patch("add", "/fields/System.AssignedTo", assigned_to))
    if not document:
        raise ValueError(
            "update_task requires at least one of title/description/state/effort/assigned_to"
        )
    item = _wit_client.update_work_item(document, task_id)
    return {
        "id": item.id,
        "title": item.fields.get("System.Title"),
        "state": item.fields.get("System.State"),
        "assigned_to": _assigned_to(item.fields),
    }


def delete_task(task_id: int) -> dict:
    _wit_client.delete_work_item(task_id)
    return {"id": task_id, "deleted": True}
