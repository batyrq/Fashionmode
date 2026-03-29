# Image Search Status

## Status

- Enabled: no
- Route: `POST /api/v1/stylist/search-by-image`
- Current route behavior: proxied to the real backend and returns a precise `503` reason

## Current prerequisites

- `faiss-cpu`
- `torch`
- `transformers`
- CLIP model load for `openai/clip-vit-base-patch32`
- built FAISS index file at:
  - `outfit_generator\outfit_generator\data\faiss_index.index`

## Current machine state

- `faiss-cpu`: installed
- FAISS import: available
- CLIP runtime: unavailable because `torch` is missing
- FAISS index file: not present

## Why it is still disabled

This repo does not currently have all three pieces ready at once:

1. CLIP runtime
2. built FAISS index
3. index load path exercised by a real bootstrap/build workflow

Because of that, image search stays disabled for the demo.

## Health/debug signals

- `/api/health`
  - `features.search_by_image_callable = false`
  - `route_notes.search_by_image_status = missing_clip_runtime`
  - `blockers.search_by_image` explains the exact current blocker

## Re-enable checklist

1. Install:
   - `torch`
   - `transformers`
2. Confirm CLIP runtime loads in `/api/health`
3. Build and persist `faiss_index.index`
4. Restart the app
5. Confirm:
   - `features.search_by_image_callable = true`

## Embeddings/index location

- FAISS index path: `outfit_generator\outfit_generator\data\faiss_index.index`
- Product embedding source is expected to come from the catalog plus the CLIP embedding pipeline in `outfit_generator\outfit_generator\models\clip_search.py`

## Demo rule

For the demo, keep image search explicitly unavailable. The route is safe to call, but it must not be presented as ready until CLIP runtime and the persisted index both exist.
