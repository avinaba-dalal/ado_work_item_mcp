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
| `get_current_sprints(project?, team?)` | Current iteration(s): id, name, path, dates. Give both `project` and `team` for a single pair, or omit both for every configured pair |
| `list_my_work_items(sprints?)` | Work items assigned to you across all configured projects: id, title, state, type, project. Filters to the given sprint iteration path(s) if supplied, otherwise returns items across all sprints |
| `get_work_item(work_item_id)` | Project, title, state, description, acceptance criteria, effort, and child tasks |
| `set_work_item_state(work_item_id, state)` | Change a work item's state |
| `add_work_item_comment(work_item_id, text)` | Add a comment to a work item |
| `attach_plan(work_item_id, content, filename?)` | Attach a markdown plan (default `PLAN.md`) to a work item |
| `create_task(work_item_id, title, description?, effort?, assigned_to?)` | Create a child task under a work item. `assigned_to` defaults to the PAT owner if omitted. `description` is rendered as Markdown in Azure Boards |
| `update_task(task_id, title?, description?, state?, effort?, assigned_to?)` | Update a task's fields. `description` is rendered as Markdown in Azure Boards |
| `delete_task(task_id)` | Soft-delete a task (recycle bin) |
| `list_tasks(work_item_id)` | List a work item's child tasks: id, title, state |

## Installation

### Homebrew (macOS, Apple Silicon)

Both the tap and this repo are private, so you'll need an authenticated `gh` CLI session (`gh auth login`) with access to this repo — the formula shells out to `gh release download` to fetch the release asset, since anonymous downloads of private-repo release assets 404.

```bash
brew tap avinaba-dalal/ado-work-item-mcp git@github.com:avinaba-dalal/homebrew-ado-work-item-mcp.git
brew trust avinaba-dalal/ado-work-item-mcp
brew install ado-work-item-mcp
```

(The explicit SSH URL on `brew tap` is only needed if you don't have an HTTPS credential helper configured for GitHub. `brew trust` is required once per machine since this is a third-party tap.)

This installs a self-contained `ado_work_item_mcp` binary — no Python/venv setup needed.

### From source

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or (if above fails)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -e .
```

## Configuration

The easiest way to get set up is the interactive setup command, which checks prerequisites (`claude`/`gh` CLIs on `PATH`) and writes `config.json` for you:

```bash
ado_work_item_mcp setup
```

It prompts for your org URL, PAT, and project/team pairs, writes the result to `~/.config/ado_work_item_mcp/config.json` (or the path in `ADO_WORK_ITEM_MCP_CONFIG` if set) with `chmod 600` permissions, and prints the `claude mcp add` command to register the server. Re-run it any time to reset your config — it asks before overwriting an existing one.

Settings live in a JSON config file, **not** environment variables — this lets one server span multiple projects, each with multiple teams. If you'd rather write it by hand, copy [`config.example.json`](config.example.json) to a real path and fill it in:

```json
{
  "org_url": "https://dev.azure.com/ircost",
  "pat": "your-personal-access-token",
  "projects": {
    "Allegion Mobile Products": ["Unified SDK"],
    "IoT Services": ["Unicorns"]
  }
}
```

| Key | Required | Default | Description |
|---|---|---|---|
| `org_url` | yes | — | e.g. `https://dev.azure.com/your-org` |
| `pat` | yes | — | Personal Access Token — needs Work Items (Read & Write) scope |
| `projects` | yes | — | Object mapping project name → list of team names. Every project/team pair is considered when listing work items or current sprints |
| `work_item_types` | no | `["Product Backlog Item", "Bug", "Tech Debt Item", "Spike", "SSRD"]` | Work item type names to include when listing "my" sprint items |
| `task_type` | no | `"Task"` | Work item type name for child tasks |
| `acceptance_criteria_field` | no | `"Microsoft.VSTS.Common.AcceptanceCriteria"` | Field reference name for acceptance criteria |
| `effort_field` | no | `"Microsoft.VSTS.Scheduling.Effort"` | Field reference name for work item effort |
| `task_effort_field` | no | `"Microsoft.VSTS.Scheduling.OriginalEstimate"` | Field reference name for task effort |

The server reads this file from `~/.config/ado_work_item_mcp/config.json` by default, or from the path in `ADO_WORK_ITEM_MCP_CONFIG` if set. The file contains your PAT in plaintext — keep it out of version control (`config.json` is already gitignored in this repo) and restrict its permissions, e.g. `chmod 600 config.json`.

### Registering the server

This server is meant to be usable from *any* Claude Code session, in any directory — not just when working inside this repo. Register it once, globally, via the CLI (`--scope user`), which stores the registration in `~/.claude.json` and makes the tools available regardless of which directory a Claude Code session is rooted in.

If installed via Homebrew, the binary is already on `PATH`:

```bash
claude mcp add ado_work_item_mcp --scope user \
  -e ADO_WORK_ITEM_MCP_CONFIG="/path/to/your/config.json" \
  -- ado_work_item_mcp
```

If installed from source, point at the venv's interpreter instead:

```bash
claude mcp add ado_work_item_mcp --scope user \
  -e ADO_WORK_ITEM_MCP_CONFIG="/path/to/your/config.json" \
  -- /path/to/ado_work_item_mcp/.venv/bin/python -m ado_work_item_mcp.server
```

Omit the `-e ADO_WORK_ITEM_MCP_CONFIG=...` flag if you put your config at the default location (`~/.config/ado_work_item_mcp/config.json`).

Restart Claude Code afterwards so the new session picks up the registration. Run `claude mcp list` to confirm it's registered, and `claude mcp remove ado_work_item_mcp` to undo.

### Example workflow command

[`commands/implement_work_item.md`](commands/implement_work_item.md) is a starting-point Claude Code slash command that drives a full work-item implementation end-to-end using these tools. Copy it to `~/.claude/commands/` to use it as `/implement_work_item <work-item-id>`, adjusting the branch naming convention to your own. It walks through:

1. **Repo context check** — confirms it's running in the right local repo for this work item, asking if unclear.
2. **Initial checks** — reads the work item and requires `state` to be `Approved`/`Committed` and `effort` to be set (groomed), stopping or asking permission otherwise.
3. **Branch** — creates a new branch off a user-chosen base branch.
4. **Plan** — drafts an implementation plan and gets explicit user approval before any writes.
5. **Attach the plan** — scrubs it of local paths/secrets and attaches it to the work item as `PLAN.md` (the only write ever made to the work item itself — no state or comment changes).
6. **Implement** — does the work, creating/updating child tasks (`create_task`/`update_task`) as it goes, each with a markdown-formatted `description` and an `effort` estimate, keeping task state current (`New` → `In Progress` → `Done`).
7. **Verification** — runs tests (or another suitable check), tracked as its own child task.
8. **User review** — reports the finished implementation and verification, and waits for explicit user confirmation before proceeding.
9. **Pull request** — commits, creates "Raise PR"/"Merge PR" child tasks, opens a PR via `gh` (following any repo PR template) including `AB#<work-item-id>` in the title/description so Azure Boards auto-links it, and confirms with the user before actually raising it.

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
├── config.py   # config.json loading
├── client.py   # azure-devops SDK calls
└── server.py   # MCP tool definitions (FastMCP)
```

## Dependencies

- [`mcp[cli]`](https://github.com/modelcontextprotocol/python-sdk) — MCP server framework
- [`azure-devops`](https://github.com/microsoft/azure-devops-python-api) — Azure DevOps REST API wrapper
