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


def _bundled_skill_path() -> Path | None:
    """Locate the implement_work_item.md shipped alongside this install.

    Homebrew's `share/ado_work_item_mcp/` sits next to `bin/` under the same
    prefix; a source checkout has `commands/` at the repo root instead.
    """
    candidates = [
        Path(sys.executable).resolve().parent.parent / "share" / "ado_work_item_mcp" / "implement_work_item.md",
        Path(__file__).resolve().parents[2] / "commands" / "implement_work_item.md",
    ]
    return next((c for c in candidates if c.exists()), None)


def _ensure_skill_installed() -> None:
    if SKILL_PATH.exists():
        return
    bundled = _bundled_skill_path()
    if bundled is None:
        return
    SKILL_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(bundled, SKILL_PATH)
    print(f"\nInstalled the implement_work_item skill to {SKILL_PATH}")


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
    return "not registered"


def run_preflight() -> str | None:
    """Print a diagnostic summary and return the resolved `claude` binary path, if any.

    `claude` is the one mandatory prerequisite (it's how this server gets registered
    and run); everything else here is advisory.
    """
    print("Checking prerequisites...")

    claude_path = shutil.which("claude")
    print(f"  claude CLI:   {'found at ' + claude_path if claude_path else 'NOT FOUND (required - install Claude Code first)'}")

    gh_path = shutil.which("gh")
    print(f"  gh CLI:       {'found at ' + gh_path if gh_path else 'not found (only needed for the implement_work_item PR step)'}")

    if claude_path:
        print(f"  MCP server:   {_mcp_server_status(claude_path)}")
    else:
        print("  MCP server:   skipped (claude CLI not found)")

    skill_found = SKILL_PATH.exists()
    print(f"  implement_work_item skill: {'found at ' + str(SKILL_PATH) if skill_found else 'not found at ' + str(SKILL_PATH)}")

    config_path = _config_path()
    config_found = config_path.exists()
    print(f"  config.json:  {'found at ' + str(config_path) if config_found else 'not found - run `ado_work_item_mcp setup`'}")

    return claude_path


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


def _write_config(path: Path) -> None:
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


def _register_with_claude(claude_path: str, config_path: Path) -> None:
    status = _mcp_server_status(claude_path)
    if status != "not registered":
        print(f"\nMCP server already registered with Claude ({status}) - skipping registration.")
        print(f"  To re-register: claude mcp remove {MCP_SERVER_NAME}, then re-run `ado_work_item_mcp setup`.")
        return

    binary = shutil.which("ado_work_item_mcp") or sys.argv[0]
    args = [claude_path, "mcp", "add", MCP_SERVER_NAME, "--scope", "user"]
    if config_path != DEFAULT_CONFIG_PATH:
        args += ["-e", f"ADO_WORK_ITEM_MCP_CONFIG={config_path}"]
    args += ["--", binary, "serve"]

    print(f"\nRegistering with Claude Code:\n  {' '.join(args)}")
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except (subprocess.SubprocessError, OSError) as e:
        print(f"Registration failed: {e}")
        return

    if result.returncode == 0:
        print("Registered. Restart Claude Code to pick it up.")
    else:
        print(f"Registration failed:\n{(result.stderr or result.stdout).strip()}")


def run_setup() -> None:
    claude_path = run_preflight()
    if not claude_path:
        print("\nAborting - the claude CLI is required to register this server (see https://claude.com/claude-code).")
        sys.exit(1)

    print()
    path = _config_path()
    if path.exists():
        answer = input(f"Config already exists at {path}. Overwrite? [y/N] ").strip().lower()
        if answer == "y":
            _write_config(path)
        else:
            print("Leaving existing config untouched.")
    else:
        _write_config(path)

    _ensure_skill_installed()
    _register_with_claude(claude_path, path)
