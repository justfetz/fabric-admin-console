from pathlib import Path

from fabric_admin_console.config import (
    FabricAdminConfig,
    FabricEnvironment,
    get_config_path,
    load_admin_config,
    save_admin_config,
)


def _clean(path: Path):
    if path.exists():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        path.rmdir()


def test_save_and_load_admin_config_round_trip():
    home = Path("tests") / "_tmp_fabric_config"
    _clean(home)

    config = FabricAdminConfig(
        deployment_pipeline_id="dp-1",
        environments=(
            FabricEnvironment("DEV", "ws-dev", "stage-dev"),
            FabricEnvironment("PROD", "ws-prod", "stage-prod"),
        ),
    )
    path = save_admin_config(config, home=home)
    assert path == get_config_path(home)

    loaded = load_admin_config(home=home, env={})
    assert loaded.deployment_pipeline_id == "dp-1"
    assert loaded.workspaces() == {"DEV": "ws-dev", "PROD": "ws-prod"}
    assert loaded.stages() == {"DEV": "stage-dev", "PROD": "stage-prod"}

    _clean(home)


def test_env_vars_override_saved_config_values():
    home = Path("tests") / "_tmp_fabric_config_env"
    _clean(home)
    save_admin_config(
        FabricAdminConfig(
            deployment_pipeline_id="dp-file",
            environments=(FabricEnvironment("DEV", "ws-file", "stage-file"),),
        ),
        home=home,
    )

    loaded = load_admin_config(
        home=home,
        env={
            "DEPLOY_PIPELINE_ID": "dp-env",
            "WS_DEV": "ws-env",
            "STAGE_DEV": "stage-env",
        },
    )
    assert loaded.deployment_pipeline_id == "dp-env"
    assert loaded.workspaces()["DEV"] == "ws-env"
    assert loaded.stages()["DEV"] == "stage-env"

    _clean(home)


def test_load_admin_config_defaults_to_dev_pilot_prod_when_empty():
    home = Path("tests") / "_tmp_fabric_config_empty"
    _clean(home)
    loaded = load_admin_config(home=home, env={})
    assert [env.name for env in loaded.environments] == ["DEV", "PILOT", "PROD"]
