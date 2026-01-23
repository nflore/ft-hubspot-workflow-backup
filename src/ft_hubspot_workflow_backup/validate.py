import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union


def validate_snapshots(
    snapshots_dir: Optional[Union[str, Path]] = None,
) -> tuple[bool, list[dict]]:
    """
    Compare current workflow snapshots against git HEAD using the index.

    Args:
        snapshots_dir: Directory containing snapshots. Defaults to ./snapshots/.

    Returns:
        Tuple of (is_valid, changes) where is_valid is True if no changes detected,
        and changes is a list of dicts describing each changed workflow.
    """
    if snapshots_dir is None:
        snapshots_dir = Path.cwd() / "snapshots"
    else:
        snapshots_dir = Path(snapshots_dir)

    index_path = snapshots_dir / "_index.json"

    if not index_path.exists():
        return False, [{"error": "No _index.json found in snapshots directory"}]

    try:
        repo_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=snapshots_dir,
        ).stdout.strip()
        rel_index_path = index_path.relative_to(repo_root)
    except subprocess.CalledProcessError:
        return False, [{"error": "Not a git repository"}]

    try:
        committed_index_raw = subprocess.run(
            ["git", "show", f"HEAD:{rel_index_path}"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        ).stdout
        committed_index = json.loads(committed_index_raw)
    except subprocess.CalledProcessError:
        return False, [{"error": "No committed _index.json found in git HEAD"}]

    with index_path.open("r", encoding="utf-8") as f:
        current_index = json.load(f)

    committed_flows = {flow["id"]: flow for flow in committed_index.get("flows", [])}
    current_flows = {flow["id"]: flow for flow in current_index.get("flows", [])}

    changes = []

    for flow_id, committed_flow in committed_flows.items():
        if flow_id not in current_flows:
            changes.append(
                {
                    "id": flow_id,
                    "name": committed_flow.get("name"),
                    "filename": committed_flow.get("filename"),
                    "change": "removed",
                }
            )
        elif current_flows[flow_id].get("hash") != committed_flow.get("hash"):
            changes.append(
                {
                    "id": flow_id,
                    "name": current_flows[flow_id].get("name"),
                    "filename": current_flows[flow_id].get("filename"),
                    "change": "modified",
                    "old_hash": committed_flow.get("hash"),
                    "new_hash": current_flows[flow_id].get("hash"),
                }
            )

    for flow_id, current_flow in current_flows.items():
        if flow_id not in committed_flows:
            changes.append(
                {
                    "id": flow_id,
                    "name": current_flow.get("name"),
                    "filename": current_flow.get("filename"),
                    "change": "added",
                }
            )

    return len(changes) == 0, changes


def main() -> None:
    """CLI entry point for workflows-validate command."""
    parser = argparse.ArgumentParser(
        description="Validate workflow snapshots against git HEAD."
    )
    parser.add_argument(
        "-d", "--snapshots-dir",
        type=str,
        default=None,
        help="Snapshots directory (default: ./snapshots/)"
    )
    args = parser.parse_args()

    snapshots_dir = Path(args.snapshots_dir) if args.snapshots_dir else Path.cwd() / "snapshots"

    print("Validating workflow snapshots against git HEAD...\n")

    is_valid, changes = validate_snapshots(snapshots_dir)

    if is_valid:
        print("All workflow snapshots match git HEAD.")
        sys.exit(0)

    for change in changes:
        if "error" in change:
            print(f"Error: {change['error']}", file=sys.stderr)
            sys.exit(1)

    print(f"Found {len(changes)} workflow(s) with differences:\n")

    for change in changes:
        status = change["change"].upper()
        name = change.get("name", "Unknown")
        filename = change.get("filename", "Unknown")
        print(f"  [{status}] {name}")
        print(f"           File: {filename}")
        if change["change"] == "modified":
            print(f"           Old hash: {change['old_hash'][:12]}...")
            print(f"           New hash: {change['new_hash'][:12]}...")
        print()

    sys.exit(1)


if __name__ == "__main__":
    main()
