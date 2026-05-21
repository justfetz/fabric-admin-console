# Spec 0004: Workspace Git Utilities

## Summary

The public-safe console needed practical Git-connected workspace utilities so an admin could inspect current source-control state and perform the most common sync actions without dropping into raw REST payloads.

## Goals

- Show the current Git connection for a workspace.
- Show pending workspace and remote Git differences.
- Support update-from-Git with explicit conflict-resolution intent.
- Support commit-all and selective commit workflows.
- Keep payload construction testable and transparent.

## Non-goals

- Manage repository creation or external Git provider setup.
- Replace Azure DevOps / GitHub PR workflows.
- Hide that some Git operations are long-running or provider-dependent.

## User stories

- As a Fabric admin, I want to confirm which branch and repository a workspace is connected to.
- As a Fabric admin, I want to see what changed before I sync.
- As a Fabric admin, I want a controlled update-from-Git action with visible conflict policy.
- As a Fabric admin, I want to commit either everything or a selected subset of changes.

## Acceptance criteria

- The CLI includes a `Workspace Git` menu with connection, status, update, commit-all, and selective-commit actions.
- Git status output is readable without dumping raw JSON first.
- Commit and update payload builders are tested directly.
- Client path helpers for Git endpoints are covered with request-path tests.
