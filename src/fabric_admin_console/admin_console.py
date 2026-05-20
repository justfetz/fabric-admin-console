"""
Fabric Admin Console

Public-safe interactive CLI for Microsoft Fabric administration.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .capacity_metrics import show_all
from .fabric_client import FabricClient


class C:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"


WORKSPACES = {
    "DEV": os.getenv("WS_DEV", ""),
    "PILOT": os.getenv("WS_PILOT", ""),
    "PROD": os.getenv("WS_PROD", ""),
}

DEPLOY_PIPELINE_ID = os.getenv("DEPLOY_PIPELINE_ID", "")
DEPLOY_STAGES = {
    "DEV": os.getenv("STAGE_DEV", ""),
    "PILOT": os.getenv("STAGE_PILOT", ""),
    "PROD": os.getenv("STAGE_PROD", ""),
}
REPO_ROOT = os.getenv("REPO_ROOT", os.getcwd())

FOLDER_KEYS_TOPLEVEL = (
    "folderId",
    "parentFolderId",
    "folderPath",
    "path",
    "parentPath",
    "subfolderId",
)
FOLDER_KEYS_NESTED = (
    ("folder", "id"),
    ("folder", "path"),
    ("folder", "name"),
    ("folder", "parentId"),
    ("folder", "parentPath"),
    ("parentFolder", "id"),
    ("parentFolder", "path"),
    ("parentFolder", "name"),
)


def banner():
    os.system("cls" if os.name == "nt" else "clear")
    print(
        f"""
{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════════════════════╗
║                   FABRIC ADMIN CONSOLE                       ║
║                      public-safe starter                     ║
╚══════════════════════════════════════════════════════════════╝{C.END}
"""
    )


def prompt(text, default=None):
    suffix = f" [{default}]" if default else ""
    value = input(f"  {C.YELLOW}>{C.END} {text}{suffix}: ").strip()
    return value if value else default


def safe_values(result):
    if isinstance(result, dict):
        return result.get("value", [])
    if isinstance(result, list):
        return result
    return []


def show_json(data):
    print(json.dumps(data, indent=2, default=str))


def pick_from_list(items, label_fn, title="Select"):
    if not items:
        print(f"  {C.YELLOW}No items found.{C.END}")
        return None
    print(f"\n  {C.BOLD}{title}{C.END}")
    for index, item in enumerate(items, 1):
        print(f"    {C.CYAN}{index:3d}{C.END}  {label_fn(item)}")
    print(f"    {C.DIM}  0  Cancel{C.END}\n")
    while True:
        choice = prompt("Choice")
        if choice == "0" or choice is None:
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                return items[idx]
        except (ValueError, IndexError):
            pass
        print(f"  {C.RED}Invalid choice.{C.END}")


def pick_workspace(client, title="Select workspace"):
    result = client.list_workspaces()
    return pick_from_list(safe_values(result), lambda w: w["displayName"], title)


def _get_nested_val(data, *keys):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def extract_folder_fields(item):
    output = {}
    for key in FOLDER_KEYS_TOPLEVEL:
        if key in item and item.get(key) not in (None, "", []):
            output[key] = item.get(key)
    for path in FOLDER_KEYS_NESTED:
        value = _get_nested_val(item, *path)
        if value not in (None, "", []):
            output[".".join(path)] = value
    for container_key in ("properties", "metadata"):
        container = item.get(container_key)
        if isinstance(container, dict):
            for key in FOLDER_KEYS_TOPLEVEL:
                if key in container and container.get(key) not in (None, "", []):
                    output[f"{container_key}.{key}"] = container.get(key)
            for path in FOLDER_KEYS_NESTED:
                value = _get_nested_val(container, *path)
                if value not in (None, "", []):
                    output[f"{container_key}." + ".".join(path)] = value
    return output


def resolve_best_path(folder_fields):
    for key in ("folderPath", "folder.path", "metadata.folder.path", "properties.folder.path", "path"):
        if key in folder_fields and isinstance(folder_fields[key], str) and folder_fields[key].strip():
            return folder_fields[key]
    return None


def normalize_path(path):
    normalized = path.strip().replace("\\", "/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized.casefold()


def show_workspace_overview(client):
    print(f"\n{C.BOLD}{C.CYAN}── Workspaces ─────────────────────────────────────────────{C.END}\n")
    workspaces = safe_values(client.list_workspaces())
    for workspace in workspaces:
        print(f"  {workspace['displayName']}  {C.DIM}{workspace['id']}{C.END}")


def show_capacity_dashboard(client):
    print(f"\n{C.BOLD}{C.CYAN}── Capacity Metrics ─────────────────────────────────────{C.END}\n")
    show_all(client._get_token())


def main():
    banner()
    try:
        client = FabricClient()
        print(f"  {C.GREEN}✓{C.END} Authenticated to Fabric API\n")
    except Exception as exc:
        print(f"  {C.RED}✗{C.END} Auth failed: {exc}")
        raise SystemExit(1) from exc

    while True:
        print(
            f"""
  {C.BOLD}MAIN MENU{C.END}

    {C.CYAN}1{C.END}  Workspaces         View accessible workspaces
    {C.CYAN}2{C.END}  Capacity           Show capacity metrics dashboard
    {C.CYAN}3{C.END}  Raw workspace JSON Inspect one workspace record
    {C.DIM}  0  Exit{C.END}
"""
        )
        choice = prompt("Choice")
        if choice == "0" or choice is None:
            print(f"\n  {C.CYAN}Goodbye.{C.END}\n")
            return
        if choice == "1":
            show_workspace_overview(client)
        elif choice == "2":
            show_capacity_dashboard(client)
        elif choice == "3":
            workspace = pick_workspace(client)
            if workspace:
                show_json(workspace)
        else:
            print(f"  {C.RED}Invalid option.{C.END}")


if __name__ == "__main__":
    main()
