import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

import requests

from .client import HubSpotClient


def get_filter_sort_key(f: dict) -> tuple:
    """Get a sort key for a filter based on property, type, and value."""
    operation = f.get("operation", {})
    op_value = operation.get("value", "") or str(operation.get("values", []))
    return (
        f.get("property", ""),
        f.get("filterType", ""),
        op_value,
    )


def get_filter_branch_sort_key(branch: dict) -> tuple:
    """Get a sort key for a filter branch based on its first filter."""
    filters = branch.get("filters", [])
    if filters:
        first_filter = filters[0]
        operation = first_filter.get("operation", {})
        op_value = operation.get("value", "") or str(operation.get("values", []))
        return (
            first_filter.get("property", ""),
            first_filter.get("filterType", ""),
            op_value,
        )
    return ("", "", "")


def sort_filters(obj: dict | list) -> dict | list:
    """Recursively sort filters and filter branches for consistent output."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "filters" and isinstance(value, list):
                obj[key] = sorted(value, key=get_filter_sort_key)
            elif key == "reEnrollmentTriggersFilterBranches" and isinstance(
                value, list
            ):
                for branch in value:
                    sort_filters(branch)
                obj[key] = sorted(value, key=get_filter_branch_sort_key)
            else:
                sort_filters(value)
    elif isinstance(obj, list):
        for item in obj:
            sort_filters(item)
    return obj


def normalize_flow(flow: dict) -> dict:
    """Normalize flow data for consistent serialization."""
    if "dataSources" in flow and isinstance(flow["dataSources"], list):
        flow["dataSources"] = sorted(
            flow["dataSources"],
            key=lambda ds: (
                ds.get("objectTypeId", ""),
                ds.get("associationTypeId", 0),
                ds.get("name", ""),
            ),
        )
    sort_filters(flow)
    return flow


def slugify(name: str, max_length: int = 80) -> str:
    """
    Convert flow name to filesystem-safe slug.

    Args:
        name: Flow name to slugify.
        max_length: Maximum slug length.

    Returns:
        Lowercase slug with only alphanumeric, dash, underscore.
    """
    if not name:
        return "unnamed-flow"
    slug = name.lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9_-]", "", slug)
    if not slug:
        slug = "unnamed-flow"
    if len(slug) > max_length:
        slug = slug[:max_length]
    return slug


def get_timestamp() -> str:
    """
    Get current UTC timestamp for backup naming.

    Returns:
        Timestamp string in YYYY_MM_DD_HHMMSS format.
    """
    return datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")


def backup_all_flows(
    token: Optional[str] = None,
    output_dir: Optional[Union[str, Path]] = None,
    client: Optional[HubSpotClient] = None,
    use_date_dir: bool = False,
    use_date_prefix: bool = False,
) -> Path:
    """
    Backup all HubSpot automation flows to JSON files.

    Args:
        token: HubSpot token. Falls back to HUBSPOT_AUTOMATION_TOKEN env var.
        output_dir: Directory for snapshots. Defaults to ./snapshots/.
        client: Pre-configured HubSpotClient instance.
        use_date_dir: If True, create a timestamped subdirectory for this run.
        use_date_prefix: If True, prefix each workflow filename with timestamp.

    Returns:
        Path to the created snapshot directory.
    """
    if client is None:
        client = HubSpotClient(token=token)

    timestamp = get_timestamp()

    if output_dir is None:
        output_dir = Path.cwd() / "snapshots"
    else:
        output_dir = Path(output_dir)

    if use_date_dir:
        run_dir = output_dir / timestamp
    else:
        run_dir = output_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    flows = client.list_flows()

    if not flows:
        return run_dir

    index_entries = []

    for flow in flows:
        flow_id = str(flow.get("id"))
        name = flow.get("name") or f"flow-{flow_id}"
        slug = slugify(name)

        try:
            details = client.get_flow(flow_id)
        except requests.exceptions.HTTPError:
            continue

        details = normalize_flow(details)

        if use_date_prefix:
            filename = f"{timestamp}_{slug}.json"
        else:
            filename = f"{slug}.json"
        filepath = run_dir / filename

        with filepath.open("w", encoding="utf-8") as f:
            json.dump(details, f, indent=2, sort_keys=True)

        index_entries.append({
            "id": flow_id,
            "name": name,
            "filename": filename,
            "isEnabled": details.get("isEnabled"),
            "flowType": details.get("flowType"),
            "type": details.get("type"),
        })

    for entry in index_entries:
        filepath = run_dir / entry["filename"]
        content = filepath.read_bytes()
        entry["hash"] = hashlib.sha256(content).hexdigest()

    index_path = run_dir / "_index.json"
    with index_path.open("w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "flows": index_entries,
        }, f, indent=2)

    return run_dir


def verify_backups(snapshot_dir: Optional[Union[str, Path]] = None) -> dict:
    """
    Verify all workflow backups against their stored SHA-256 hashes.

    Args:
        snapshot_dir: Directory containing snapshots. Defaults to ./snapshots/.

    Returns:
        Dict with 'verified', 'failed', and 'missing' lists of filenames.
    """
    if snapshot_dir is None:
        snapshot_path = Path.cwd() / "snapshots"
    else:
        snapshot_path = Path(snapshot_dir)

    index_path = snapshot_path / "_index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Index file not found: {index_path}")

    with index_path.open("r", encoding="utf-8") as f:
        index = json.load(f)

    results: dict = {"verified": [], "failed": [], "missing": []}

    for flow in index.get("flows", []):
        filename = flow.get("filename")
        expected_hash = flow.get("hash")

        if not filename or not expected_hash:
            continue

        filepath = snapshot_path / filename
        if not filepath.exists():
            results["missing"].append(filename)
            continue

        actual_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
        if actual_hash == expected_hash:
            results["verified"].append(filename)
        else:
            results["failed"].append(filename)

    return results


def main() -> None:
    """CLI entry point for workflows-backup command."""
    parser = argparse.ArgumentParser(
        description="Backup HubSpot automation workflows to JSON files."
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default=None,
        help="Output directory for snapshots (default: ./snapshots/)"
    )
    parser.add_argument(
        "--use-date-dir",
        action="store_true",
        help="Create a timestamped subdirectory for this backup run"
    )
    parser.add_argument(
        "--use-date-prefix",
        action="store_true",
        help="Prefix each workflow filename with a timestamp"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify backup integrity after completion"
    )
    args = parser.parse_args()

    try:
        client = HubSpotClient()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("Listing all HubSpot automation flows (v4)...\n")
    flows = client.list_flows()

    if not flows:
        print("No flows returned.")
        return

    print(f"Total flows returned: {len(flows)}")
    for flow in flows:
        print(f"{flow.get('id')}: {flow.get('name')}")

    print("\nBacking up flows...")
    run_dir = backup_all_flows(
        client=client,
        output_dir=args.output_dir,
        use_date_dir=args.use_date_dir,
        use_date_prefix=args.use_date_prefix,
    )

    print(f"\nBackup complete.")
    print(f"Files saved to: {run_dir}")

    if args.verify:
        print("\nVerifying backup integrity...")
        results = verify_backups(run_dir)
        print(f"  Verified: {len(results['verified'])}")
        if results["failed"]:
            print(f"  Failed: {len(results['failed'])}")
            for f in results["failed"]:
                print(f"    - {f}")
            sys.exit(1)
        if results["missing"]:
            print(f"  Missing: {len(results['missing'])}")
            for f in results["missing"]:
                print(f"    - {f}")
        print("All backups verified successfully.")


if __name__ == "__main__":
    main()
