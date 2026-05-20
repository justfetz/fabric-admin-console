# Spec 0002: Deployment Workflows

## Status

Accepted

## Problem

The public starter could authenticate, list workspaces, run basic pipeline actions, and inspect semantic models, but it did not yet restore the deployment-pipeline workflows that made the original internal console useful for day-to-day Fabric administration.

Fabric admins need to compare environment stages, shape safe deployment payloads, exclude known unsupported items, and diagnose folder/path issues without hard-coding one tenant's IDs into the repo.

## Goals

- add public-safe deployment-pipeline compare and deploy workflows
- keep deployment pipeline IDs and stage IDs environment-driven
- provide reusable helper functions for deploy payloads and smart exclusions
- restore workspace item diff and folder collision diagnostics
- add tests around payload shaping and diagnostics

## Non-Goals

- embedding tenant-specific pipeline, stage, workspace, or connection IDs
- automating destructive purges
- replacing Microsoft Fabric deployment pipeline governance
- porting Azure DevOps helpers in this slice

## User Stories

- As a Fabric admin, I want to compare DEV to PILOT or PILOT to PROD before deploying.
- As a Fabric admin, I want deploy payloads to use conservative default options.
- As a Fabric admin, I want a smart deploy path that excludes Lakehouse, Warehouse, SQLEndpoint, and generated semantic models.
- As a Fabric admin, I want to inspect workspace-level item drift and folder metadata collisions.

## Command Surface

- `Deployments -> Compare DEV vs PILOT`
- `Deployments -> Compare PILOT vs PROD`
- `Deployments -> Deploy DEV -> PILOT`
- `Deployments -> Deploy PILOT -> PROD`
- `Deployments -> Smart deploy`
- `Deployments -> Workspace item diff`
- `Deployments -> Folder conflict scan`

## Acceptance Criteria

- missing deployment configuration is reported clearly
- deployment body construction is tested
- smart deploy exclusion logic is tested
- workspace diff and type mismatch detection are tested
- folder path collision detection is tested
- deploy actions require user confirmation

## Why This Slice Matters

This moves the repo from a starter shell toward a practical Fabric admin console again. It restores a high-value workflow while keeping the public repo safe for other tenants.
