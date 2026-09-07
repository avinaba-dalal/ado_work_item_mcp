import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        from ado_work_item_mcp.setup import run_setup

        run_setup()
        return

    from ado_work_item_mcp.server import main as server_main

    server_main()
