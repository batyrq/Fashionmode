# Demo-Ready Plan

## Fully enable now

- Keep `ai-stylist-platform\ai-stylist-platform\main.py` as the single runtime entrypoint.
- Keep catalog, Supabase auth, saved outfits, chat fallback mode, try-on routing, and health diagnostics working.
- Make `/api/v1/stylist/search-by-image` proxy to the real backend route so it reports the real blocker instead of a hardcoded placeholder.
- Make measurement setup operator-proof with env aliases plus default local asset lookup under `assets/measurement` and `models/measurement`.

## Keep explicitly disabled

- Full Qwen chat mode: environment-blocked by missing `torch` and `transformers`, plus model download/load.
- Body analysis: environment/runtime-blocked because the installed `mediapipe` wheel does not expose `mediapipe.solutions`, which the current analyzer depends on.
- Measurement inference: asset-blocked until pose and segmentation model files exist locally.
- Search-by-image: runtime-blocked until CLIP runtime is installed and the FAISS index is built.
- Favorites: data-blocked until catalog item IDs map safely to Supabase `public.products.id` UUIDs.

## Blocker types

- Code-blocked: none on the primary demo flows after this pass.
- Environment-blocked: full chat mode, CLIP image search runtime, current body-analysis runtime.
- Asset-blocked: measurement models.
- Data-contract blocked: favorites UUID mapping.

## Demo-ready acceptance criteria

- App boots from the single integrated entrypoint without optional ML extras.
- `/api/health` reports exact capability state and blockers.
- Homepage, login, register, catalog, chat, try-on, and analysis pages render.
- Chat returns real catalog-backed outfit recommendations in heuristic fallback mode.
- Try-on routes are callable and fail actionably on invalid input or missing external prerequisites.
- Disabled features never crash boot and never pretend to be working.
