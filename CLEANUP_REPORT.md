# Cleanup Report

## Removed files/folders

- None removed in this pass.

## Why nothing was deleted yet

- The integration is now coherent, but the backend ML runtime is still environment-blocked, so deleting duplicate or legacy code before a fully provisioned end-to-end run would be higher risk than helpful.
- `outfit_generator` remains required because the new runtime imports and delegates to it.
- The old compatibility surfaces were intentionally kept where they still help preserve the visible frontend contract.
- Stabilization focused on import isolation and diagnostics, so no new deletions were necessary to achieve a safe boot.

## High-confidence cleanup candidates kept for now

- `outfit_generator\outfit_generator\frontend\`
  - Reason: appears to be a parallel/demo frontend surface rather than the primary runtime
  - Confidence: medium
- Legacy mock/demo snippets formerly embedded in templates
  - Reason: most were already replaced, but remaining design/demo assets should be reviewed after a real browser QA pass
  - Confidence: high
- Any unused compatibility route once the frontend no longer needs `/api/v1/vton/try-on`
  - Reason: can likely be removed after confirming `/api/v1/claid/try-on` is the only active contract
  - Confidence: medium

## Intentionally kept

- `outfit_generator\outfit_generator\main.py`
  - Kept as the authoritative backend/AI service entrypoint
- `measure_from_image.py`
  - Kept and exposed through `/api/v1/body/measurements`
- Sample catalog JSON
  - Kept as a runtime fallback until the full backend dependency stack is installed
