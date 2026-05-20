# Contributing

This repo is intended to be useful in the open, so changes should stay easy to review and safe to share.

## Rules

- do not commit secrets
- do not commit real tenant IDs unless they are already public and intentionally documented
- do not commit environment-specific defaults that only work for one company or one laptop
- prefer `.env` and explicit configuration over hard-coded IDs

## Workflow

1. Create a branch from `main`
2. Make one focused change
3. Run:

```powershell
pytest
```

4. Open a PR with:
   - what changed
   - why it changed
   - how it was tested

## Good first follow-ups

- expand CLI coverage beyond helper-level tests
- add mocked tests for more Fabric API flows
- introduce JMESPath / rich table formatting if it improves usability
- add more subcommands as isolated, testable modules
