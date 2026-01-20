import os
from typing import Optional

import requests


class HubSpotClient:
    """Client for HubSpot Automation v4 API."""

    BASE_URL = "https://api.hubapi.com"

    def __init__(self, token: Optional[str] = None):
        """
        Initialize client.

        Args:
            token: HubSpot private app token. Falls back to HUBSPOT_AUTOMATION_TOKEN env var.
        """
        self.token = token or os.getenv("HUBSPOT_AUTOMATION_TOKEN")
        if not self.token:
            raise ValueError(
                "HubSpot token required. Pass token= or set HUBSPOT_AUTOMATION_TOKEN env var."
            )
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def list_flows(self) -> list:
        """
        List all automation flows with pagination.

        Returns:
            List of flow summary dicts.
        """
        url = f"{self.BASE_URL}/automation/v4/flows"
        params = {"limit": 100}
        flows: list = []

        while True:
            resp = requests.get(url, headers=self._headers, params=params, timeout=30)
            resp.raise_for_status()

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

    def get_flow(self, flow_id: str) -> dict:
        """
        Get full details of a flow.

        Args:
            flow_id: HubSpot flow ID.

        Returns:
            Flow details dict.
        """
        url = f"{self.BASE_URL}/automation/v4/flows/{flow_id}"
        resp = requests.get(url, headers=self._headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def update_flow(self, flow_id: str, body: dict) -> dict:
        """
        Update a flow configuration.

        Args:
            flow_id: HubSpot flow ID.
            body: Flow configuration to apply.

        Returns:
            Updated flow dict.
        """
        url = f"{self.BASE_URL}/automation/v4/flows/{flow_id}"
        resp = requests.put(url, headers=self._headers, json=body, timeout=30)
        resp.raise_for_status()
        return resp.json()
