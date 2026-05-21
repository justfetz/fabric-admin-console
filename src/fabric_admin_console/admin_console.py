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
from .config import FabricAdminConfig, FabricEnvironment, get_config_path, load_admin_config, save_admin_config
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


def get_active_config():
    return load_admin_config()


def get_active_workspaces(config=None):
    return (config or get_active_config()).workspaces()


def get_active_deploy_stages(config=None):
    return (config or get_active_config()).stages()


def get_active_deploy_pipeline_id(config=None):
    return (config or get_active_config()).deployment_pipeline_id


def configured_environment_names(config=None):
    return [env.name for env in (config or get_active_config()).environments]


def configured_workspace_count(config=None):
    return sum(1 for value in get_active_workspaces(config).values() if value)


def should_offer_setup(config=None):
    return configured_workspace_count(config) == 0


def print_config_summary(config=None):
    active_config = config or get_active_config()
    print(f"\n  {C.BOLD}Active configuration{C.END}\n")
    print(f"    Config file: {get_config_path()}")
    print(f"    Deployment pipeline ID: {get_active_deploy_pipeline_id(active_config) or '-'}")
    for env in active_config.environments:
        workspace = env.workspace_id or "-"
        stage = env.stage_id or "-"
        print(f"    {env.name:<12} workspace={workspace}  stage={stage}")


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


def get_deployment_config_issues(source_env, target_env, config=None):
    deployment_pipeline_id = get_active_deploy_pipeline_id(config)
    stages = get_active_deploy_stages(config)
    issues = []
    if not deployment_pipeline_id:
        issues.append("DEPLOY_PIPELINE_ID is not configured")
    for env_name in (source_env, target_env):
        if not stages.get(env_name):
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


def semantic_model_connection_name(connection):
    return (
        connection.get("displayName")
        or connection.get("name")
        or connection.get("id")
        or "?"
    )


def semantic_model_connection_path(connection):
    details = connection.get("connectionDetails")
    if isinstance(details, dict):
        path = details.get("path")
        if isinstance(path, str) and path.strip():
            return path
    path = connection.get("path")
    if isinstance(path, str) and path.strip():
        return path
    return ""


def semantic_model_connection_type(connection, default="SQL"):
    details = connection.get("connectionDetails")
    if isinstance(details, dict):
        ctype = details.get("type")
        if isinstance(ctype, str) and ctype.strip():
            return ctype
    ctype = connection.get("type")
    if isinstance(ctype, str) and ctype.strip():
        return ctype
    return default


def semantic_model_connection_label(connection):
    name = semantic_model_connection_name(connection)
    ctype = semantic_model_connection_type(connection)
    path = semantic_model_connection_path(connection)
    tail = f" | {path}" if path else ""
    return f"{name} [{ctype}]{tail}"


def print_semantic_model_connections(connections, title):
    print(f"\n  {C.BOLD}{title}{C.END}\n")
    if not connections:
        warn("No connections found.")
        return
    for index, connection in enumerate(connections, 1):
        name = semantic_model_connection_name(connection)
        ctype = semantic_model_connection_type(connection)
        path = semantic_model_connection_path(connection) or "-"
        conn_id = connection.get("id", "-")
        print(f"    {index:3d}  {name:<28} {ctype:<10} {path}")
        print(f"         {C.DIM}{conn_id}{C.END}")


def print_refresh_history_runs(history, model_name):
    print(f"\n  {C.BOLD}Refresh history: {model_name}{C.END}\n")
    if not history:
        warn("No refresh history found.")
        return
    for run in history:
        start = str(run.get("startTime", "?"))[:19].replace("T", " ")
        end = str(run.get("endTime", ""))
        end = end[:19].replace("T", " ") if end else "-"
        status = run.get("status", "?")
        rtype = run.get("refreshType", "?")
        print(f"    {start:<20} {end:<20} {rtype:<12} {status}")


def git_connection_summary(connection):
    if not isinstance(connection, dict):
        return {"provider": "?", "repository": "?", "branch": "?", "directory": "/"}
    details = connection.get("gitProviderDetails") if isinstance(connection.get("gitProviderDetails"), dict) else {}
    return {
        "provider": connection.get("gitProviderType") or details.get("provider") or "?",
        "repository": details.get("repositoryName") or details.get("repository") or connection.get("repositoryName") or "?",
        "branch": connection.get("branchName") or details.get("branchName") or details.get("branch") or "?",
        "directory": connection.get("directoryName") or details.get("directoryName") or "/",
    }


def git_change_identifier(change):
    return change.get("itemId") or change.get("objectId") or change.get("path") or "?"


def git_change_label(change):
    item_type = change.get("itemType") or change.get("type") or "?"
    display_name = change.get("displayName") or change.get("name") or git_change_identifier(change)
    workspace_state = change.get("workspaceChange") or change.get("workspaceState") or "-"
    remote_state = change.get("remoteChange") or change.get("remoteState") or "-"
    return f"{item_type}: {display_name} | workspace={workspace_state} remote={remote_state}"


def git_status_changes(status):
    if not isinstance(status, dict):
        return []
    for key in ("changes", "value", "items"):
        value = status.get(key)
        if isinstance(value, list):
            return value
    return []


def build_commit_to_git_body(comment, changes=None):
    body = {"mode": "All", "comment": comment}
    if changes:
        body["mode"] = "Selective"
        body["items"] = [{"itemId": git_change_identifier(change)} for change in changes]
    return body


def build_update_from_git_body(remote_commit_hash=None, conflict_resolution_policy="PreferRemote"):
    body = {"conflictResolution": {"conflictResolutionType": conflict_resolution_policy}}
    if remote_commit_hash:
        body["remoteCommitHash"] = remote_commit_hash
    return body


def select_git_changes(changes, raw_indexes):
    selected = []
    for raw_index in (raw_indexes or "").replace(";", ",").split(","):
        raw_index = raw_index.strip()
        if not raw_index:
            continue
        try:
            idx = int(raw_index) - 1
        except ValueError:
            continue
        if 0 <= idx < len(changes):
            selected.append(changes[idx])
    return selected


def pipeline_terminal_state(status):
    if not isinstance(status, dict):
        return "Unknown"
    return status.get("status", "Unknown")


def decode_pipeline_definition_payload(result):
    if not isinstance(result, dict):
        return None
    if result.get("error"):
        return None
    definition = result.get("definition", result.get("operation", {}).get("definition", {}))
    parts = definition.get("parts", []) if isinstance(definition, dict) else []
    for part in parts:
        if part.get("path") == "pipeline-content.json":
            return json.loads(base64.b64decode(part["payload"]).decode())
    return None


def print_git_status_changes(changes, title):
    print(f"\n  {C.BOLD}{title}{C.END}\n")
    if not changes:
        warn("No Git changes reported.")
        return
    for index, change in enumerate(changes, 1):
        print(f"    {index:3d}  {git_change_label(change)}")


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


def parse_environment_names(raw_names):
    names = []
    for raw_name in raw_names.replace(";", ",").split(","):
        name = raw_name.strip().upper()
        if name and name not in names:
            names.append(name)
    return names


def cmd_setup():
    print(f"\n{C.BOLD}{C.CYAN}-- Setup ---------------------------------------------{C.END}\n")
    current = get_active_config()
    current_names = ", ".join(env.name for env in current.environments) or "DEV,PILOT,PROD"
    raw_names = prompt("Environment names, comma-separated", current_names)
    names = parse_environment_names(raw_names or "")
    if not names:
        fail("At least one environment name is required.")
        return

    environments = []
    current_by_name = {env.name: env for env in current.environments}
    for name in names:
        existing = current_by_name.get(name, FabricEnvironment(name=name))
        workspace_id = prompt(f"{name} workspace ID", existing.workspace_id)
        stage_id = prompt(f"{name} deployment stage ID (blank if not using deployment pipelines)", existing.stage_id)
        environments.append(
            FabricEnvironment(
                name=name,
                workspace_id=workspace_id or "",
                stage_id=stage_id or "",
            )
        )

    deployment_pipeline_id = prompt(
        "Deployment pipeline ID (blank if not using deployment pipelines)",
        current.deployment_pipeline_id,
    )
    config = FabricAdminConfig(
        deployment_pipeline_id=deployment_pipeline_id or "",
        environments=tuple(environments),
    )
    path = save_admin_config(config)
    ok(f"Saved Fabric Admin Console config to {path}")
    info("Azure tenant/client credentials still belong in .env or environment variables.")
    print_config_summary(config)


def run_doctor(client):
    print(f"\n{C.BOLD}{C.CYAN}-- Doctor --------------------------------------------{C.END}\n")
    info(f"Local config path: {get_config_path()}")

    all_good = True
    for name, present in get_required_env_status():
        if present:
            ok(f"{name} is set")
        else:
            fail(f"{name} is missing")
            all_good = False

    active_config = get_active_config()
    for alias, workspace_id in get_active_workspaces(active_config).items():
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

    if get_active_deploy_pipeline_id(active_config):
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
                    state = pipeline_terminal_state(status)
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

            decoded = decode_pipeline_definition_payload(result)
            if decoded is None:
                warn("No pipeline-content.json part found in definition payload.")
                continue
            show_json(decoded)

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
    names = configured_environment_names()
    if len(names) < 2:
        return None, None
    if choice in ("1", "3"):
        return names[0], names[1]
    if choice in ("2", "4") and len(names) >= 3:
        return names[1], names[2]
    return None, None


def build_adjacent_environment_pairs(config=None):
    names = configured_environment_names(config)
    return [
        {"source": names[index], "target": names[index + 1]}
        for index in range(len(names) - 1)
    ]


def cmd_deployments(client):
    while True:
        active_config = get_active_config()
        env_pairs = build_adjacent_environment_pairs(active_config)
        first_pair = env_pairs[0] if env_pairs else {"source": "ENV1", "target": "ENV2"}
        second_pair = env_pairs[1] if len(env_pairs) > 1 else None
        second_label = (
            f"Compare {second_pair['source']} vs {second_pair['target']}"
            if second_pair
            else "Compare next environment pair (configure 3+ envs)"
        )
        second_deploy_label = (
            f"Deploy {second_pair['source']} -> {second_pair['target']}"
            if second_pair
            else "Deploy next environment pair (configure 3+ envs)"
        )
        print(
            f"""
  {C.BOLD}DEPLOYMENTS{C.END}

    {C.CYAN}1{C.END}  Compare {first_pair['source']} vs {first_pair['target']}             Preview stage differences
    {C.CYAN}2{C.END}  {second_label:<34} Preview stage differences
    {C.CYAN}3{C.END}  Deploy {first_pair['source']} -> {first_pair['target']}              Promote all deployment-pipeline items
    {C.CYAN}4{C.END}  {second_deploy_label:<34} Promote all deployment-pipeline items
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
            if not source_env or not target_env:
                fail("Configure at least two adjacent environments first.")
                continue
            issues = get_deployment_config_issues(source_env, target_env)
            if issues:
                for issue in issues:
                    fail(issue)
                continue
            deployment_pipeline_id = get_active_deploy_pipeline_id()
            stages = get_active_deploy_stages()
            source_items = safe_values(
                client.get_deployment_stage_items(deployment_pipeline_id, stages[source_env])
            )
            target_items = safe_values(
                client.get_deployment_stage_items(deployment_pipeline_id, stages[target_env])
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
            if not source_env or not target_env:
                fail("Configure at least two adjacent environments first.")
                continue
            issues = get_deployment_config_issues(source_env, target_env)
            if issues:
                for issue in issues:
                    fail(issue)
                continue
            deployment_pipeline_id = get_active_deploy_pipeline_id()
            stages = get_active_deploy_stages()
            warn(f"Deploy ALL items from {source_env} -> {target_env}")
            if not confirm("Proceed?"):
                continue
            note = prompt("Deployment note", f"{source_env} -> {target_env}")
            body = build_deploy_body(stages[source_env], stages[target_env], note=note)
            result = client.deploy_stage(deployment_pipeline_id, body)
            if result and result.get("error"):
                fail(f"Deployment {source_env} -> {target_env} failed")
                _print_deployment_errors(result)
            else:
                ok(f"Deployment {source_env} -> {target_env} submitted")
                show_json(result)

        elif choice == "5":
            env_pairs = build_adjacent_environment_pairs()
            if not env_pairs:
                fail("Configure at least two adjacent environments first.")
                continue
            direction = pick_from_list(
                env_pairs,
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
            deployment_pipeline_id = get_active_deploy_pipeline_id()
            stages = get_active_deploy_stages()
            all_items = safe_values(
                client.get_deployment_stage_items(deployment_pipeline_id, stages[source_env])
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
                stages[source_env],
                stages[target_env],
                note=note,
                items=build_deploy_items(deployable),
            )
            result = client.deploy_stage(deployment_pipeline_id, body)
            if result and result.get("error"):
                fail("Smart deploy failed")
                _print_deployment_errors(result)
            else:
                ok(f"Smart deploy submitted with {len(deployable)} item(s)")
                show_json(result)

        elif choice == "6":
            workspaces = get_active_workspaces()
            source = pick_from_list([{"name": name} for name in workspaces], lambda item: item["name"], "Source")
            if not source:
                continue
            target = pick_from_list([{"name": name} for name in workspaces], lambda item: item["name"], "Target")
            if not target:
                continue
            source_ws = workspaces.get(source["name"])
            target_ws = workspaces.get(target["name"])
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
    {C.CYAN}2{C.END}  Show model connections          Inspect current bindings on one model
    {C.CYAN}3{C.END}  List shared connections         Show tenant-level reusable connections
    {C.CYAN}4{C.END}  Bind model connection           Rebind one model to a selected connection or path
    {C.CYAN}5{C.END}  Take over model                 Take ownership through Power BI dataset API
    {C.CYAN}6{C.END}  Refresh model                   Trigger a refresh through Power BI dataset API
    {C.CYAN}7{C.END}  Show refresh history            Display recent refresh runs
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
            connections = safe_values(client.get_sm_connections(workspace["id"], model["id"]))
            print_semantic_model_connections(
                connections,
                f"Connections for {model['displayName']}",
            )

        elif choice == "3":
            connections = safe_values(client.list_connections())
            print_semantic_model_connections(connections, "Tenant shared connections")

        elif choice == "4":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            model = pick_semantic_model(client, workspace["id"], "Which semantic model?")
            if not model:
                continue
            current_connections = safe_values(client.get_sm_connections(workspace["id"], model["id"]))
            if current_connections:
                print_semantic_model_connections(
                    current_connections,
                    f"Current bindings for {model['displayName']}",
                )
            use_existing = confirm("Use an existing shared connection?", "y")
            if use_existing:
                connections = safe_values(client.list_connections())
                if not connections:
                    warn("No shared connections available.")
                    continue
                connection = pick_from_list(
                    connections,
                    semantic_model_connection_label,
                    "Select shared connection",
                )
                if not connection:
                    continue
                default_path = semantic_model_connection_path(connection)
                connection_path = prompt(
                    "Connection path (server/database or equivalent)",
                    default_path,
                )
                if not connection_path:
                    fail("Connection path is required.")
                    continue
                connection_type = semantic_model_connection_type(connection)
                result = client.bind_sm_connection(
                    workspace["id"],
                    model["id"],
                    connection.get("id"),
                    connection_type=connection_type,
                    connection_path=connection_path,
                )
            else:
                connection_type = prompt("Connection type", "SQL")
                connection_path = prompt("Connection path (server/database or equivalent)")
                if not connection_path:
                    fail("Connection path is required.")
                    continue
                result = client.bind_sm_connection(
                    workspace["id"],
                    model["id"],
                    None,
                    connection_type=connection_type or "SQL",
                    connection_path=connection_path,
                )
            if result and not result.get("error"):
                ok(f"Connection binding submitted for {model['displayName']}")
                show_json(result)
            else:
                fail(f"Connection binding failed: {result}")

        elif choice == "5":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            model = pick_semantic_model(client, workspace["id"], "Which semantic model?")
            if not model:
                continue
            warn("This uses the Power BI dataset ownership endpoint against the semantic model ID.")
            if not confirm(f"Take over {model['displayName']}?"):
                continue
            result = client.takeover_dataset(workspace["id"], model["id"])
            if result and not result.get("error"):
                ok(f"Takeover submitted for {model['displayName']}")
                show_json(result)
            else:
                fail(f"Takeover failed: {result}")

        elif choice == "6":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            model = pick_semantic_model(client, workspace["id"], "Which semantic model?")
            if not model:
                continue
            if not confirm(f"Trigger a refresh for {model['displayName']}?", "y"):
                continue
            result = client.refresh_dataset(workspace["id"], model["id"])
            if result and not result.get("error"):
                ok(f"Refresh submitted for {model['displayName']}")
                show_json(result)
            else:
                fail(f"Refresh failed: {result}")

        elif choice == "7":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            model = pick_semantic_model(client, workspace["id"], "Which semantic model?")
            if not model:
                continue
            history = safe_values(client.get_refresh_history(workspace["id"], model["id"]))
            print_refresh_history_runs(history, model["displayName"])

        else:
            fail("Invalid option.")


def cmd_workspace_git(client):
    while True:
        print(
            f"""
  {C.BOLD}WORKSPACE GIT{C.END}

    {C.CYAN}1{C.END}  Show Git connection             Inspect provider, repo, branch, and directory
    {C.CYAN}2{C.END}  Show Git status                 Inspect pending workspace/remote differences
    {C.CYAN}3{C.END}  Update from Git                 Pull remote content into the workspace
    {C.CYAN}4{C.END}  Commit all to Git               Push current workspace changes with one comment
    {C.CYAN}5{C.END}  Commit selected changes         Commit only selected changed items
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
            connection = client.get_git_connection(workspace["id"])
            if connection and connection.get("error"):
                fail(f"Git connection lookup failed: {connection}")
                continue
            summary = git_connection_summary(connection)
            print(f"\n  {C.BOLD}Git connection: {workspace['displayName']}{C.END}\n")
            print(f"    Provider   {summary['provider']}")
            print(f"    Repository {summary['repository']}")
            print(f"    Branch     {summary['branch']}")
            print(f"    Directory  {summary['directory']}")

        elif choice == "2":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            status = client.get_git_status(workspace["id"])
            if status and status.get("error"):
                fail(f"Git status failed: {status}")
                continue
            changes = git_status_changes(status)
            print_git_status_changes(changes, f"Git status for {workspace['displayName']}")

        elif choice == "3":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            remote_commit_hash = prompt("Remote commit hash (blank for latest)", "")
            prefer_remote = confirm("Prefer remote changes if conflicts occur?", "y")
            body = build_update_from_git_body(
                remote_commit_hash=remote_commit_hash or None,
                conflict_resolution_policy="PreferRemote" if prefer_remote else "PreferWorkspace",
            )
            warn("Update from Git will apply remote content into this workspace.")
            if not confirm(f"Proceed with update for {workspace['displayName']}?", "n"):
                continue
            result = client.update_from_git(workspace["id"], body)
            if result and not result.get("error"):
                ok(f"Update from Git submitted for {workspace['displayName']}")
                show_json(result)
            else:
                fail(f"Update from Git failed: {result}")

        elif choice == "4":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            comment = prompt("Commit comment", "Workspace sync from Fabric Admin Console")
            body = build_commit_to_git_body(comment)
            if not confirm(f"Commit all changes from {workspace['displayName']} to Git?", "y"):
                continue
            result = client.commit_to_git(workspace["id"], body)
            if result and not result.get("error"):
                ok(f"Commit to Git submitted for {workspace['displayName']}")
                show_json(result)
            else:
                fail(f"Commit to Git failed: {result}")

        elif choice == "5":
            workspace = pick_workspace(client, "Which workspace?")
            if not workspace:
                continue
            status = client.get_git_status(workspace["id"])
            if status and status.get("error"):
                fail(f"Git status failed: {status}")
                continue
            changes = git_status_changes(status)
            if not changes:
                warn("No Git changes available for selective commit.")
                continue
            print_git_status_changes(changes, f"Select changes for {workspace['displayName']}")
            raw_indexes = prompt("Indexes to commit (comma-separated)")
            selected = select_git_changes(changes, raw_indexes)
            if not selected:
                fail("No valid changes selected.")
                continue
            comment = prompt("Commit comment", "Selective workspace sync from Fabric Admin Console")
            body = build_commit_to_git_body(comment, selected)
            if not confirm(f"Commit {len(selected)} selected change(s) from {workspace['displayName']}?", "y"):
                continue
            result = client.commit_to_git(workspace["id"], body)
            if result and not result.get("error"):
                ok(f"Selective commit submitted for {workspace['displayName']}")
                show_json(result)
            else:
                fail(f"Selective commit failed: {result}")

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

    active_config = get_active_config()
    if should_offer_setup(active_config):
        warn("No workspace aliases are configured yet.")
        info("Run Setup once to define the environment names and workspace IDs you actually use.")
        if confirm("Launch Setup now?", "y"):
            cmd_setup()

    while True:
        print(
            f"""
  {C.BOLD}MAIN MENU{C.END}

    {C.CYAN}1{C.END}  Doctor             Validate config and access
    {C.CYAN}2{C.END}  Setup              Configure environment names, workspaces, and stages
    {C.CYAN}3{C.END}  Workspaces         View accessible workspaces
    {C.CYAN}4{C.END}  Pipelines          List and run Fabric pipelines
    {C.CYAN}5{C.END}  Deployments        Compare, deploy, and diagnose environment differences
    {C.CYAN}6{C.END}  Semantic Models    Inspect models and refresh history
    {C.CYAN}7{C.END}  Workspace Git      Inspect and sync Git-connected workspaces
    {C.CYAN}8{C.END}  Capacity           Show capacity metrics dashboard
    {C.CYAN}9{C.END}  Raw workspace JSON Inspect one workspace record
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
            cmd_setup()
        elif choice == "3":
            show_workspace_overview(client)
        elif choice == "4":
            cmd_pipelines(client)
        elif choice == "5":
            cmd_deployments(client)
        elif choice == "6":
            cmd_semantic_models(client)
        elif choice == "7":
            cmd_workspace_git(client)
        elif choice == "8":
            show_capacity_dashboard(client)
        elif choice == "9":
            workspace = pick_workspace(client)
            if workspace:
                show_json(workspace)
        else:
            fail("Invalid option.")


if __name__ == "__main__":
    main()
