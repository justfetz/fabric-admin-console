from unittest.mock import Mock, patch

from fabric_admin_console.fabric_client import FabricClient


def make_client():
    with patch("fabric_admin_console.fabric_client.os.getenv") as getenv:
        values = {
            "AZURE_TENANT_ID": "tenant",
            "AZURE_CLIENT_ID": "client",
            "AZURE_CLIENT_SECRET": "secret",
        }
        getenv.side_effect = lambda key, default=None: values.get(key, default)
        return FabricClient()


def test_request_wraps_list_response():
    client = make_client()
    response = Mock(status_code=200)
    response.json.return_value = [{"id": 1}]
    with patch.object(client, "_headers", return_value={"Authorization": "Bearer token"}):
        with patch("fabric_admin_console.fabric_client.requests.request", return_value=response):
            result = client._request("GET", "/workspaces")
    assert result == {"value": [{"id": 1}]}


def test_request_returns_error_payload_on_failure():
    client = make_client()
    response = Mock(status_code=400)
    response.json.return_value = {"message": "bad"}
    with patch.object(client, "_headers", return_value={"Authorization": "Bearer token"}):
        with patch("fabric_admin_console.fabric_client.requests.request", return_value=response):
            result = client._request("GET", "/workspaces")
    assert result["error"] is True
    assert result["status"] == 400


def test_bind_sm_connection_uses_shareable_cloud_body():
    client = make_client()
    with patch.object(client, "post", return_value={"ok": True}) as post:
        client.bind_sm_connection("ws", "sm", "conn", connection_path="server;db")
    body = post.call_args.args[1]
    assert body["connectionBinding"]["id"] == "conn"
    assert body["connectionBinding"]["connectivityType"] == "ShareableCloud"


def test_pbi_request_wraps_list_payload():
    client = make_client()
    response = Mock(status_code=200)
    response.json.return_value = [{"status": "ok"}]
    with patch.object(client, "_get_powerbi_token", return_value="token"):
        with patch("fabric_admin_console.fabric_client.requests.request", return_value=response):
            result = client._pbi_request("GET", "/groups/test")
    assert result == {"value": [{"status": "ok"}]}


def test_run_pipeline_wraps_parameter_payload():
    client = make_client()
    with patch.object(client, "post", return_value={"ok": True}) as post:
        client.run_pipeline("ws", "pipe", parameters={"batch": {"value": "42", "type": "string"}})
    assert post.call_args.args[0].endswith("/items/pipe/jobs/instances?jobType=Pipeline")
    assert post.call_args.args[1]["executionData"]["parameters"]["batch"]["value"] == "42"


def test_get_pipeline_definition_uses_expected_path():
    client = make_client()
    with patch.object(client, "post", return_value={"ok": True}) as post:
        client.get_pipeline_definition("ws", "pipe")
    assert post.call_args.args[0] == "/workspaces/ws/dataPipelines/pipe/getDefinition"


def test_get_job_status_uses_expected_path():
    client = make_client()
    with patch.object(client, "get", return_value={"status": "Completed"}) as get:
        client.get_job_status("ws", "pipe", "job-1")
    assert get.call_args.args[0] == "/workspaces/ws/items/pipe/jobs/instances/job-1"
