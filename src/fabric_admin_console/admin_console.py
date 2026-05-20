"""
Fabric Admin Console

Public-safe interactive CLI for Microsoft Fabric administration.
"""

from __future__ import annotations

import base64
import json
import os
import time

from .capacity_metrics import show_all
from .fabric_client import FabricClient


class C:
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
REQUIRED_ENV_VARS = (
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
)


def banner():
    os.system("cls" if os.name == "nt" else "clear")
    print(
        f"""
{C.CYAN}{C.BOLD}+--------------------------------------------------------------+
|                   FABRIC ADMIN CONSOLE                      |
|                     public-safe starter                     |
+--------------------------------------------------------------+{C.END}
"""
    )


def prompt(text, default=None):
    suffix = f" [{default}]" if default else ""
    value = input(f"  {C.YELLOW}>{C.END} {text}{suffix}: ").strip()
    return value if value else default


def confirm(text, default="n"):
    value = prompt(f"{text} (y/n)", default)
    return bool(value and value.lower().startswith("y"))


def info(text):
    print(f"  {C.BLUE}i{C.END} {text}")


def ok(text):
    print(f"  {C.GREEN}+{C.END} {text}")


def warn(text):
    print(f"  {C.YELLOW}!{C.END} {text}")


def fail(text):
    print(f"  {C.RED}x{C.END} {text}")


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
        warn("No items found.")
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
        fail("Invalid choice.")


def pick_workspace(client, title="Select workspace"):
    result = client.list_workspaces()
    return pick_from_list(safe_values(result), lambda w: w["displayName"], title)


def pick_pipeline(client, workspace_id, title="Select pipeline"):
    result = client.list_items(workspace_id, "DataPipeline")
    return pick_from_list(safe_values(result), lambda p: p["displayName"], title)


def pick_semantic_model(client, workspace_id, title="Select semantic model"):
    result = client.list_semantic_models(workspace_id)
    return pick_from_list(safe_values(result), lambda m: m["displayName"], title)


def get_required_env_status(env=None):
    current_env = env or os.environ
    return [(name, bool(current_env.get(name))) for name in REQUIRED_ENV_VARS]


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


def resolve_best_folder_id(folder_fields):
    for key in ("folderId", "folder.id", "metadata.folder.id", "properties.folder.id", "subfolderId"):
        value = folder_fields.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def normalize_path(path):
    normalized = path.strip().replace("\\", "/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    if len(normalized) > 1:
        normalized = normalized.rstrip("/")
    return normalized.casefold()


def get_deployment_config_issues(source_env, target_env):
    issues = []
    if not DEPLOY_PIPELINE_ID:
        issues.append("DEPLOY_PIPELINE_ID is not configured")
    for env_name in (source_env, target_env):
        if not DEPLOY_STAGES.get(env_name):
            issues.append(f"STAGE_{env_name} is not configured")
    return issues


def deployment_item_name(item):
    return item.get("itemDisplayName") or item.get("displayName") or item.get("name") or "?"


def deployment_item_type(item):
    return item.get("itemType") or item.get("type") or "?"


def compare_deployment_items(source_items, target_items):
    source_map = {deployment_item_name(item): item for item in source_items}
    target_map = {deployment_item_name(item): item for item in target_items}
    names = sorted(set(source_map) | set(target_map))
    return {
        "new": [name for name in names if name in source_map and name not in target_map],
        "updated": [name for name in names if name in source_map and name in target_map],
        "orphaned": [name for name in names if name not in source_map and name in target_map],
    }


def default_deploy_options():
    return {
        "allowOverrideItems": True,
        "allowCreateNewItems": True,
        "allowPurgeData": False,
    }


def build_deploy_body(source_stage_id, target_stage_id, note="", items=None):
    body = {
        "sourceStageId": source_stage_id,
        "targetStageId": target_stage_id,
        "note": note,
        "options": default_deploy_options(),
    }
    if items:
        body["items"] = items
    return body


def build_deploy_items(items):
    return [
        {
            "sourceItemId": item["itemId"],
            "itemType": deployment_item_type(item),
        }
        for item in items
    ]


def split_smart_deploy_items(items):
    excluded_types = {"Warehouse", "Lakehouse", "SQLEndpoint"}
    excluded_model_names = {"ENTERPRISE_LAKEHOUSE", "ENTERPRISE_WAREHOUSE"}
    deployable = []
    excluded = []
    for item in items:
        item_type = deployment_item_type(item)
        item_name = deployment_item_name(item)
        if item_type in excluded_types:
            excluded.append(item)
        elif item_type == "SemanticModel" and item_name in excluded_model_names:
            excluded.append(item)
        else:
            deployable.append(item)
    return deployable, excluded


def build_item_key_map(items):
    result = {}
    for item in items:
        item_type = item.get("type") or item.get("itemType") or "?"
        item_name = item.get("displayName") or item.get("itemDisplayName") or "?"
        result[(item_type, item_name)] = item
    return result


def compare_workspace_items(source_items, target_items):
    source_by_key = build_item_key_map(source_items)
    target_by_key = build_item_key_map(target_items)
    all_keys = sorted(set(source_by_key) | set(target_by_key))
    source_names = {}
    target_names = {}
    for item_type, item_name in source_by_key:
        source_names.setdefault(item_name, set()).add(item_type)
    for item_type, item_name in target_by_key:
        target_names.setdefault(item_name, set()).add(item_type)

    type_mismatches = []
    for item_name in sorted(set(source_names) | set(target_names)):
        source_types = source_names.get(item_name, set())
        target_types = target_names.get(item_name, set())
        if source_types and target_types and source_types != target_types:
            type_mismatches.append((item_name, source_types, target_types))

    return {
        "only_source": [key for key in all_keys if key in source_by_key and key not in target_by_key],
        "only_target": [key for key in all_keys if key not in source_by_key and key in target_by_key],
        "both": [key for key in all_keys if key in source_by_key and key in target_by_key],
        "type_mismatches": type_mismatches,
    }


def detect_folder_path_collisions(items):
    by_norm = {}
    for item in items:
        fields = extract_folder_fields(item)
        path = resolve_best_path(fields)
        if not path:
            continue
        by_norm.setdefault(normalize_path(path), []).append(
            (path, item.get("displayName", "?"), item.get("id", item.get("itemId", "?")))
        )
    return [
        (norm, rows)
        for norm, rows in sorted(by_norm.items())
        if len({row[0] for row in rows}) > 1
    ]


def show_workspace_overview(client):
    print(f"\n{C.BOLD}{C.CYAN}-- Workspaces ----------------------------------------{C.END}\n")
    workspaces = safe_values(client.list_workspaces())
    for workspace in workspaces:
        print(f"  {workspace['displayName']}  {C.DIM}{workspace['id']}{C.END}")


def show_capacity_dashboard(client):
    print(f"\n{C.BOLD}{C.CYAN}-- Capacity Metrics ----------------------------------{C.END}\n")
    show_all(client._get_token())


def run_doctor(client):
    print(f"\n{C.BOLD}{C.CYAN}-- Doctor --------------------------------------------{C.END}\n")

    all_good = True
    for name, present in get_required_env_status():
        if present:
            ok(f"{name} is set")
        else:
            fail(f"{name} is missing")
            all_good = False

    for alias, workspace_id in WORKSPACES.items():
        if workspace_id:
            ok(f"Workspace alias {alias} is configured")
        else:
            warn(f"Workspace alias {alias} is not configured")

    try:
        client._get_token()
        ok("Fabric API token acquired")
    except Exception as exc:
        fail(f"Fabric API auth failed: {exc}")
        return

    try:
        client._get_powerbi_token()
        ok("Power BI token acquired")
    except Exception as exc:
        warn(f"Power BI auth unavailable: {exc}")
        all_good = False

    try:
        workspaces = safe_values(client.list_workspaces())
        ok(f"Fabric workspace access verified ({len(workspaces)} workspace(s) visible)")
    except Exception as exc:
        fail(f"Workspace enumeration failed: {exc}")
        all_good = False

    if DEPLOY_PIPELINE_ID:
        ok("Deployment pipeline ID is configured")
    else:
        warn("Deployment pipeline ID is not configured")

    if all_good:
        ok("Doctor check completed with no blocking issues.")
    else:
        warn("Doctor check found at least one issue worth fixing before deeper workflows.")


def cmd_pipelines(client):
    while True:
        print(
            f"""
  {C.BOLD}PIPELINES{C.END}

    {C.CYAN}1{C.END}  List pipelines                   Show pipelines in one workspace
    {C.CYAN}2{C.END}  Run pipeline                    Start a pipeline run
    {C.CYAN}3{C.END}  Monitor job                     Poll a job instance until terminal state
    {C.CYAN}4{C.END}  Show pipeline definition        Decode pipeline-content.json
    {C.DIM}  0  Back{C.END}
"""
        )
        choice = prompt("Choice")
        if choice == "0" or choice is None:
            return

        if choice == "1":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            pipelines = safe_values(client.list_items(workspace["id"], "DataPipeline"))
            print(f"\n  {C.BOLD}Pipelines in {workspace['displayName']}{C.END}\n")
            for index, pipeline in enumerate(pipelines, 1):
                print(f"    {index:3d}  {pipeline['displayName']}  {C.DIM}{pipeline['id']}{C.END}")

        elif choice == "2":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            pipeline = pick_pipeline(client, workspace["id"], "Which pipeline to run?")
            if not pipeline:
                continue
            result = client.run_pipeline(workspace["id"], pipeline["id"])
            if result and not result.get("error"):
                ok(f"Pipeline run started for {pipeline['displayName']}")
                show_json(result)
            else:
                fail(f"Pipeline run failed: {result}")

        elif choice == "3":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            pipeline = pick_pipeline(client, workspace["id"], "Which pipeline?")
            if not pipeline:
                continue
            job_id = prompt("Job Instance ID")
            if not job_id:
                continue
            info("Polling every 5 seconds. Press Ctrl+C to stop.")
            try:
                while True:
                    status = client.get_job_status(workspace["id"], pipeline["id"], job_id)
                    state = status.get("status", "Unknown") if isinstance(status, dict) else "Unknown"
                    print(f"    {time.strftime('%H:%M:%S')}  Status: {state}")
                    if state in ("Completed", "Succeeded", "Failed", "Cancelled"):
                        show_json(status)
                        break
                    time.sleep(5)
            except KeyboardInterrupt:
                print()
                warn("Polling cancelled.")

        elif choice == "4":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            pipeline = pick_pipeline(client, workspace["id"], "Which pipeline?")
            if not pipeline:
                continue
            result = client.get_pipeline_definition(workspace["id"], pipeline["id"])
            if result and result.get("error"):
                fail(f"Definition fetch failed: {result}")
                continue

            definition = result.get("definition", result.get("operation", {}).get("definition", {}))
            parts = definition.get("parts", [])
            found = False
            for part in parts:
                if part.get("path") == "pipeline-content.json":
                    decoded = json.loads(base64.b64decode(part["payload"]).decode())
                    show_json(decoded)
                    found = True
                    break
            if not found:
                warn("No pipeline-content.json part found in definition payload.")

        else:
            fail("Invalid option.")


def _print_deployment_errors(result):
    operation = result.get("operation", {}) if isinstance(result, dict) else {}
    error = operation.get("error", {}) if isinstance(operation, dict) else {}
    if not error:
        show_json(result)
        return
    fail(f"{error.get('errorCode', '')} - {error.get('message', '')}")
    for detail in error.get("moreDetails", []):
        fail(f"  {detail.get('errorCode', '')}: {detail.get('message', '')}")
        for key in ("resourceType", "resourceId", "additionalInfo"):
            if key in detail:
                info(f"  {key}: {detail[key]}")


def _deployment_direction_from_choice(choice):
    if choice in ("1", "3"):
        return "DEV", "PILOT"
    if choice in ("2", "4"):
        return "PILOT", "PROD"
    return None, None


def cmd_deployments(client):
    while True:
        print(
            f"""
  {C.BOLD}DEPLOYMENTS{C.END}

    {C.CYAN}1{C.END}  Compare DEV vs PILOT             Preview stage differences
    {C.CYAN}2{C.END}  Compare PILOT vs PROD            Preview stage differences
    {C.CYAN}3{C.END}  Deploy DEV -> PILOT              Promote all deployment-pipeline items
    {C.CYAN}4{C.END}  Deploy PILOT -> PROD             Promote all deployment-pipeline items
    {C.CYAN}5{C.END}  Smart deploy                     Exclude unsupported item types first
    {C.CYAN}6{C.END}  Workspace item diff              Compare all items between two workspaces
    {C.CYAN}7{C.END}  Folder conflict scan             Find folder path collisions
    {C.DIM}  0  Back{C.END}
"""
        )
        choice = prompt("Choice")
        if choice == "0" or choice is None:
            return

        if choice in ("1", "2"):
            source_env, target_env = _deployment_direction_from_choice(choice)
            issues = get_deployment_config_issues(source_env, target_env)
            if issues:
                for issue in issues:
                    fail(issue)
                continue
            source_items = safe_values(
                client.get_deployment_stage_items(DEPLOY_PIPELINE_ID, DEPLOY_STAGES[source_env])
            )
            target_items = safe_values(
                client.get_deployment_stage_items(DEPLOY_PIPELINE_ID, DEPLOY_STAGES[target_env])
            )
            diff = compare_deployment_items(source_items, target_items)
            print(f"\n  {C.BOLD}{source_env} -> {target_env}{C.END}")
            print(f"    New: {len(diff['new'])}  Updated: {len(diff['updated'])}  Orphaned: {len(diff['orphaned'])}\n")
            for label, names in (("NEW", diff["new"]), ("UPDATED", diff["updated"]), ("ORPHANED", diff["orphaned"])):
                if names:
                    print(f"  {C.BOLD}{label}{C.END}")
                    for name in names:
                        print(f"    - {name}")

        elif choice in ("3", "4"):
            source_env, target_env = _deployment_direction_from_choice(choice)
            issues = get_deployment_config_issues(source_env, target_env)
            if issues:
                for issue in issues:
                    fail(issue)
                continue
            warn(f"Deploy ALL items from {source_env} -> {target_env}")
            if not confirm("Proceed?"):
                continue
            note = prompt("Deployment note", f"{source_env} -> {target_env}")
            body = build_deploy_body(DEPLOY_STAGES[source_env], DEPLOY_STAGES[target_env], note=note)
            result = client.deploy_stage(DEPLOY_PIPELINE_ID, body)
            if result and result.get("error"):
                fail(f"Deployment {source_env} -> {target_env} failed")
                _print_deployment_errors(result)
            else:
                ok(f"Deployment {source_env} -> {target_env} submitted")
                show_json(result)

        elif choice == "5":
            direction = pick_from_list(
                [{"source": "DEV", "target": "PILOT"}, {"source": "PILOT", "target": "PROD"}],
                lambda item: f"{item['source']} -> {item['target']}",
                "Direction",
            )
            if not direction:
                continue
            source_env = direction["source"]
            target_env = direction["target"]
            issues = get_deployment_config_issues(source_env, target_env)
            if issues:
                for issue in issues:
                    fail(issue)
                continue
            all_items = safe_values(
                client.get_deployment_stage_items(DEPLOY_PIPELINE_ID, DEPLOY_STAGES[source_env])
            )
            deployable, excluded = split_smart_deploy_items(all_items)
            print(f"\n  Deployable: {len(deployable)}  Excluded: {len(excluded)}\n")
            if excluded:
                print(f"  {C.YELLOW}Excluded{C.END}")
                for item in excluded:
                    print(f"    - {deployment_item_type(item)}: {deployment_item_name(item)}")
            if not deployable:
                warn("No deployable items found.")
                continue
            if not confirm(f"Deploy {len(deployable)} item(s) from {source_env} -> {target_env}?"):
                continue
            note = prompt("Deployment note", f"Smart deploy {source_env} -> {target_env}")
            body = build_deploy_body(
                DEPLOY_STAGES[source_env],
                DEPLOY_STAGES[target_env],
                note=note,
                items=build_deploy_items(deployable),
            )
            result = client.deploy_stage(DEPLOY_PIPELINE_ID, body)
            if result and result.get("error"):
                fail("Smart deploy failed")
                _print_deployment_errors(result)
            else:
                ok(f"Smart deploy submitted with {len(deployable)} item(s)")
                show_json(result)

        elif choice == "6":
            source = pick_from_list([{"name": name} for name in WORKSPACES], lambda item: item["name"], "Source")
            if not source:
                continue
            target = pick_from_list([{"name": name} for name in WORKSPACES], lambda item: item["name"], "Target")
            if not target:
                continue
            source_ws = WORKSPACES.get(source["name"])
            target_ws = WORKSPACES.get(target["name"])
            if not source_ws or not target_ws:
                fail("Both workspace aliases must be configured.")
                continue
            source_items = safe_values(client.list_items(source_ws))
            target_items = safe_values(client.list_items(target_ws))
            diff = compare_workspace_items(source_items, target_items)
            print(f"\n  {C.BOLD}{source['name']} vs {target['name']}{C.END}")
            print(
                f"    Matched: {len(diff['both'])}  "
                f"Only source: {len(diff['only_source'])}  "
                f"Only target: {len(diff['only_target'])}  "
                f"Type mismatches: {len(diff['type_mismatches'])}"
            )
            if diff["type_mismatches"]:
                print(f"\n  {C.RED}Type mismatches{C.END}")
                for name, source_types, target_types in diff["type_mismatches"]:
                    print(f"    - {name}: {sorted(source_types)} vs {sorted(target_types)}")

        elif choice == "7":
            workspace = pick_workspace(client, "Workspace to scan")
            if not workspace:
                continue
            items = safe_values(client.list_items(workspace["id"]))
            collisions = detect_folder_path_collisions(items)
            if not collisions:
                ok("No folder path collisions found from item metadata.")
                continue
            print(f"\n  {C.RED}Folder path collisions: {len(collisions)}{C.END}\n")
            for norm, rows in collisions[:50]:
                print(f"    NORMALIZED: {norm}")
                for raw, name, item_id in rows:
                    print(f"      RAW: {raw!r} | {name} | {item_id}")

        else:
            fail("Invalid option.")


def cmd_semantic_models(client):
    while True:
        print(
            f"""
  {C.BOLD}SEMANTIC MODELS{C.END}

    {C.CYAN}1{C.END}  List semantic models             Show semantic models in a workspace
    {C.CYAN}2{C.END}  Show refresh history            Display recent refresh runs
    {C.DIM}  0  Back{C.END}
"""
        )
        choice = prompt("Choice")
        if choice == "0" or choice is None:
            return

        if choice == "1":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            models = safe_values(client.list_semantic_models(workspace["id"]))
            print(f"\n  {C.BOLD}Semantic models in {workspace['displayName']}{C.END}\n")
            if not models:
                warn("No semantic models found.")
                continue
            for index, model in enumerate(models, 1):
                print(f"    {index:3d}  {model['displayName']}  {C.DIM}{model['id']}{C.END}")

        elif choice == "2":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            model = pick_semantic_model(client, workspace["id"], "Which semantic model?")
            if not model:
                continue
            history = safe_values(client.get_refresh_history(workspace["id"], model["id"]))
            print(f"\n  {C.BOLD}Refresh history: {model['displayName']}{C.END}\n")
            if not history:
                warn("No refresh history found.")
                continue
            for run in history:
                start = str(run.get("startTime", "?"))[:19].replace("T", " ")
                end = str(run.get("endTime", ""))
                end = end[:19].replace("T", " ") if end else "-"
                status = run.get("status", "?")
                rtype = run.get("refreshType", "?")
                print(f"    {start:<20} {end:<20} {rtype:<12} {status}")

        else:
            fail("Invalid option.")


def main():
    banner()
    try:
        client = FabricClient()
        ok("Authenticated to Fabric API")
    except Exception as exc:
        fail(f"Auth failed: {exc}")
        raise SystemExit(1) from exc

    while True:
        print(
            f"""
  {C.BOLD}MAIN MENU{C.END}

    {C.CYAN}1{C.END}  Doctor             Validate config and access
    {C.CYAN}2{C.END}  Workspaces         View accessible workspaces
    {C.CYAN}3{C.END}  Pipelines          List and run Fabric pipelines
    {C.CYAN}4{C.END}  Deployments        Compare, deploy, and diagnose environment differences
    {C.CYAN}5{C.END}  Semantic Models    Inspect models and refresh history
    {C.CYAN}6{C.END}  Capacity           Show capacity metrics dashboard
    {C.CYAN}7{C.END}  Raw workspace JSON Inspect one workspace record
    {C.DIM}  0  Exit{C.END}
"""
        )
        choice = prompt("Choice")
        if choice == "0" or choice is None:
            print(f"\n  {C.CYAN}Goodbye.{C.END}\n")
            return
        if choice == "1":
            run_doctor(client)
        elif choice == "2":
            show_workspace_overview(client)
        elif choice == "3":
            cmd_pipelines(client)
        elif choice == "4":
            cmd_deployments(client)
        elif choice == "5":
            cmd_semantic_models(client)
        elif choice == "6":
            show_capacity_dashboard(client)
        elif choice == "7":
            workspace = pick_workspace(client)
            if workspace:
                show_json(workspace)
        else:
            fail("Invalid option.")


if __name__ == "__main__":
    main()
