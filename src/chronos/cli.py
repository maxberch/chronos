"""CLI for Chronos to inspect runs, examine DAG checkpoints, and visualize execution trees."""

import argparse
import sys
import json
from chronos.storage import ChronosStore


def cmd_runs(args):
    store = ChronosStore(db_path=args.db)
    with store._get_connection() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        if not rows:
            print("No Chronos runs found in database.")
            return
        print("\n--- Chronos Runs ---")
        for r in rows:
            print(f"• Run ID: {r['run_id']} | Name: {r['name']} | Created: {r['created_at']}")


def cmd_log(args):
    store = ChronosStore(db_path=args.db)
    checkpoints = store.get_branch_checkpoints(args.branch)
    if not checkpoints:
        print(f"No checkpoints found for branch '{args.branch}'.")
        return

    print(f"\n--- Checkpoint Log for Branch: {args.branch} ---")
    for chk in checkpoints:
        status_icon = "❌" if chk.event.error else "✅"
        print(
            f"[{chk.checkpoint_id}] Step {chk.step_index:02d} {status_icon} "
            f"<{chk.event.event_type.value.upper()}:{chk.event.name}> "
            f"({chk.event.duration_ms:.1f}ms)"
        )
        if chk.event.error:
            print(f"   └── Error: {chk.event.error}")


def cmd_inspect(args):
    store = ChronosStore(db_path=args.db)
    chk = store.get_checkpoint(args.checkpoint_id)
    if not chk:
        print(f"Checkpoint '{args.checkpoint_id}' not found.")
        sys.exit(1)

    print(f"\nCheckpoint Details: {chk.checkpoint_id}")
    print(f"Run ID:      {chk.run_id}")
    print(f"Branch ID:   {chk.branch_id}")
    print(f"Step Index:  {chk.step_index}")
    print(f"Parent ID:   {chk.parent_id or 'ROOT'}")
    print(f"Event Type:  {chk.event.event_type.value}")
    print(f"Name:        {chk.event.name}")
    print(f"Duration:    {chk.event.duration_ms:.2f} ms")
    print(f"Status:      {'FAILED: ' + chk.event.error if chk.event.error else 'SUCCESS'}")
    print("\n--- Inputs ---")
    print(json.dumps(chk.event.inputs, indent=2))
    print("\n--- Outputs ---")
    print(json.dumps(chk.event.outputs, indent=2))


def main():
    parser = argparse.ArgumentParser(prog="chronos", description="Time-Travel Debugger for AI Agents")
    parser.add_argument("--db", default=".chronos.db", help="Path to SQLite database")

    subparsers = parser.add_subparsers(dest="command")

    # runs
    subparsers.add_parser("runs", help="List all runs")

    # log
    log_parser = subparsers.add_parser("log", help="Show checkpoints for a branch")
    log_parser.add_argument("branch", default="main", nargs="?", help="Branch name (default: main)")

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect a specific checkpoint")
    inspect_parser.add_argument("checkpoint_id", help="Checkpoint ID to inspect")

    args = parser.parse_args()
    if args.command == "runs":
        cmd_runs(args)
    elif args.command == "log":
        cmd_log(args)
    elif args.command == "inspect":
        cmd_inspect(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
