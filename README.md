# HubSpot Workflow Backup & Restore

Backup and restore HubSpot Automation (v4) workflows. There is NO confirmation once you request a restore, it will just overwrite the workflow.

## Installation

```bash
# From PyPI
pip install ft-hubspot-workflow-backup

# Or with uv
uv pip install ft-hubspot-workflow-backup

# Or add to pyproject.toml
# dependencies = ["ft-hubspot-workflow-backup>=0.1.0"]
```

## Requirements

- Python 3.9+ (recommended with [`uv`](https://github.com/astral-sh/uv))
- HubSpot private app token with `automation` read/write scope
- Environment variable `HUBSPOT_AUTOMATION_TOKEN` set to your token

## Usage

### Backup all workflows

```bash
uv run workflows-backup
```

Creates `workflows_backup/<timestamp>/` with:
- One JSON file per workflow: `<timestamp>_<slugified-name>.json`
- An `index.json` listing all backed up flows

### Restore a workflow

```bash
uv run workflows-restore <backup-file> [--flow-id <id>] [--name "<name>"] [--dry]
```

Options:
- `--flow-id`: Target flow ID (defaults to ID in backup)
- `--name`: Override flow name
- `--dry`: Preview payload without sending

Example:
```bash
uv run workflows-restore workflows_backup/<timestamp>/<timestamp>_<workflow-name>.json --dry
```

### As a Python module

```python
from ft_hubspot_workflow_backup import backup_all_flows, restore_flow, HubSpotClient

# Backup (uses HUBSPOT_AUTOMATION_TOKEN env var)
backup_dir = backup_all_flows()

# Or with explicit token
client = HubSpotClient(token="your-token")
backup_dir = backup_all_flows(client=client)

# Restore
restore_flow("path/to/backup.json", flow_id="123456")
```

## Notes

- Secrets (`secretNames`) are not backed up; only their names are referenced.
- Flows reference HubSpot assets (pipelines, stages, templates) by ID. Restores assume those IDs are still valid.
- Restored flows are always set to DISABLED. Enable manually after verifying.

## License

MIT License

Copyright (c) 2026 Nathan Flore / Flore Technologies, LLC.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
