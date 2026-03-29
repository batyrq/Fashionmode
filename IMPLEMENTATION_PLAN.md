# Implementation Plan

## Runtime entrypoint

- Primary runtime entrypoint: `C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py`
- `ai-stylist-platform` remains the user-facing web app and page owner.
- Real backend logic will be imported from `outfit_generator` into the `ai-stylist-platform` runtime.

## Route ownership

- Preserve frontend page routes:
  - `/`
  - `/chat`
  - `/tryon`
  - `/analysis`
  - `/catalog`
  - `/outfits`
  - `/login`
  - `/register`
  - `/profile`
- Preserve existing API route shapes where practical:
  - `/api/v1/stylist/query`
  - `/api/v1/stylist/analyze-body`
  - `/api/v1/catalog/products`
  - `/api/v1/vton/try-on` as compatibility adapter
- Also expose real backend route:
  - `/api/v1/claid/try-on`
- Add measurement endpoint:
  - `/api/v1/body/measurements`

## Integration decisions

- Import and reuse real AI/backend service functions from `outfit_generator`.
- Replace demo API handlers in `ai-stylist-platform` with delegating/adapter handlers.
- Use Supabase browser auth in the frontend via ES module helpers copied from `outfit_generator`.
- Keep auth state in Supabase session, not `localStorage`.
- Keep `selectedProducts` in browser storage as temporary UI state for the try-on flow.
- Wire catalog page to real backend products endpoint.
- If backend ML import is unavailable, serve catalog from `outfit_generator\outfit_generator\catalog\sample_catalog.json` as a temporary runtime fallback so the visible UI stays functional.
- Wire chat page to real stylist endpoint.
- Wire try-on page directly to real backend-compatible payloads while keeping `/api/v1/vton/try-on` as a thin adapter for compatibility.

## Feature handling

- Saved outfits:
  - enable via Supabase `saved_outfits` from frontend using `outfit_payload` JSON
- Favorites / liked items:
  - defer and disable in UI because current catalog IDs are local string IDs and do not safely match `liked_items.product_id` UUID foreign key requirements
- Search-by-image:
  - keep unavailable and return a clear non-ready response if surfaced; no fake enablement
- Backend dependency gaps:
  - if `faiss` / other ML dependencies are not installed, return clear `503` messages for AI endpoints instead of silent mock fallbacks
- Measurement from image:
  - expose endpoint now
  - require `height_cm`
  - require configured model asset paths
  - return clear unavailable error if assets are missing

## Schema/payload adapters

- `/api/v1/vton/try-on`:
  - accept `user_photo` and `clothing_photo`
  - map to real try-on handler fields
  - accept optional `garment_size`, default from UI selection
- Body-analysis path:
  - keep existing body-type UI response stable
  - add fit-readiness metadata instead of inventing unavailable measurements
- Try-on page:
  - submit `model_file`, `clothing_file`, `garment_size`
  - optionally call measurement endpoint first when height is supplied

## Planned later cleanup

- Remove demo/mock API code from `ai-stylist-platform/main.py` after real wiring is stable
- Remove unused localStorage auth flow code from templates
- Remove unused mock outfit/product arrays from templates once replaced
- Reassess unused helper/demo files after validation
