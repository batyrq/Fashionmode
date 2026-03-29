# Stabilization Plan

## Current blockers

- `outfit_generator` still imports optional ML/search modules at backend startup, so missing `faiss` can block unrelated routes.
- Backend capability state is not fully visible from `/api/health`.
- Dependency expectations are spread across multiple requirement files and runtime fallbacks are not documented clearly enough.
- Measurement works only when model asset paths are configured, but the diagnostics can be more actionable.
- Favorites remain intentionally disabled because current catalog IDs do not map safely to Supabase UUID product rows.

## Exact plan

- Refactor backend imports so `ProductDatabase`, `ClipFashionSearch`, `QwenStylistChatbot`, and `BodyTypeAnalyzer` are loaded only when their routes need them.
- Make `faiss` optional inside the catalog/search modules so catalog reads can boot without image-search support.
- Add structured capability reporting to the integrated health endpoint, including backend import status, optional subsystem availability, and catalog source.
- Produce a dependency matrix and bootstrap script so the intended local setup is reproducible.
- Keep favorites disabled unless a real UUID mapping already exists; otherwise make the disabled state explicit and documented.

## Full fixes in this pass

- Global boot fragility from optional ML imports
- Clear subsystem diagnostics
- Reproducible dependency guidance
- Better route-scoped error behavior for chat/try-on/body-analysis/measurement/search

## Intentionally deferred or isolated

- Search-by-image remains disabled unless a real runtime index/load path is present
- Favorites remain disabled unless safe catalog-to-UUID mapping is discoverable
- Measurement inference remains environment-dependent on model assets
