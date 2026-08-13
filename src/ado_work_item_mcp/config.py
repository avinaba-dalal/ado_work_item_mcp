import os


class ConfigError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


ORG_URL = _require("ADO_ORG_URL")
PROJECT = _require("ADO_PROJECT")
TEAM = _require("ADO_TEAM")
PAT = _require("ADO_PAT")

PBI_TYPES = [
    t.strip()
    for t in os.environ.get(
        "ADO_PBI_TYPES", "Product Backlog Item,Bug,Tech Debt Item,Spike,SSRD"
    ).split(",")
    if t.strip()
]
TASK_TYPE = os.environ.get("ADO_TASK_TYPE", "Task")
ACCEPTANCE_CRITERIA_FIELD = os.environ.get(
    "ADO_ACCEPTANCE_CRITERIA_FIELD", "Microsoft.VSTS.Common.AcceptanceCriteria"
)
EFFORT_FIELD = os.environ.get("ADO_EFFORT_FIELD", "Microsoft.VSTS.Scheduling.Effort")
TASK_EFFORT_FIELD = os.environ.get(
    "ADO_TASK_EFFORT_FIELD", "Microsoft.VSTS.Scheduling.OriginalEstimate"
)
