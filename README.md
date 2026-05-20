# Fabric Admin Console

[![Python CI](https://github.com/justfetz/fabric-admin-console/actions/workflows/python-ci.yml/badge.svg)](https://github.com/justfetz/fabric-admin-console/actions/workflows/python-ci.yml)

Interactive CLI and reusable API helpers for Microsoft Fabric administration.

This public-safe version is designed to help operators and engineers:

- authenticate to the Fabric REST API with a service principal
- inspect workspaces and items
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
  - interactive CLI shell and reusable picker / display helpers
- `tests/`
  - regression tests for sanitization-safe helpers and API request normalization

## Setup

1. Create a virtual environment.
2. Install the package and dev tooling:

```powershell
pip install -e .[dev]
```

3. Copy `.env.template` to `.env` and fill in your Fabric credentials.

## Running

```powershell
python -m fabric_admin_console.admin_console
```

or after editable install:

```powershell
fabric-admin-console
```

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
