import os
import sys
import json
import re
import argparse
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


def get_current_flow(flow_id: str) -> dict:
    url = f"{BASE_URL}/automation/v4/flows/{flow_id}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching current flow {flow_id} from HubSpot:", file=sys.stderr)
        print(f"  Status: {resp.status_code}", file=sys.stderr)
        try:
            print(f"  Response: {resp.text}", file=sys.stderr)
        except Exception:
            pass
        raise e
    return resp.json()


def put_flow(flow_id: str, body: dict) -> dict:
    url = f"{BASE_URL}/automation/v4/flows/{flow_id}"
    resp = requests.put(url, headers=HEADERS, json=body, timeout=30)
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"Error updating flow {flow_id} in HubSpot:", file=sys.stderr)
        print(f"  Status: {resp.status_code}", file=sys.stderr)
        try:
            print(f"  Response: {resp.text}", file=sys.stderr)
        except Exception:
            pass
        raise e
    return resp.json()


def build_datasource_mapping(backup_datasources: list, target_datasources: list) -> dict:
    def ds_key(ds):
        return (ds.get("objectTypeId"), ds.get("associationTypeId"), ds.get("type"))
    
    def extract_id(name):
        match = re.search(r'fetched_object_(\d+)', name)
        return match.group(1) if match else None
    
    target_by_key = {}
    for ds in target_datasources:
        key = ds_key(ds)
        ds_id = extract_id(ds.get("name", ""))
        if ds_id and key not in target_by_key:
            target_by_key[key] = ds_id
    
    mapping = {}
    for ds in backup_datasources:
        key = ds_key(ds)
        backup_id = extract_id(ds.get("name", ""))
        if backup_id and key in target_by_key:
            target_id = target_by_key[key]
            if backup_id != target_id:
                mapping[backup_id] = target_id
    
    return mapping


def remap_fetched_objects(obj, mapping: dict):
    if not mapping:
        return obj
    if isinstance(obj, str):
        result = obj
        for old_id, new_id in mapping.items():
            result = result.replace(f"fetched_object_{old_id}", f"fetched_object_{new_id}")
        return result
    elif isinstance(obj, dict):
        return {k: remap_fetched_objects(v, mapping) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [remap_fetched_objects(item, mapping) for item in obj]
    return obj


def renumber_actions(backup_actions: list, backup_start_id: str, current_next_available: str) -> tuple:
    if not backup_actions:
        return [], None, current_next_available
    
    start_id = int(current_next_available)
    old_to_new = {}
    
    for i, action in enumerate(backup_actions):
        old_id = action.get("actionId")
        new_id = str(start_id + i)
        old_to_new[old_id] = new_id
    
    def remap_id(old_id):
        return old_to_new.get(old_id, old_id)
    
    def remap_action(action):
        new_action = dict(action)
        new_action["actionId"] = remap_id(action["actionId"])
        
        if "connection" in new_action:
            conn = dict(new_action["connection"])
            if "nextActionId" in conn:
                conn["nextActionId"] = remap_id(conn["nextActionId"])
            new_action["connection"] = conn
        
        if "staticBranches" in new_action and new_action["staticBranches"]:
            new_branches = []
            for branch in new_action["staticBranches"]:
                new_branch = dict(branch)
                if "nextActionId" in new_branch:
                    new_branch["nextActionId"] = remap_id(new_branch["nextActionId"])
                if "connection" in new_branch and new_branch["connection"]:
                    conn = dict(new_branch["connection"])
                    if "nextActionId" in conn:
                        conn["nextActionId"] = remap_id(conn["nextActionId"])
                    new_branch["connection"] = conn
                new_branches.append(new_branch)
            new_action["staticBranches"] = new_branches
        
        if "defaultBranch" in new_action:
            db = dict(new_action["defaultBranch"])
            if "nextActionId" in db:
                db["nextActionId"] = remap_id(db["nextActionId"])
            new_action["defaultBranch"] = db
        
        if "acceptActions" in new_action:
            new_action["acceptActions"] = [remap_id(a) for a in new_action["acceptActions"]]
        if "rejectActions" in new_action:
            new_action["rejectActions"] = [remap_id(a) for a in new_action["rejectActions"]]
        
        if "listBranches" in new_action and new_action["listBranches"]:
            new_list_branches = []
            for lb in new_action["listBranches"]:
                new_lb = dict(lb)
                if "connection" in new_lb and new_lb["connection"]:
                    conn = dict(new_lb["connection"])
                    if "nextActionId" in conn:
                        conn["nextActionId"] = remap_id(conn["nextActionId"])
                    new_lb["connection"] = conn
                new_list_branches.append(new_lb)
            new_action["listBranches"] = new_list_branches
        
        return new_action
    
    renumbered = [remap_action(a) for a in backup_actions]
    new_start_id = remap_id(backup_start_id) if backup_start_id else None
    new_next_available = str(start_id + len(backup_actions))
    
    def remap_action_output_refs(obj):
        if isinstance(obj, str):
            def replace_ref(match):
                prefix = match.group(1)
                old_id = match.group(2)
                new_id = old_to_new.get(old_id, old_id)
                return f"{prefix}{new_id}"
            return re.sub(r'(action_outputs?\.action_output_?)(\d+)', replace_ref, obj)
        elif isinstance(obj, dict):
            return {k: remap_action_output_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [remap_action_output_refs(item) for item in obj]
        else:
            return obj
    
    renumbered = remap_action_output_refs(renumbered)
    
    return renumbered, new_start_id, new_next_available


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore/replace a HubSpot automation flow from a backup JSON file.")
    parser.add_argument("backup_path", help="Path to the backup JSON file")
    parser.add_argument("--flow-id", dest="flow_id", help="Override target flowId (defaults to id in backup)")
    parser.add_argument("--name", dest="name", help="Override flow name in the restored configuration")
    parser.add_argument("--dry", action="store_true", help="Show what would be sent, but do not PUT")

    args = parser.parse_args()

    backup_file = Path(args.backup_path)
    if not backup_file.is_file():
        print(f"Backup file not found: {backup_file}", file=sys.stderr)
        sys.exit(1)

    with backup_file.open("r", encoding="utf-8") as f:
        backup = json.load(f)

    flow_id = args.flow_id or backup.get("id")
    if not flow_id:
        print("flowId not provided and not present in backup JSON.", file=sys.stderr)
        sys.exit(1)

    flow_id = str(flow_id)

    print(f"Using flowId: {flow_id}")
    print(f"Backup file: {backup_file}")

    current = get_current_flow(flow_id)

    current_revision = current.get("revisionId")
    current_type = current.get("type")
    current_name = current.get("name")
    current_next_available = current.get("nextAvailableActionId", "1")

    print("\nCurrent flow summary:")
    print(f"  name: {current_name}")
    print(f"  revisionId: {current_revision}")
    print(f"  type: {current_type}")
    print(f"  nextAvailableActionId: {current_next_available}")

    backup_name = backup.get("name")
    backup_revision = backup.get("revisionId")
    backup_actions = backup.get("actions", [])
    backup_start_id = backup.get("startActionId")

    print("\nBackup summary:")
    print(f"  name: {backup_name}")
    print(f"  revisionId (from backup): {backup_revision}")
    print(f"  actions: {len(backup_actions)}")

    renumbered_actions, new_start_id, new_next_available = renumber_actions(
        backup_actions, backup_start_id, current_next_available
    )

    if backup_actions:
        print(f"\nRenumbering {len(backup_actions)} actions (IDs starting from {current_next_available})")

    ds_mapping = build_datasource_mapping(
        backup.get("dataSources", []),
        current.get("dataSources", [])
    )
    if ds_mapping:
        print(f"Remapping {len(ds_mapping)} dataSource reference(s)")
        renumbered_actions = remap_fetched_objects(renumbered_actions, ds_mapping)

    body = {
        "type": current_type,
        "revisionId": current_revision,
        "objectTypeId": current.get("objectTypeId"),
        "flowType": current.get("flowType"),
        "actions": renumbered_actions,
        "startActionId": new_start_id,
        "nextAvailableActionId": new_next_available,
    }

    if args.name:
        body["name"] = args.name
    elif "name" in backup:
        body["name"] = backup["name"]
    else:
        body["name"] = current_name

    body["isEnabled"] = False

    keys_to_copy = [
        "description",
        "customProperties",
        "enrollmentCriteria",
        "blockedDates",
        "timeWindows",
    ]
    for key in keys_to_copy:
        if key in backup:
            body[key] = backup[key]

    backup_enabled = backup.get("isEnabled", False)
    if backup_enabled:
        print("\nNote: Flow will be restored in DISABLED state. Enable manually after verifying.")

    if args.dry:
        print("\n[DRY RUN] Would send PUT /automation/v4/flows/{flowId} with body:")
        print(json.dumps(body, indent=2))
        return

    print("\nSending PUT to update flow to backup configuration...")
    updated = put_flow(flow_id, body)

    print("\nUpdate complete. New flow summary:")
    print(f"  id: {updated.get('id')}")
    print(f"  name: {updated.get('name')}")
    print(f"  revisionId: {updated.get('revisionId')}")
    print(f"  isEnabled: {updated.get('isEnabled')}")


if __name__ == "__main__":
    main()
