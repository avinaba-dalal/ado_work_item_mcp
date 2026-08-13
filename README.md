# Azure DevOps Work Item MCP

An [MCP](https://modelcontextprotocol.io/) server for working sprint items (PBI, Bug, Tech Debt Item, Spike, SSRD, etc) assigned to you in Azure DevOps — read state/description/acceptance criteria, then write back a state change, a comment, an implementation plan attachment, and full CRUD on child tasks.

## How it works

```
MCP Client (Claude Code)
        │
        │  MCP tool calls
        ▼
  MCPServer        (src/ado_work_item_mcp/server.py)
        │
        ▼
  ADO client layer (src/ado_work_item_mcp/client.py)
        │
        ▼
  azure-devops SDK  →  Azure DevOps REST API
```

## Tools

| Tool | Description |
|---|---|
| `get_current_sprint()` | Current iteration for the configured team: id, name, path, dates |
| `list_my_work_items(sprints?)` | Work items assigned to you: id, title, state, type. Filters to the given sprint iteration path(s) if supplied, otherwise returns items across all sprints |
| `get_work_item(work_item_id)` | Title, state, description, acceptance criteria, effort, and child tasks |
| `set_work_item_state(work_item_id, state)` | Change a work item's state |
| `add_work_item_comment(work_item_id, text)` | Add a comment to a work item |
| `attach_plan(work_item_id, content, filename?)` | Attach a markdown plan (default `PLAN.md`) to a work item |
| `create_task(work_item_id, title, description?, effort?)` | Create a child task under a work item |
| `update_task(task_id, title?, description?, state?, effort?)` | Update a task's fields |
| `delete_task(task_id)` | Soft-delete a task (recycle bin) |
| `list_tasks(work_item_id)` | List a work item's child tasks: id, title, state |

## Installation

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

All settings are environment variables, passed via the server's registration (see below):

| Variable | Required | Default | Description |
|---|---|---|---|
| `ADO_ORG_URL` | yes | — | e.g. `https://dev.azure.com/your-org` |
| `ADO_PROJECT` | yes | — | Project name |
| `ADO_TEAM` | yes | — | Team name (used for current-sprint lookup) |
| `ADO_PAT` | yes | — | Personal Access Token — needs Work Items (Read & Write) scope |
| `ADO_PBI_TYPES` | no | `Product Backlog Item,Bug,Tech Debt Item,Spike,SSRD` | Comma-separated work item type names to include when listing "my" sprint items |
| `ADO_TASK_TYPE` | no | `Task` | Work item type name for child tasks |
| `ADO_ACCEPTANCE_CRITERIA_FIELD` | no | `Microsoft.VSTS.Common.AcceptanceCriteria` | Field reference name for acceptance criteria |
| `ADO_EFFORT_FIELD` | no | `Microsoft.VSTS.Scheduling.Effort` | Field reference name for PBI effort |
| `ADO_TASK_EFFORT_FIELD` | no | `Microsoft.VSTS.Scheduling.OriginalEstimate` | Field reference name for task effort |

### Registering the server

This server is meant to be usable from *any* Claude Code session, in any directory — not just when working inside this repo. Register it once, globally, via the CLI (`--scope user`), which stores the registration in `~/.claude.json` and makes the tools available regardless of which directory a Claude Code session is rooted in:

```bash
claude mcp add ado_work_item_mcp --scope user \
  -e ADO_ORG_URL="https://dev.azure.com/your-org" \
  -e ADO_PROJECT="your-project" \
  -e ADO_TEAM="your-team" \
  -e ADO_PAT="your-personal-access-token" \
  -- /path/to/ado_work_item_mcp/.venv/bin/python -m ado_work_item_mcp.server
```

Restart Claude Code afterwards so the new session picks up the registration. Run `claude mcp list` to confirm it's registered, and `claude mcp remove ado_work_item_mcp` to undo.

### Example workflow command

[`commands/implement_work_item.md`](commands/implement_work_item.md) is a starting-point Claude Code slash command that drives a full work-item implementation using these tools (grooming/state checks, plan-approval gate, branch creation, task-tracked implementation). Copy it to `~/.claude/commands/` to use it as `/implement_work_item <work-item-id>`, adjusting the branch naming convention to your own.

## Manual testing

Before wiring into Claude Code, exercise the tools with the MCP inspector:

```bash
mcp dev src/ado_work_item_mcp/server.py
```

## Project structure

```
commands/
└── implement_work_item.md   # example Claude Code slash command
src/ado_work_item_mcp/
├── config.py   # env var loading
├── client.py   # azure-devops SDK calls
└── server.py   # MCP tool definitions (FastMCP)
```

## Dependencies

- [`mcp[cli]`](https://github.com/modelcontextprotocol/python-sdk) — MCP server framework
- [`azure-devops`](https://github.com/microsoft/azure-devops-python-api) — Azure DevOps REST API wrapper
