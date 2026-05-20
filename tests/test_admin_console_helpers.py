from fabric_admin_console.admin_console import (
    cmd_pipelines,
    cmd_semantic_models,
    extract_folder_fields,
    get_required_env_status,
    pick_pipeline,
    pick_semantic_model,
    normalize_path,
    pick_from_list,
    resolve_best_path,
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
