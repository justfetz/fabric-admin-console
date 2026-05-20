import fabric_admin_console.admin_console as admin_console
from fabric_admin_console.admin_console import (
    build_deploy_body,
    build_deploy_items,
    compare_deployment_items,
    compare_workspace_items,
    cmd_deployments,
    detect_folder_path_collisions,
    cmd_pipelines,
    cmd_semantic_models,
    extract_folder_fields,
    get_required_env_status,
    pick_pipeline,
    pick_semantic_model,
    normalize_path,
    pick_from_list,
    resolve_best_path,
    split_smart_deploy_items,
    run_doctor,
    safe_values,
    show_workspace_overview,
)


def test_safe_values_handles_dict_and_list():
    assert safe_values({"value": [1, 2]}) == [1, 2]
    assert safe_values([3, 4]) == [3, 4]
    assert safe_values("bad") == []


def test_normalize_path_collapses_slashes_and_case():
    assert normalize_path(r" /Folder\\Sub//Path ") == "/folder/sub/path"


def test_extract_folder_fields_finds_nested_metadata():
    item = {
        "displayName": "Example",
        "metadata": {"folder": {"id": "abc", "path": "/Ops/Shared"}},
    }
    fields = extract_folder_fields(item)
    assert fields["metadata.folder.id"] == "abc"
    assert resolve_best_path(fields) == "/Ops/Shared"


def test_detect_folder_path_collisions_groups_path_variants():
    items = [
        {"displayName": "A", "id": "1", "metadata": {"folder": {"path": "/Ops/Shared"}}},
        {"displayName": "B", "id": "2", "metadata": {"folder": {"path": "/ops/shared/"}}},
        {"displayName": "C", "id": "3", "metadata": {"folder": {"path": "/Finance"}}},
    ]
    collisions = detect_folder_path_collisions(items)
    assert len(collisions) == 1
    assert collisions[0][0] == "/ops/shared"
    assert {row[1] for row in collisions[0][1]} == {"A", "B"}


def test_pick_from_list_selects_expected_item(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "2")
    result = pick_from_list(
        [{"name": "alpha"}, {"name": "beta"}],
        lambda item: item["name"],
        "Choose item",
    )
    assert result == {"name": "beta"}


def test_get_required_env_status_marks_missing_values():
    status = dict(
        get_required_env_status(
            {
                "AZURE_TENANT_ID": "tenant",
                "AZURE_CLIENT_ID": "client",
            }
        )
    )
    assert status["AZURE_TENANT_ID"] is True
    assert status["AZURE_CLIENT_ID"] is True
    assert status["AZURE_CLIENT_SECRET"] is False


def test_compare_deployment_items_splits_new_updated_and_orphaned():
    source = [
        {"itemDisplayName": "Pipeline A", "itemId": "1"},
        {"itemDisplayName": "Pipeline B", "itemId": "2"},
    ]
    target = [
        {"itemDisplayName": "Pipeline B", "itemId": "3"},
        {"itemDisplayName": "Old Pipeline", "itemId": "4"},
    ]
    diff = compare_deployment_items(source, target)
    assert diff["new"] == ["Pipeline A"]
    assert diff["updated"] == ["Pipeline B"]
    assert diff["orphaned"] == ["Old Pipeline"]


def test_build_deploy_body_includes_safe_default_options():
    body = build_deploy_body("stage-a", "stage-b", note="promote")
    assert body["sourceStageId"] == "stage-a"
    assert body["targetStageId"] == "stage-b"
    assert body["note"] == "promote"
    assert body["options"]["allowPurgeData"] is False


def test_build_deploy_items_uses_source_item_id_and_type():
    items = [{"itemId": "item-1", "itemType": "DataPipeline"}]
    assert build_deploy_items(items) == [{"sourceItemId": "item-1", "itemType": "DataPipeline"}]


def test_split_smart_deploy_items_excludes_unsupported_items():
    items = [
        {"itemDisplayName": "Daily Load", "itemType": "DataPipeline", "itemId": "pipe"},
        {"itemDisplayName": "Warehouse", "itemType": "Warehouse", "itemId": "wh"},
        {"itemDisplayName": "ENTERPRISE_LAKEHOUSE", "itemType": "SemanticModel", "itemId": "sm"},
    ]
    deployable, excluded = split_smart_deploy_items(items)
    assert [item["itemId"] for item in deployable] == ["pipe"]
    assert {item["itemId"] for item in excluded} == {"wh", "sm"}


def test_compare_workspace_items_detects_type_mismatch():
    source = [
        {"displayName": "Shared Name", "type": "Notebook", "id": "n1"},
        {"displayName": "Only Source", "type": "DataPipeline", "id": "p1"},
    ]
    target = [
        {"displayName": "Shared Name", "type": "Report", "id": "r1"},
        {"displayName": "Only Target", "type": "SemanticModel", "id": "s1"},
    ]
    diff = compare_workspace_items(source, target)
    assert ("DataPipeline", "Only Source") in diff["only_source"]
    assert ("SemanticModel", "Only Target") in diff["only_target"]
    assert diff["type_mismatches"][0][0] == "Shared Name"


def test_pick_pipeline_uses_data_pipeline_filter(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "1")

    class FakeClient:
        def list_items(self, workspace_id, item_type=None):
            assert workspace_id == "ws-1"
            assert item_type == "DataPipeline"
            return {"value": [{"displayName": "Daily Load", "id": "pipe-1"}]}

    result = pick_pipeline(FakeClient(), "ws-1")
    assert result["id"] == "pipe-1"


def test_pick_semantic_model_lists_models(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "1")

    class FakeClient:
        def list_semantic_models(self, workspace_id):
            assert workspace_id == "ws-2"
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

    result = pick_semantic_model(FakeClient(), "ws-2")
    assert result["id"] == "sm-1"


def test_run_doctor_reports_basic_health(monkeypatch, capsys):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")

    class FakeClient:
        def _get_token(self):
            return "fabric-token"

        def _get_powerbi_token(self):
            return "pbi-token"

        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

    run_doctor(FakeClient())
    out = capsys.readouterr().out
    assert "Fabric API token acquired" in out
    assert "Power BI token acquired" in out
    assert "workspace(s) visible" in out


def test_show_workspace_overview_prints_workspace_names(capsys):
    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

    show_workspace_overview(FakeClient())
    out = capsys.readouterr().out
    assert "Ops" in out
    assert "ws-1" in out


def test_cmd_pipelines_lists_pipelines(monkeypatch, capsys):
    answers = iter(["1", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_items(self, workspace_id, item_type=None):
            assert workspace_id == "ws-1"
            assert item_type == "DataPipeline"
            return {"value": [{"displayName": "Daily Load", "id": "pipe-1"}]}

    cmd_pipelines(FakeClient())
    out = capsys.readouterr().out
    assert "Daily Load" in out
    assert "pipe-1" in out


def test_cmd_semantic_models_lists_models(monkeypatch, capsys):
    answers = iter(["1", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            assert workspace_id == "ws-1"
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "Finance Model" in out
    assert "sm-1" in out


def test_cmd_semantic_models_prints_refresh_history(monkeypatch, capsys):
    answers = iter(["2", "1", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

        def get_refresh_history(self, workspace_id, model_id):
            assert workspace_id == "ws-1"
            assert model_id == "sm-1"
            return {
                "value": [
                    {
                        "startTime": "2026-05-20T08:00:00",
                        "endTime": "2026-05-20T08:03:00",
                        "refreshType": "ViaApi",
                        "status": "Completed",
                    }
                ]
            }

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "2026-05-20 08:00:00" in out
    assert "Completed" in out


def test_cmd_deployments_compares_stages(monkeypatch, capsys):
    monkeypatch.setattr(admin_console, "DEPLOY_PIPELINE_ID", "dp-1")
    monkeypatch.setattr(admin_console, "DEPLOY_STAGES", {"DEV": "dev-stage", "PILOT": "pilot-stage", "PROD": "prod-stage"})
    answers = iter(["1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def get_deployment_stage_items(self, pipeline_id, stage_id):
            assert pipeline_id == "dp-1"
            if stage_id == "dev-stage":
                return {
                    "value": [
                        {"itemDisplayName": "New Pipeline", "itemId": "1"},
                        {"itemDisplayName": "Shared Pipeline", "itemId": "2"},
                    ]
                }
            return {
                "value": [
                    {"itemDisplayName": "Shared Pipeline", "itemId": "3"},
                    {"itemDisplayName": "Old Pipeline", "itemId": "4"},
                ]
            }

    cmd_deployments(FakeClient())
    out = capsys.readouterr().out
    assert "New: 1" in out
    assert "New Pipeline" in out
    assert "Old Pipeline" in out


def test_cmd_deployments_deploy_all_requires_confirmation_and_posts_body(monkeypatch, capsys):
    monkeypatch.setattr(admin_console, "DEPLOY_PIPELINE_ID", "dp-1")
    monkeypatch.setattr(admin_console, "DEPLOY_STAGES", {"DEV": "dev-stage", "PILOT": "pilot-stage", "PROD": "prod-stage"})
    answers = iter(["3", "y", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    posted = {}

    class FakeClient:
        def deploy_stage(self, pipeline_id, body):
            posted["pipeline_id"] = pipeline_id
            posted["body"] = body
            return {"status": "Succeeded"}

    cmd_deployments(FakeClient())
    out = capsys.readouterr().out
    assert "Deployment DEV -> PILOT submitted" in out
    assert posted["pipeline_id"] == "dp-1"
    assert posted["body"]["sourceStageId"] == "dev-stage"
    assert posted["body"]["targetStageId"] == "pilot-stage"
    assert posted["body"]["options"]["allowPurgeData"] is False


def test_cmd_deployments_smart_deploy_excludes_unsupported_items(monkeypatch, capsys):
    monkeypatch.setattr(admin_console, "DEPLOY_PIPELINE_ID", "dp-1")
    monkeypatch.setattr(admin_console, "DEPLOY_STAGES", {"DEV": "dev-stage", "PILOT": "pilot-stage", "PROD": "prod-stage"})
    answers = iter(["5", "1", "y", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    posted = {}

    class FakeClient:
        def get_deployment_stage_items(self, pipeline_id, stage_id):
            assert pipeline_id == "dp-1"
            assert stage_id == "dev-stage"
            return {
                "value": [
                    {"itemDisplayName": "Daily Load", "itemType": "DataPipeline", "itemId": "pipe-1"},
                    {"itemDisplayName": "Warehouse", "itemType": "Warehouse", "itemId": "wh-1"},
                ]
            }

        def deploy_stage(self, pipeline_id, body):
            posted["body"] = body
            return {"status": "Succeeded"}

    cmd_deployments(FakeClient())
    out = capsys.readouterr().out
    assert "Deployable: 1" in out
    assert "Excluded: 1" in out
    assert posted["body"]["items"] == [{"sourceItemId": "pipe-1", "itemType": "DataPipeline"}]


def test_cmd_deployments_workspace_diff(monkeypatch, capsys):
    monkeypatch.setattr(admin_console, "WORKSPACES", {"DEV": "dev-ws", "PILOT": "pilot-ws", "PROD": ""})
    answers = iter(["6", "1", "2", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_items(self, workspace_id, item_type=None):
            if workspace_id == "dev-ws":
                return {"value": [{"displayName": "Shared", "type": "Notebook", "id": "n1"}]}
            return {"value": [{"displayName": "Shared", "type": "Report", "id": "r1"}]}

    cmd_deployments(FakeClient())
    out = capsys.readouterr().out
    assert "Type mismatches: 1" in out
    assert "Shared" in out


def test_cmd_deployments_folder_scan(monkeypatch, capsys):
    answers = iter(["7", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_items(self, workspace_id, item_type=None):
            assert workspace_id == "ws-1"
            return {
                "value": [
                    {"displayName": "A", "id": "1", "metadata": {"folder": {"path": "/Ops"}}},
                    {"displayName": "B", "id": "2", "metadata": {"folder": {"path": "/ops/"}}},
                ]
            }

    cmd_deployments(FakeClient())
    out = capsys.readouterr().out
    assert "Folder path collisions" in out
    assert "A" in out
