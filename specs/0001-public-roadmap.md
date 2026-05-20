# Fabric Admin Console Public Roadmap

## Status

`fabric-admin-console` is now a good public-safe starter, but it is not yet the full tool. The next steps should preserve the internal app's value without leaking tenant-specific defaults or turning the repo into an opaque monolith.

## Problem

Microsoft Fabric administration often involves:

- repeated API calls
- awkward JSON payloads
- environment comparisons
- Git-connected workspace workflows
- semantic model binding steps
- capacity inspection

The public tool should make those tasks reusable, inspectable, and testable.

## Users

- Fabric administrators
- analytics engineers
- platform engineers
- consultants working across multiple tenants

## Goals

- provide a reusable Python Fabric client
- provide a practical interactive CLI
- keep all org-specific values externalized
- explain workflows clearly enough for non-experts
- grow test coverage as feature depth increases

## Non-Goals

- shipping one company's environment defaults
- embedding secrets, IDs, or repo paths
- becoming a one-off private script dump

## Current Baseline

Today the public repo already has:

- auth and REST helpers
- Power BI token handling
- workspace and item listing helpers
- capacity metrics query helpers
- a starter interactive console
- CI, coverage wiring, contributing guide, and PR template

## Feature Slices To Port Next

### Slice 1: Pipelines

Bring in:

- run pipeline
- monitor job instance
- get pipeline definition
- compare pipelines across environments
- create scheduled run with parameters

Required tests:

- parameter payload shaping
- response normalization
- safe list extraction

### Slice 2: Deployment Helpers

Bring in:

- compare deployment stages
- selective deploy payload builder
- smart deploy exclusions
- folder conflict helpers

Required tests:

- exclude unsupported item types
- normalize folder paths
- detect folder metadata consistently
- verify deploy payload structure

### Slice 3: Workspace Git Utilities

Bring in:

- git status
- update from git
- commit to git
- branch convenience helpers

Required tests:

- git payload construction
- environment variable fallback behavior
- output formatting helpers

### Slice 4: Semantic Model Operations

Bring in:

- list model connections
- manual bind
- quick bind through configuration
- takeover
- refresh
- refresh history

Required tests:

- bind body construction
- refresh history formatting
- quick-bind config validation

### Slice 5: Azure DevOps Helpers

Bring in:

- list open PRs
- create PR
- list remote branches
- delete remote branch

Required tests:

- URL/path construction
- PAT auth header construction
- branch deletion payload shaping

## Coverage Plan

Current public starter coverage is good enough for launch, but not for the mature repo.

Target progression:

- after Slice 1: `70%+`
- after Slice 2: `75%+`
- after Slice 4: `80%+`

Focus on:

- payload builders
- helper normalization
- parsing and rendering logic
- failure-path handling

## Documentation Plan

As the repo grows, add:

- `docs/workspace-git.md`
- `docs/deployments.md`
- `docs/semantic-models.md`
- `docs/capacity-metrics.md`

Each doc should include:

- what problem it solves
- required environment variables
- sample command flow
- safe usage notes

## Open Source Positioning

Best framing:

"A public-safe Microsoft Fabric admin CLI and reusable Python client for workspace inspection, deployment workflows, semantic model operations, and capacity visibility."

Avoid framing it as:

- a full private enterprise automation dump
- a tenant-specific control plane

## Recommended Immediate Next Step

Port the `Pipelines` slice next and add tests for:

- run payloads
- schedule payloads
- list/picker helpers

That is the cleanest high-value expansion from the current public baseline.
