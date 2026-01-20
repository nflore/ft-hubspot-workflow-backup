import os
import sys
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

HUBSPOT_TOKEN = os.getenv("HUBSPOT_AUTOMATION_TOKEN")
if not HUBSPOT_TOKEN:
    print("Error: HUBSPOT_AUTOMATION_TOKEN environment variable is not set.", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}


def slugify(name: str, max_length: int = 80) -> str:
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
    return datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")


def list_flows() -> list:
    url = f"{BASE_URL}/automation/v4/flows"
    params = {"limit": 100}
    flows: list = []

    while True:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print("Error listing flows from HubSpot:", file=sys.stderr)
            print(f"  Status: {resp.status_code}", file=sys.stderr)
            try:
                print(f"  Response: {resp.text}", file=sys.stderr)
            except Exception:
                pass
            raise e

        data = resp.json()
        batch = data.get("results", [])
        flows.extend(batch)

        paging = data.get("paging") or {}
        next_page = paging.get("next") if isinstance(paging, dict) else None
        after = next_page.get("after") if isinstance(next_page, dict) else None
        if not after:
            break
        params["after"] = after

    return flows


def get_flow_details(flow_id: str) -> dict:
    url = f"{BASE_URL}/automation/v4/flows/{flow_id}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching flow {flow_id} details from HubSpot:", file=sys.stderr)
        print(f"  Status: {resp.status_code}", file=sys.stderr)
        try:
            print(f"  Response: {resp.text}", file=sys.stderr)
        except Exception:
            pass
        raise e
    return resp.json()


def main() -> None:
    timestamp = get_timestamp()
    project_root = Path(__file__).resolve().parent
    backup_root = project_root / "hubspot-backup"
    run_dir = backup_root / f"{timestamp}_backups"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("Listing all HubSpot automation flows (v4)...\n")
    flows = list_flows()

    if not flows:
        print("No flows returned.")
        return

    print(f"Total flows returned: {len(flows)}")
    for flow in flows:
        print(f"{flow.get('id')}: {flow.get('name')}")

    index_entries = []

    print("\nBacking up each flow to:")
    print(f"  {run_dir}")

    for flow in flows:
        flow_id = str(flow.get("id"))
        name = flow.get("name") or f"flow-{flow_id}"
        slug = slugify(name)

        try:
            details = get_flow_details(flow_id)
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

        print(f"Saved {flow_id} ({name}) -> {filepath}")

    index_path = run_dir / "index.json"
    with index_path.open("w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "flows": index_entries,
        }, f, indent=2)

    print("\nBackup complete.")
    print(f"Index written to: {index_path}")


if __name__ == "__main__":
    main()
