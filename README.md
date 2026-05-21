# Fabric Admin Console

[![Python CI](https://github.com/justfetz/fabric-admin-console/actions/workflows/python-ci.yml/badge.svg)](https://github.com/justfetz/fabric-admin-console/actions/workflows/python-ci.yml)

Interactive CLI and reusable API helpers for Microsoft Fabric administration.

This public-safe version is designed to help operators and engineers:

- authenticate to the Fabric REST API with a service principal
- configure their own environment names, workspaces, and deployment stages
- inspect workspaces and items
- inspect and run Fabric data pipelines
- compare and submit deployment-pipeline promotions
- run smart deploys that exclude known unsupported item types
- diagnose workspace item drift and folder path collisions
- inspect semantic models, bindings, ownership, and refresh behavior
- query Fabric Capacity Metrics through the Power BI Execute Queries API
- build higher-level admin workflows without hard-coding tenant-specific values

## What was sanitized

The original internal version contained tenant-specific identifiers and environment defaults. This public version removes or neutralizes:

- workspace GUID defaults
- deployment pipeline and stage IDs
- semantic model connection IDs and endpoint paths
- Azure DevOps org / project / repo defaults
- local repo paths tied to one machine

## Project structure

- `src/fabric_admin_console/fabric_client.py`
  - core auth and REST helpers
- `src/fabric_admin_console/capacity_metrics.py`
  - DAX query helpers and CLI-friendly metrics formatting
- `src/fabric_admin_console/admin_console.py`
  - interactive CLI shell, deployment workflows, and reusable picker / display helpers
- `tests/`
  - regression tests for sanitization-safe helpers and API request normalization

## Setup

1. Create a virtual environment.
2. Install the package and dev tooling:

```powershell
pip install -e .[dev]
```

3. Copy `.env.template` to `.env` and fill in your Fabric credentials.

At minimum, set:

```powershell
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
```

Workspace IDs, deployment pipeline IDs, and deployment stage IDs can now be configured interactively through the app instead of living in `.env`.

## Running

```powershell
python -m fabric_admin_console
```

or after editable install:

```powershell
fabric-admin-console
```

Current interactive menus include:

- `Doctor`
- `Setup`
- `Workspaces`
- `Pipelines`
- `Deployments`
- `Semantic Models`
- `Capacity`

## First-run flow

1. Launch the CLI.
2. Run `Doctor` to validate Azure credentials and basic API access.
3. Run `Setup` to define the environment names you actually use, such as `DEV,TEST,PROD` or `CHI,IND`.
4. Save workspace IDs and deployment stage IDs into the local user config.
5. Return to `Deployments`, `Pipelines`, or `Semantic Models`.

The setup command writes a local config file outside the repo:

- Windows: `%USERPROFILE%\\.fabric-admin-console\\config.toml`

Environment variables still work as explicit overrides. That means you can keep the local config for normal use and override selected values in CI or one-off sessions.

Optional override variables:

```powershell
DEPLOY_PIPELINE_ID=...
WS_DEV=...
STAGE_DEV=...
```

The same pattern works for any configured environment name, for example `WS_TEST`, `STAGE_TEST`, `WS_PROD`, and so on.

## API surface

The reusable client is intentionally split across two Microsoft APIs because Fabric administration still spans both surfaces today.

### Fabric REST API

Used for workspace- and item-native Fabric operations:

- list workspaces
- list items in a workspace
- get pipeline definitions
- start Fabric pipeline jobs
- poll job status
- create job schedules
- inspect deployment pipelines and stages
- deploy one stage to another
- list semantic models
- list semantic model connections
- bind semantic model connections
- list connections

### Power BI REST API

Used where semantic models and capacity workflows still rely on Power BI-era dataset operations:

- dataset takeover
- dataset refresh
- refresh history
- execute-query flows used by the capacity metrics module

In practice, the strengthening opportunity is to keep the CLI honest about which surface it is using and why. Fabric-native admin tasks should prefer Fabric REST first, while dataset ownership, refresh, and capacity-query scenarios still require Power BI REST.

## Strengthening paths

The current tool is strongest for:

- workspace inspection
- deployment pipeline comparison and promotion
- pipeline runs and job monitoring
- semantic model connection inspection and rebinding
- semantic model takeover, refresh, and refresh-history inspection
- capacity metrics summaries

The next high-value growth areas are:

- pipeline parameter capture and schedule creation
- workspace Git helpers
- richer Power BI dataset operations where Fabric still depends on them

## Tests

```powershell
pytest
```

## Coverage

Coverage runs through `pytest-cov` and emits:

- terminal missing-lines report
- `coverage.xml`

## Open-source workflow

- use short-lived branches
- run `pytest` before opening a PR
- avoid committing tenant data, IDs, secrets, or environment-specific defaults
- prefer configuration through `.env` or explicit runtime arguments
