import fabric_admin_console.admin_console as admin_console
from fabric_admin_console.config import FabricAdminConfig, FabricEnvironment
from fabric_admin_console.admin_console import (
    build_deploy_body,
    build_deploy_items,
    compare_deployment_items,
    compare_workspace_items,
    cmd_deployments,
    cmd_setup,
    cmd_workspace_git,
    detect_folder_path_collisions,
    cmd_pipelines,
    cmd_semantic_models,
    build_commit_to_git_body,
    build_update_from_git_body,
    configured_workspace_count,
    decode_pipeline_definition_payload,
    extract_folder_fields,
    get_required_env_status,
    git_connection_summary,
    git_status_summary,
    git_status_summary_lines,
    git_status_changes,
    pipeline_terminal_state,
    print_config_summary,
    pick_pipeline,
    pick_semantic_model,
    normalize_path,
    parse_environment_names,
    pick_from_list,
    resolve_best_path,
    select_git_changes,
    should_offer_setup,
    split_smart_deploy_items,
    run_doctor,
    safe_values,
    semantic_model_connection_card_lines,
    semantic_model_connection_label,
    semantic_model_connection_path,
    semantic_model_connection_type,
    show_workspace_overview,
)


def test_safe_values_handles_dict_and_list():
    assert safe_values({"value": [1, 2]}) == [1, 2]
    assert safe_values([3, 4]) == [3, 4]
    assert safe_values("bad") == []


def test_normalize_path_collapses_slashes_and_case():
    assert normalize_path(r" /Folder\\Sub//Path ") == "/folder/sub/path"


def test_parse_environment_names_deduplicates_and_uppercases():
    assert parse_environment_names("dev, test;prod, DEV") == ["DEV", "TEST", "PROD"]


def test_should_offer_setup_when_no_workspace_ids_are_configured():
    config = FabricAdminConfig(
        environments=(
            FabricEnvironment("DEV", "", ""),
            FabricEnvironment("PROD", "", ""),
        )
    )
    assert configured_workspace_count(config) == 0
    assert should_offer_setup(config) is True


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


def test_semantic_model_connection_helpers_prefer_nested_details():
    connection = {
        "displayName": "Pilot SQL",
        "id": "conn-1",
        "connectionDetails": {"type": "SQL", "path": "server;database"},
    }
    assert semantic_model_connection_type(connection) == "SQL"
    assert semantic_model_connection_path(connection) == "server;database"
    assert semantic_model_connection_label(connection) == "Pilot SQL [SQL] | server;database"


def test_semantic_model_connection_card_lines_render_card():
    lines = semantic_model_connection_card_lines(
        {
            "displayName": "Pilot SQL",
            "id": "conn-1",
            "connectionDetails": {"type": "SQL", "path": "server;database"},
        }
    )
    assert lines[0].startswith("    +")
    assert any("Pilot SQL" in line for line in lines)


def test_git_connection_summary_uses_provider_details():
    summary = git_connection_summary(
        {
            "gitProviderType": "AzureDevOps",
            "branchName": "main",
            "directoryName": "/fabric",
            "gitProviderDetails": {"repositoryName": "fabric-repo"},
        }
    )
    assert summary == {
        "provider": "AzureDevOps",
        "repository": "fabric-repo",
        "branch": "main",
        "directory": "/fabric",
    }


def test_git_status_changes_prefers_changes_key():
    status = {"changes": [{"itemId": "1"}], "value": [{"itemId": "2"}]}
    assert git_status_changes(status) == [{"itemId": "1"}]


def test_git_status_summary_groups_workspace_and_remote_states():
    summary = git_status_summary(
        [
            {"workspaceChange": "Modified", "remoteChange": "Same"},
            {"workspaceChange": "Modified", "remoteChange": "Behind"},
        ]
    )
    assert summary["total"] == 2
    assert summary["workspace"]["Modified"] == 2
    assert summary["remote"]["Same"] == 1
    assert summary["remote"]["Behind"] == 1


def test_git_status_summary_lines_render_card():
    lines = git_status_summary_lines(
        {
            "total": 2,
            "workspace": {"Modified": 2},
            "remote": {"Behind": 1, "Same": 1},
        }
    )
    assert lines[0].startswith("    +")
    assert any("Total changes" in line for line in lines)


def test_build_commit_to_git_body_supports_all_and_selective_modes():
    all_body = build_commit_to_git_body("sync")
    selective_body = build_commit_to_git_body("sync", [{"itemId": "a"}])
    assert all_body == {"mode": "All", "comment": "sync"}
    assert selective_body == {"mode": "Selective", "comment": "sync", "items": [{"itemId": "a"}]}


def test_build_update_from_git_body_supports_remote_hash_and_policy():
    body = build_update_from_git_body("abc123", "PreferWorkspace")
    assert body["remoteCommitHash"] == "abc123"
    assert body["conflictResolution"]["conflictResolutionType"] == "PreferWorkspace"


def test_print_config_summary_shows_environments(monkeypatch, capsys):
    monkeypatch.setattr(admin_console, "get_config_path", lambda: "C:/fake/.fabric-admin-console/config.toml")
    print_config_summary(
        FabricAdminConfig(
            deployment_pipeline_id="dp-1",
            environments=(
                FabricEnvironment("DEV", "ws-dev", "stage-dev"),
                FabricEnvironment("PROD", "", ""),
            ),
        )
    )
    out = capsys.readouterr().out
    assert "Active configuration" in out
    assert "C:/fake/.fabric-admin-console/config.toml" in out
    assert "DEV" in out
    assert "ws-dev" in out
    assert "PROD" in out


def test_select_git_changes_ignores_invalid_indexes():
    changes = [{"itemId": "a"}, {"itemId": "b"}]
    assert select_git_changes(changes, "2, x, 99, 1") == [{"itemId": "b"}, {"itemId": "a"}]


def test_pipeline_terminal_state_handles_non_dict_payloads():
    assert pipeline_terminal_state({"status": "Completed"}) == "Completed"
    assert pipeline_terminal_state("bad") == "Unknown"


def test_decode_pipeline_definition_payload_returns_json_object():
    payload = "eyJuYW1lIjogIkRhaWx5IExvYWQifQ=="
    result = {
        "definition": {
            "parts": [{"path": "pipeline-content.json", "payload": payload}]
        }
    }
    assert decode_pipeline_definition_payload(result) == {"name": "Daily Load"}


def test_decode_pipeline_definition_payload_returns_none_when_missing():
    assert decode_pipeline_definition_payload({"definition": {"parts": []}}) is None
    assert decode_pipeline_definition_payload({"error": True}) is None


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


def test_cmd_pipelines_warns_when_definition_part_missing(monkeypatch, capsys):
    answers = iter(["4", "1", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_items(self, workspace_id, item_type=None):
            return {"value": [{"displayName": "Daily Load", "id": "pipe-1"}]}

        def get_pipeline_definition(self, workspace_id, pipeline_id):
            return {"definition": {"parts": []}}

    cmd_pipelines(FakeClient())
    out = capsys.readouterr().out
    assert "No pipeline-content.json part found" in out


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
    answers = iter(["7", "1", "1", "0"])
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


def test_cmd_semantic_models_shows_model_connections(monkeypatch, capsys):
    answers = iter(["2", "1", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

        def get_sm_connections(self, workspace_id, model_id):
            assert workspace_id == "ws-1"
            assert model_id == "sm-1"
            return {
                "value": [
                    {
                        "displayName": "Pilot SQL",
                        "id": "conn-1",
                        "connectionDetails": {"type": "SQL", "path": "server;db"},
                    }
                ]
            }

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "Connections for Finance Model" in out
    assert "+-----------------------------------------------------------+" in out
    assert "Pilot SQL" in out
    assert "server;db" in out


def test_cmd_semantic_models_binds_existing_connection(monkeypatch, capsys):
    answers = iter(["4", "1", "1", "y", "1", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    called = {}

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

        def get_sm_connections(self, workspace_id, model_id):
            return {"value": []}

        def list_connections(self):
            return {
                "value": [
                    {
                        "displayName": "Pilot SQL",
                        "id": "conn-1",
                        "connectionDetails": {"type": "SQL", "path": "server;db"},
                    }
                ]
            }

        def bind_sm_connection(self, workspace_id, model_id, connection_id, connection_type="SQL", connection_path=None):
            called["args"] = (
                workspace_id,
                model_id,
                connection_id,
                connection_type,
                connection_path,
            )
            return {"status": "Succeeded"}

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "Connection binding submitted" in out
    assert called["args"] == ("ws-1", "sm-1", "conn-1", "SQL", "server;db")


def test_cmd_semantic_models_warns_when_no_shared_connections_available(monkeypatch, capsys):
    answers = iter(["4", "1", "1", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

        def get_sm_connections(self, workspace_id, model_id):
            return {"value": []}

        def list_connections(self):
            return {"value": []}

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "No shared connections available." in out


def test_cmd_semantic_models_requires_manual_connection_path(monkeypatch, capsys):
    answers = iter(["4", "1", "1", "n", "SQL", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

        def get_sm_connections(self, workspace_id, model_id):
            return {"value": []}

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "Connection path is required." in out


def test_cmd_semantic_models_reports_bind_failure(monkeypatch, capsys):
    answers = iter(["4", "1", "1", "n", "SQL", "server;db", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

        def get_sm_connections(self, workspace_id, model_id):
            return {"value": []}

        def bind_sm_connection(self, workspace_id, model_id, connection_id, connection_type="SQL", connection_path=None):
            return {"error": True, "status": 400, "detail": {"message": "bad bind"}}

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "Connection binding failed" in out


def test_cmd_semantic_models_triggers_refresh(monkeypatch, capsys):
    answers = iter(["6", "1", "1", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    called = {}

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

        def refresh_dataset(self, workspace_id, model_id):
            called["args"] = (workspace_id, model_id)
            return {"status": "Accepted"}

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "Refresh submitted for Finance Model" in out
    assert called["args"] == ("ws-1", "sm-1")


def test_cmd_semantic_models_reports_refresh_failure(monkeypatch, capsys):
    answers = iter(["6", "1", "1", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

        def refresh_dataset(self, workspace_id, model_id):
            return {"error": True, "status": 500, "detail": {"message": "refresh failed"}}

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "Refresh failed:" in out


def test_cmd_semantic_models_takes_over_model(monkeypatch, capsys):
    answers = iter(["5", "1", "1", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    called = {}

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

        def takeover_dataset(self, workspace_id, model_id):
            called["args"] = (workspace_id, model_id)
            return {"status": "Accepted"}

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "Takeover submitted for Finance Model" in out
    assert called["args"] == ("ws-1", "sm-1")


def test_cmd_semantic_models_reports_takeover_failure(monkeypatch, capsys):
    answers = iter(["5", "1", "1", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def list_semantic_models(self, workspace_id):
            return {"value": [{"displayName": "Finance Model", "id": "sm-1"}]}

        def takeover_dataset(self, workspace_id, model_id):
            return {"error": True, "status": 403, "detail": {"message": "forbidden"}}

    cmd_semantic_models(FakeClient())
    out = capsys.readouterr().out
    assert "Takeover failed:" in out


def test_cmd_workspace_git_shows_connection(monkeypatch, capsys):
    answers = iter(["1", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def get_git_connection(self, workspace_id):
            assert workspace_id == "ws-1"
            return {
                "gitProviderType": "AzureDevOps",
                "branchName": "main",
                "directoryName": "/fabric",
                "gitProviderDetails": {"repositoryName": "fabric-repo"},
            }

    cmd_workspace_git(FakeClient())
    out = capsys.readouterr().out
    assert "Git connection: Ops" in out
    assert "fabric-repo" in out
    assert "main" in out


def test_cmd_workspace_git_shows_status_summary_before_changes(monkeypatch, capsys):
    answers = iter(["2", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def get_git_status(self, workspace_id):
            return {
                "changes": [
                    {
                        "itemId": "item-1",
                        "itemType": "Notebook",
                        "displayName": "Ops Notebook",
                        "workspaceChange": "Modified",
                        "remoteChange": "Same",
                    }
                ]
            }

    cmd_workspace_git(FakeClient())
    out = capsys.readouterr().out
    assert "Git status summary: Ops" in out
    assert "Total changes:" in out


def test_cmd_workspace_git_reports_connection_failure(monkeypatch, capsys):
    answers = iter(["1", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def get_git_connection(self, workspace_id):
            return {"error": True, "status": 404, "detail": {"message": "not connected"}}

    cmd_workspace_git(FakeClient())
    out = capsys.readouterr().out
    assert "Git connection lookup failed:" in out


def test_cmd_workspace_git_reports_status_failure(monkeypatch, capsys):
    answers = iter(["2", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def get_git_status(self, workspace_id):
            return {"error": True, "status": 500, "detail": {"message": "status failed"}}

    cmd_workspace_git(FakeClient())
    out = capsys.readouterr().out
    assert "Git status failed:" in out


def test_cmd_workspace_git_reports_update_failure(monkeypatch, capsys):
    answers = iter(["3", "1", "", "y", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def update_from_git(self, workspace_id, body):
            return {"error": True, "status": 409, "detail": {"message": "conflict"}}

    cmd_workspace_git(FakeClient())
    out = capsys.readouterr().out
    assert "Update from Git failed:" in out


def test_cmd_workspace_git_reports_commit_all_failure(monkeypatch, capsys):
    answers = iter(["4", "1", "Workspace sync", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def commit_to_git(self, workspace_id, body):
            return {"error": True, "status": 500, "detail": {"message": "commit failed"}}

    cmd_workspace_git(FakeClient())
    out = capsys.readouterr().out
    assert "Commit to Git failed:" in out


def test_cmd_workspace_git_commits_selected_changes(monkeypatch, capsys):
    answers = iter(["5", "1", "1,2", "Selective sync", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    called = {}

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def get_git_status(self, workspace_id):
            assert workspace_id == "ws-1"
            return {
                "changes": [
                    {"itemId": "item-1", "itemType": "Notebook", "displayName": "Ops Notebook", "workspaceChange": "Modified", "remoteChange": "Same"},
                    {"itemId": "item-2", "itemType": "Report", "displayName": "Ops Report", "workspaceChange": "Added", "remoteChange": "Same"},
                ]
            }

        def commit_to_git(self, workspace_id, body):
            called["args"] = (workspace_id, body)
            return {"status": "Succeeded"}

    cmd_workspace_git(FakeClient())
    out = capsys.readouterr().out
    assert "Selective commit submitted for Ops" in out
    assert called["args"][0] == "ws-1"
    assert called["args"][1]["mode"] == "Selective"
    assert called["args"][1]["comment"] == "Selective sync"
    assert called["args"][1]["items"] == [{"itemId": "item-1"}, {"itemId": "item-2"}]


def test_cmd_workspace_git_rejects_invalid_selected_changes(monkeypatch, capsys):
    answers = iter(["5", "1", "x,99", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def get_git_status(self, workspace_id):
            return {
                "changes": [
                    {"itemId": "item-1", "itemType": "Notebook", "displayName": "Ops Notebook", "workspaceChange": "Modified", "remoteChange": "Same"},
                ]
            }

    cmd_workspace_git(FakeClient())
    out = capsys.readouterr().out
    assert "No valid changes selected." in out


def test_cmd_workspace_git_warns_when_no_selective_changes_available(monkeypatch, capsys):
    answers = iter(["5", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def get_git_status(self, workspace_id):
            return {"changes": []}

    cmd_workspace_git(FakeClient())
    out = capsys.readouterr().out
    assert "No Git changes available for selective commit." in out


def test_cmd_workspace_git_reports_selective_commit_failure(monkeypatch, capsys):
    answers = iter(["5", "1", "1", "Selective sync", "y", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    class FakeClient:
        def list_workspaces(self):
            return {"value": [{"displayName": "Ops", "id": "ws-1"}]}

        def get_git_status(self, workspace_id):
            return {
                "changes": [
                    {"itemId": "item-1", "itemType": "Notebook", "displayName": "Ops Notebook", "workspaceChange": "Modified", "remoteChange": "Same"},
                ]
            }

        def commit_to_git(self, workspace_id, body):
            return {"error": True, "status": 500, "detail": {"message": "commit failed"}}

    cmd_workspace_git(FakeClient())
    out = capsys.readouterr().out
    assert "Selective commit failed:" in out


def test_cmd_deployments_compares_stages(monkeypatch, capsys):
    monkeypatch.setattr(
        admin_console,
        "get_active_config",
        lambda: FabricAdminConfig(
            deployment_pipeline_id="dp-1",
            environments=(
                FabricEnvironment("DEV", "dev-ws", "dev-stage"),
                FabricEnvironment("PILOT", "pilot-ws", "pilot-stage"),
                FabricEnvironment("PROD", "prod-ws", "prod-stage"),
            ),
        ),
    )
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
    monkeypatch.setattr(
        admin_console,
        "get_active_config",
        lambda: FabricAdminConfig(
            deployment_pipeline_id="dp-1",
            environments=(
                FabricEnvironment("DEV", "dev-ws", "dev-stage"),
                FabricEnvironment("PILOT", "pilot-ws", "pilot-stage"),
                FabricEnvironment("PROD", "prod-ws", "prod-stage"),
            ),
        ),
    )
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
    monkeypatch.setattr(
        admin_console,
        "get_active_config",
        lambda: FabricAdminConfig(
            deployment_pipeline_id="dp-1",
            environments=(
                FabricEnvironment("DEV", "dev-ws", "dev-stage"),
                FabricEnvironment("PILOT", "pilot-ws", "pilot-stage"),
                FabricEnvironment("PROD", "prod-ws", "prod-stage"),
            ),
        ),
    )
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
    monkeypatch.setattr(
        admin_console,
        "get_active_config",
        lambda: FabricAdminConfig(
            environments=(
                FabricEnvironment("DEV", "dev-ws", "dev-stage"),
                FabricEnvironment("PILOT", "pilot-ws", "pilot-stage"),
                FabricEnvironment("PROD", "", ""),
            ),
        ),
    )
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


def test_cmd_setup_saves_environment_config(monkeypatch, capsys):
    answers = iter(["DEV,TEST,PROD", "ws-dev", "stage-dev", "ws-test", "stage-test", "ws-prod", "stage-prod", "dp-1"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(admin_console, "get_active_config", lambda: FabricAdminConfig())
    saved = {}

    def fake_save(config):
        saved["config"] = config
        return "C:/fake/.fabric-admin-console/config.toml"

    monkeypatch.setattr(admin_console, "save_admin_config", fake_save)
    cmd_setup()
    out = capsys.readouterr().out
    assert "Saved Fabric Admin Console config" in out
    assert saved["config"].deployment_pipeline_id == "dp-1"
    assert [env.name for env in saved["config"].environments] == ["DEV", "TEST", "PROD"]
