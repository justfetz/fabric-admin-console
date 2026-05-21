# Spec 0003: Semantic Model Workflows

## Summary

The public-safe console already had reusable semantic-model helpers in the client, but the CLI only exposed model listing and refresh-history inspection. This slice restores the practical day-to-day semantic-model workflows that made the internal console useful.

## Goals

- Let an admin inspect current semantic-model bindings.
- Let an admin inspect tenant-level reusable connections.
- Let an admin bind a semantic model to a selected shared connection or a manually supplied path.
- Let an admin take ownership of a semantic model through the Power BI dataset surface.
- Let an admin trigger and review refresh activity.

## Non-goals

- Hard-code tenant-specific connection IDs or endpoint paths.
- Assume all users run DEV/PILOT/PROD.
- Hide that some semantic-model operations still rely on the Power BI dataset API.

## User stories

- As a Fabric admin, I want to see how one semantic model is currently bound before I change it.
- As a Fabric admin, I want to select from shared connections instead of pasting raw IDs blindly.
- As a Fabric admin, I want a manual-path fallback when I do not have a reusable shared connection.
- As a Fabric admin, I want takeover, refresh, and refresh history in the same menu so I can complete the workflow end to end.

## Acceptance criteria

- The semantic-model menu includes current bindings, shared connections, bind, takeover, refresh, and refresh-history flows.
- Bind can use either a selected shared connection or a manual path.
- Successful takeover and refresh actions clearly note that they run through the Power BI dataset surface.
- Tests cover helper formatting and CLI semantic-model actions without live API access.
