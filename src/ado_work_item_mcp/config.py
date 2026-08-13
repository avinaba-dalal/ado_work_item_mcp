import json
import os
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ado_work_item_mcp" / "config.json"


class ConfigError(RuntimeError):
    pass


def _load() -> dict:
    path = Path(os.environ.get("ADO_WORK_ITEM_MCP_CONFIG", DEFAULT_CONFIG_PATH))
    if not path.is_file():
        raise ConfigError(
            f"Config file not found at {path}. Create it (see config.example.json), "
            "or point ADO_WORK_ITEM_MCP_CONFIG at your config file."
        )
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file at {path} is not valid JSON: {exc}") from exc


def _require(data: dict, key: str):
    value = data.get(key)
    if not value:
        raise ConfigError(f"Missing required config key: '{key}'")
    return value


_data = _load()

ORG_URL = _require(_data, "org_url")
PAT = _require(_data, "pat")

_projects = _require(_data, "projects")
if not isinstance(_projects, dict) or not all(
    isinstance(teams, list) and teams for teams in _projects.values()
):
    raise ConfigError(
        "'projects' must be an object mapping project name -> non-empty list of team names"
    )
PROJECTS: dict[str, list[str]] = _projects

WORK_ITEM_TYPES = _data.get(
    "work_item_types", ["Product Backlog Item", "Bug", "Tech Debt Item", "Spike", "SSRD"]
)
TASK_TYPE = _data.get("task_type", "Task")
ACCEPTANCE_CRITERIA_FIELD = _data.get(
    "acceptance_criteria_field", "Microsoft.VSTS.Common.AcceptanceCriteria"
)
EFFORT_FIELD = _data.get("effort_field", "Microsoft.VSTS.Scheduling.Effort")
TASK_EFFORT_FIELD = _data.get(
    "task_effort_field", "Microsoft.VSTS.Scheduling.OriginalEstimate"
)
