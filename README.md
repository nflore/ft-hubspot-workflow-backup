# HubSpot Workflow Backup & Restore

This folder contains scripts to back up and restore HubSpot Automation (v4) flows. There is NO confirmation once you request a restore, it will just overwrite the workflow.

## Requirements

- Python (recommended with [`uv`](https://github.com/astral-sh/uv))
- HubSpot private app token with at least `automation` read/write scope
- Environment variable:
-  - `HUBSPOT_AUTOMATION_TOKEN` set to your HubSpot private app token

## Backup: export all flows

From this directory (with `HUBSPOT_AUTOMATION_TOKEN` already exported in your shell):

```bash
uv run --with requests hubspot_backup_flows.py
```

What it does:

- Calls `GET /automation/v4/flows` to list all flows (with pagination).
- Prints `id: name` for each flow.
- Creates a timestamped folder under `hubspot-backup/` in this directory, e.g.
  - `hubspot-backup/<timestamp>_backups/`
- For each flow ID:
  - Calls `GET /automation/v4/flows/{flowId}`
  - Writes a JSON file: `YYYY_MM_DD_HHMMSS_<slugified-name>.json`
- Writes an `index.json` describing all flows in that run.

Use this whenever you want a snapshot of all automation logic.

## Restore: replace a flow from a backup

From this directory (with `HUBSPOT_AUTOMATION_TOKEN` already exported in your shell):

```bash
uv run --with requests hubspot_restore_flow_from_backup.py \
  hubspot-backup/<timestamp>_backups/<timestamp>_<workflow-name>.json \
  --flow-id <flow-id> \
  --name "<name>"
```

Key behavior:

- `backup_path` (positional): path to a JSON file produced by the backup script.
- `--flow-id` (optional): target HubSpot flow ID to update.
  - If omitted, the script uses the `id` field inside the backup JSON.
- `--name` (optional): overrides the flow name in HubSpot (useful to "clone" logic into a differently named test flow).
- `--dry`: prints the exact JSON body that would be sent to HubSpot without doing the PUT.

Under the hood, the restore script:

1. Loads the backup JSON.
2. Determines the target `flowId`.
3. Calls `GET /automation/v4/flows/{flowId}` to fetch the **current** `revisionId` and `type`.
4. Builds a request body from the backup JSON, but forces:
   - `revisionId` = current revision from HubSpot
   - `type` = current type from HubSpot (e.g. `PLATFORM_FLOW`)
   - `id` = target `flowId`
5. Optionally overrides `name` if `--name` is provided.
6. `PUT /automation/v4/flows/{flowId}` to create a new revision matching the backup.

## Typical workflow

1. **Set your token once per shell session or add to env**:

   ```bash
   export HUBSPOT_AUTOMATION_TOKEN="<your_private_app_token>"
   ```

2. **Backup everything** before making edits:
   - Run the backup script and commit the new `*_backups/` folder to version control.
3. **If a regression happens** in a given flow:
   - Identify the correct backup JSON for that flow.
   - Run restore in `--dry` mode to inspect the payload.
   - Run without `--dry` to push the backup config back into HubSpot.

## Notes

- Secrets used by flows (`secretNames`) are **not** backed up; only their names are referenced. The actual secret values live in HubSpot and must be configured separately.
- Flows reference other HubSpot assets (pipelines, stages, email templates, users) by ID. Restores assume those IDs are still valid.

## License

MIT License

Copyright (c) 2026 Nathan Flore / Flore Technologies, LLC.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
