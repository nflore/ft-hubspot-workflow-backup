import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

import requests

from .client import HubSpotClient


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
) -> Path:
    """
    Backup all HubSpot automation flows to JSON files.

    Args:
        token: HubSpot token. Falls back to HUBSPOT_AUTOMATION_TOKEN env var.
        output_dir: Directory for backups. Defaults to ./workflows_backup/.
        client: Pre-configured HubSpotClient instance.

    Returns:
        Path to the created backup directory.
    """
    if client is None:
        client = HubSpotClient(token=token)

    timestamp = get_timestamp()

    if output_dir is None:
        output_dir = Path.cwd() / "workflows_backup"
    else:
        output_dir = Path(output_dir)

    run_dir = output_dir / timestamp
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

        filename = f"{timestamp}_{slug}.json"
        filepath = run_dir / filename

        with filepath.open("w", encoding="utf-8") as f:
            json.dump(details, f, indent=2)

        index_entries.append({
            "id": flow_id,
            "name": name,
            "filename": filename,
            "isEnabled": details.get("isEnabled"),
            "flowType": details.get("flowType"),
            "type": details.get("type"),
        })

    index_path = run_dir / "index.json"
    with index_path.open("w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "flows": index_entries,
        }, f, indent=2)

    return run_dir


def main() -> None:
    """CLI entry point for workflows-backup command."""
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
    run_dir = backup_all_flows(client=client)

    print(f"\nBackup complete.")
    print(f"Files saved to: {run_dir}")


if __name__ == "__main__":
    main()
