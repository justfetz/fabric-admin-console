"""
Fabric REST API client.

Core authentication and HTTP methods for Fabric and Power BI REST APIs using
the service-principal client credentials flow.
"""

from __future__ import annotations

import base64
import json
import os
import time

import requests
from dotenv import load_dotenv

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

load_dotenv()

FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
POWERBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"


class FabricClient:
    def __init__(self) -> None:
        self.tenant_id = os.getenv("AZURE_TENANT_ID")
        self.client_id = os.getenv("AZURE_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_CLIENT_SECRET")
        self._token_cache = None
        self._token_expiry = 0.0
        self._pbi_token_cache = None
        self._pbi_token_expiry = 0.0

        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError(
                "Missing AZURE_TENANT_ID, AZURE_CLIENT_ID, or AZURE_CLIENT_SECRET in .env"
            )

    def _get_token(self) -> str:
        if self._token_cache and time.time() < self._token_expiry - 60:
            return self._token_cache

        from msal import ConfidentialClientApplication

        app = ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(scopes=[FABRIC_SCOPE])
        if "access_token" not in result:
            raise Exception(f"Authentication failed: {result.get('error_description', result)}")

        self._token_cache = result["access_token"]
        self._token_expiry = time.time() + result.get("expires_in", 3600)
        return self._token_cache

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, body=None, raw: bool = False):
        url = f"{FABRIC_API_BASE}{path}" if path.startswith("/") else path
        response = requests.request(method, url, headers=self._headers(), json=body)

        if raw:
            return response

        if response.status_code == 202:
            return self._poll_operation(response)

        if response.status_code == 204:
            return None

        if response.status_code >= 400:
            try:
                error = response.json()
            except Exception:
                error = response.text
            return {"error": True, "status": response.status_code, "detail": error}

        try:
            data = response.json()
            if isinstance(data, list):
                return {"value": data}
            return data
        except Exception:
            return {"status": response.status_code, "text": response.text}

    def _poll_operation(self, response, timeout: int = 300):
        operation_id = response.headers.get("x-ms-operation-id")
        location = response.headers.get("Location")
        retry_after = int(response.headers.get("Retry-After", 5))

        if not operation_id and not location:
            return {"status": 202, "message": "Accepted (no operation ID)"}

        poll_url = location or f"{FABRIC_API_BASE}/operations/{operation_id}"
        start = time.time()

        while time.time() - start < timeout:
            time.sleep(retry_after)
            result = requests.get(poll_url, headers=self._headers())
            if result.status_code == 200:
                data = result.json()
                status = data.get("status", "Unknown")
                if status in ("Succeeded", "Completed"):
                    return {"status": status, "operation": data}
                if status in ("Failed", "Cancelled"):
                    return {"error": True, "status": status, "operation": data}
                retry_after = int(result.headers.get("Retry-After", 5))

        return {"status": "Timeout", "message": f"Operation timed out after {timeout}s"}

    def get(self, path: str):
        return self._request("GET", path)

    def post(self, path: str, body=None):
        return self._request("POST", path, body)

    def patch(self, path: str, body=None):
        return self._request("PATCH", path, body)

    def delete(self, path: str):
        return self._request("DELETE", path)

    def _get_powerbi_token(self) -> str:
        if self._pbi_token_cache and time.time() < self._pbi_token_expiry - 60:
            return self._pbi_token_cache

        from msal import ConfidentialClientApplication

        app = ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(scopes=[POWERBI_SCOPE])
        if "access_token" not in result:
            raise Exception(f"PBI auth failed: {result.get('error_description', result)}")

        self._pbi_token_cache = result["access_token"]
        self._pbi_token_expiry = time.time() + result.get("expires_in", 3600)
        return self._pbi_token_cache

    def _pbi_request(self, method: str, path: str, body=None):
        url = f"{POWERBI_API_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {self._get_powerbi_token()}",
            "Content-Type": "application/json",
        }
        response = requests.request(method, url, headers=headers, json=body)
        if response.status_code == 202:
            return {"status": "Accepted"}
        if response.status_code == 204:
            return None
        if response.status_code >= 400:
            try:
                error = response.json()
            except Exception:
                error = response.text
            return {"error": True, "status": response.status_code, "detail": error}
        try:
            data = response.json()
            if isinstance(data, list):
                return {"value": data}
            return data
        except Exception:
            return {"status": response.status_code, "text": response.text}

    def list_workspaces(self):
        return self.get("/workspaces")

    def get_workspace(self, workspace_id: str):
        return self.get(f"/workspaces/{workspace_id}")

    def list_items(self, workspace_id: str, item_type: str | None = None):
        path = f"/workspaces/{workspace_id}/items"
        if item_type:
            path += f"?type={item_type}"
        return self.get(path)

    def list_connections(self):
        return self.get("/connections")

    def list_semantic_models(self, workspace_id: str):
        return self.get(f"/workspaces/{workspace_id}/semanticModels")

    def get_sm_connections(self, workspace_id: str, sm_id: str):
        return self.get(f"/workspaces/{workspace_id}/semanticModels/{sm_id}/connections")

    def bind_sm_connection(
        self,
        workspace_id: str,
        sm_id: str,
        connection_id: str | None,
        connection_type: str = "SQL",
        connection_path: str | None = None,
    ):
        if connection_id and connection_path:
            body = {
                "connectionBinding": {
                    "id": connection_id,
                    "connectivityType": "ShareableCloud",
                    "connectionDetails": {"type": connection_type, "path": connection_path},
                }
            }
        elif connection_path:
            body = {
                "connectionBinding": {
                    "connectivityType": "None",
                    "connectionDetails": {"type": connection_type, "path": connection_path},
                }
            }
        else:
            raise ValueError("bind_sm_connection requires at least connection_path")

        return self.post(
            f"/workspaces/{workspace_id}/semanticModels/{sm_id}/bindConnection",
            body,
        )

    def takeover_dataset(self, workspace_id: str, dataset_id: str):
        return self._pbi_request("POST", f"/groups/{workspace_id}/datasets/{dataset_id}/Default.TakeOver")

    def refresh_dataset(self, workspace_id: str, dataset_id: str):
        return self._pbi_request(
            "POST",
            f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes",
            {"notifyOption": "NoNotification"},
        )

    def get_refresh_history(self, workspace_id: str, dataset_id: str, top: int = 10):
        return self._pbi_request(
            "GET", f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top={top}"
        )
