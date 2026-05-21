"""User-local configuration for Fabric Admin Console."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


DEFAULT_CONFIG_DIRNAME = ".fabric-admin-console"
DEFAULT_CONFIG_FILENAME = "config.toml"
DEFAULT_ENVIRONMENTS = ("DEV", "PILOT", "PROD")


@dataclass(frozen=True)
class FabricEnvironment:
    name: str
    workspace_id: str = ""
    stage_id: str = ""


@dataclass(frozen=True)
class FabricAdminConfig:
    deployment_pipeline_id: str = ""
    environments: tuple[FabricEnvironment, ...] = ()

    def workspaces(self) -> dict[str, str]:
        return {env.name: env.workspace_id for env in self.environments}

    def stages(self) -> dict[str, str]:
        return {env.name: env.stage_id for env in self.environments}


def get_config_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / DEFAULT_CONFIG_DIRNAME


def get_config_path(home: Path | None = None) -> Path:
    return get_config_dir(home) / DEFAULT_CONFIG_FILENAME


def load_admin_config(
    home: Path | None = None,
    env: dict[str, str] | None = None,
) -> FabricAdminConfig:
    active_env = env or os.environ
    file_config = _load_file_config(get_config_path(home))

    file_environments = file_config.environments
    if not file_environments:
        file_environments = tuple(FabricEnvironment(name=name) for name in DEFAULT_ENVIRONMENTS)

    environments = []
    for fabric_env in file_environments:
        name = fabric_env.name.upper()
        environments.append(
            FabricEnvironment(
                name=name,
                workspace_id=active_env.get(f"WS_{name}", fabric_env.workspace_id),
                stage_id=active_env.get(f"STAGE_{name}", fabric_env.stage_id),
            )
        )

    deployment_pipeline_id = (
        active_env.get("DEPLOY_PIPELINE_ID")
        or file_config.deployment_pipeline_id
        or ""
    )
    return FabricAdminConfig(
        deployment_pipeline_id=deployment_pipeline_id,
        environments=tuple(environments),
    )


def save_admin_config(config: FabricAdminConfig, home: Path | None = None) -> Path:
    path = get_config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    if config.deployment_pipeline_id:
        lines.append(f'deployment_pipeline_id = "{config.deployment_pipeline_id}"')
        lines.append("")
    for env in config.environments:
        lines.extend(
            [
                "[[environments]]",
                f'name = "{env.name}"',
                f'workspace_id = "{env.workspace_id}"',
                f'stage_id = "{env.stage_id}"',
                "",
            ]
        )

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _load_file_config(path: Path) -> FabricAdminConfig:
    if not path.exists():
        return FabricAdminConfig()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    environments = tuple(
        FabricEnvironment(
            name=str(item.get("name", "")).strip().upper(),
            workspace_id=str(item.get("workspace_id", "")).strip(),
            stage_id=str(item.get("stage_id", "")).strip(),
        )
        for item in data.get("environments", [])
        if str(item.get("name", "")).strip()
    )
    return FabricAdminConfig(
        deployment_pipeline_id=str(data.get("deployment_pipeline_id", "")).strip(),
        environments=environments,
    )
