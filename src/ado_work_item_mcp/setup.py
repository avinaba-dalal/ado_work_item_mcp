import getpass
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ado_work_item_mcp" / "config.json"
SKILL_PATH = Path.home() / ".claude" / "commands" / "implement_work_item.md"
MCP_SERVER_NAME = "ado_work_item_mcp"


def _config_path() -> Path:
    env_path = os.environ.get("ADO_WORK_ITEM_MCP_CONFIG")
    return Path(env_path) if env_path else DEFAULT_CONFIG_PATH


def _mcp_server_status(claude_path: str) -> str:
    try:
        result = subprocess.run(
            [claude_path, "mcp", "list"], capture_output=True, text=True, timeout=15
        )
    except (subprocess.SubprocessError, OSError) as e:
        return f"could not check ({e})"

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith(f"{MCP_SERVER_NAME}:"):
            return line.split(" - ", 1)[-1].strip() if " - " in line else line
    return "not registered (run `claude mcp add`, see README)"


def run_preflight() -> None:
    print("Checking prerequisites...")

    claude_path = shutil.which("claude")
    print(f"  claude CLI:   {'found at ' + claude_path if claude_path else 'NOT FOUND (needed to register this server)'}")

    gh_path = shutil.which("gh")
    print(f"  gh CLI:       {'found at ' + gh_path if gh_path else 'not found (only needed for the implement_work_item PR step)'}")

    if claude_path:
        print(f"  MCP server:   {_mcp_server_status(claude_path)}")
    else:
        print("  MCP server:   skipped (claude CLI not found)")

    skill_found = SKILL_PATH.exists()
    print(f"  implement_work_item skill: {'found at ' + str(SKILL_PATH) if skill_found else 'NOT FOUND at ' + str(SKILL_PATH)}")

    config_path = _config_path()
    config_found = config_path.exists()
    print(f"  config.json:  {'found at ' + str(config_path) if config_found else 'NOT FOUND - run `ado_work_item_mcp setup config`'}")


def _prompt_projects() -> dict[str, list[str]]:
    projects: dict[str, list[str]] = {}
    print("Enter your Azure DevOps projects and teams (blank project name to finish).")
    while True:
        project = input("  Project name: ").strip()
        if not project:
            break
        teams_raw = input(f"  Teams under '{project}' (comma-separated): ").strip()
        teams = [t.strip() for t in teams_raw.split(",") if t.strip()]
        if not teams:
            print("  Need at least one team - skipping this project.")
            continue
        projects[project] = teams
    return projects


def run_setup() -> None:
    path = _config_path()
    if path.exists():
        answer = input(f"Config already exists at {path}. Overwrite? [y/N] ").strip().lower()
        if answer != "y":
            print("Leaving existing config untouched.")
            return

    org_url = input("Azure DevOps org URL (e.g. https://dev.azure.com/your-org): ").strip()
    pat = getpass.getpass("Personal Access Token (Work Items Read & Write scope, input hidden): ").strip()
    projects = _prompt_projects()

    if not org_url or not pat or not projects:
        print("Aborting - org URL, PAT, and at least one project/team are required.")
        sys.exit(1)

    config = {"org_url": org_url, "pat": pat, "projects": projects}

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    print(f"\nWrote config to {path}")
    binary = shutil.which("ado_work_item_mcp") or sys.argv[0]
    print("\nRegister the server with Claude Code:")
    print(f"  claude mcp add ado_work_item_mcp --scope user -- {binary}")
    if path != DEFAULT_CONFIG_PATH:
        print(f'  (add -e ADO_WORK_ITEM_MCP_CONFIG="{path}" before -- since this isn\'t the default location)')
