# Integration Changelog

## What changed

- Replaced the deleted `ai-stylist-platform` runtime entrypoint with a single integrated FastAPI app in `ai-stylist-platform\ai-stylist-platform\main.py`.
- Kept `ai-stylist-platform` as the user-facing web app and delegated API work to `outfit_generator` where the backend can load successfully.
- Added lazy backend loading so the web UI can still boot even when optional ML dependencies are not installed.
- Added a catalog JSON fallback from `outfit_generator\outfit_generator\catalog\sample_catalog.json` to keep the visible catalog usable when the backend import fails on ML dependencies.
- Stabilized backend boot by isolating optional ML/search imports from global startup.
- Added reproducible setup artifacts and root-level run instructions.

## Routes and pages wired

- Preserved page routes:
  - `/`
  - `/chat`
  - `/tryon`
  - `/analysis`
  - `/catalog`
  - `/outfits`
  - `/login`
  - `/register`
  - `/profile`
- Preserved / exposed API routes:
  - `GET /api/health`
  - `POST /api/v1/stylist/query`
  - `POST /api/v1/stylist/analyze-body`
  - `GET /api/v1/catalog/products`
  - `POST /api/v1/claid/try-on`
  - `POST /api/v1/vton/try-on`
  - `POST /api/v1/body/measurements`
  - `POST /api/v1/stylist/search-by-image`

## Auth flows made real

- Added frontend Supabase client helpers:
  - `static/js/supabase.js`
  - `static/js/auth.js`
  - `static/js/app-auth.js`
- Rewired login page to `supabase.auth.signInWithPassword`.
- Rewired register page to `supabase.auth.signUp` with user metadata.
- Rewired logout buttons to real `supabase.auth.signOut`.
- Replaced profile/session ownership from `localStorage` with Supabase session state.

## AI and backend wiring

- Chat page now posts to the real stylist endpoint contract at `/api/v1/stylist/query`.
- Try-on page now posts to `/api/v1/claid/try-on` with normalized backend field names:
  - `model_file`
  - `clothing_url`
  - `garment_size`
  - optional `body_measurements`
- Added `/api/v1/body/measurements` adapter around `measure_from_image.py`.
- Added clear `503` responses for backend/AI routes when runtime dependencies like `faiss` or measurement model assets are unavailable.
- Search-by-image now returns an explicit unavailable response instead of a silent dead path.
- `faiss` is now isolated to vector-search capability instead of blocking backend import.
- Qwen, CLIP, and MediaPipe runtime gaps now surface as route-scoped degradation or `503`s instead of global startup failure.
- Added a demo-readiness pass that tightened capability diagnostics, measurement asset discovery, and backend-driven blocked-feature responses.

## Payload and schema mismatches resolved

- Reconciled frontend try-on field names from:
  - `user_photo`
  - `clothing_photo`
- to backend-compatible fields:
  - `model_file`
  - `clothing_file` or `clothing_url`
- Added frontend garment size selection for try-on.
- Added optional fit-measurement pre-step in try-on using `/api/v1/body/measurements`.
- Added `fit_ready` / measurement endpoint metadata on body-analysis responses.

## Persistence wiring

- Added `static/js/saved-outfits.js` for Supabase `saved_outfits` reads/writes/deletes.
- Profile page and saved outfits page now read real `saved_outfits`.
- Chat and try-on pages can save outfit payloads to Supabase.
- Favorites now persist through the same Supabase project using `saved_outfits` rows tagged with `source_type = "favorite_product"`.

## Features intentionally deferred or disabled

- Legacy `liked_items` remains unused by the visible UI because current catalog product IDs still do not safely match the Supabase `liked_items.product_id` UUID contract.
- Search-by-image remains unavailable because the CLIP runtime is not installed and the FAISS index file is not built yet.
- Measurement endpoint requires:
  - `POSE_MODEL_PATH` or `MEDIAPIPE_POSE_MODEL_PATH`
  - `SEG_MODEL_PATH` or `MEDIAPIPE_SEG_MODEL_PATH`
- Full stylist model mode still depends on installing the Qwen runtime stack, especially `torch` and `transformers`.
- Body analysis remains unavailable on this machine because the installed `mediapipe` build does not expose `mediapipe.solutions`, which the current analyzer depends on.

## Stabilization updates

- Added `STABILIZATION_PLAN.md`
- Added `DEPENDENCY_MATRIX.md`
- Added `ENV_CHECK_REPORT.md`
- Added `FINAL_SMOKE_REPORT.md`
- Added `README.md`
- Added `scripts\bootstrap_local.ps1`
- Expanded `GET /api/health` into a structured capability report with:
  - backend import status
  - optional subsystem availability
  - measurement readiness
  - catalog source
  - major route callability flags

## Demo-ready polish updates

- Installed and validated `faiss-cpu`; image-search capability is now importable but still blocked until CLIP runtime and a built index exist.
- Installed and validated `mediapipe` and `opencv-python`; the body-analysis blocker is now identified as a MediaPipe API mismatch rather than a generic missing dependency.
- Added measurement model path resolution with:
  - env aliases
  - default local asset lookup under `assets\measurement` and `models\measurement`
  - exact missing-path diagnostics in `/api/health` and route errors
- Replaced the frontend hardcoded image-search `503` response with a backend proxy so operators now see the real blocker.
- Updated chat responses to state when heuristic fallback mode is being used.
- Added demo/operator docs:
  - `DEMO_READY_PLAN.md`
  - `CHAT_RUNTIME_REPORT.md`
  - `BODY_ANALYSIS_RUNTIME_REPORT.md`
  - `MEASUREMENT_SETUP_GUIDE.md`
  - `IMAGE_SEARCH_STATUS.md`
  - `FAVORITES_MAPPING_REPORT.md`
  - `DEMO_QA_CHECKLIST.md`

## Final demo polish updates

- Added a compact footer demo-status widget driven by `GET /api/health`.
- Updated the homepage to distinguish ready demo flows from setup-required ML features.
- Added a visible fallback-mode pill on the chat page.
- Improved page-level messaging on chat, try-on, login, register, and analysis to make errors friendlier without hiding the real limitation.
- Initially changed favorites UI from clickable-looking alerts to clearly disabled states in catalog and profile.
- Added explicit confirmed-account guidance on login/register for the live Supabase demo flow.
- Added presenter/operator artifacts:
  - `DEMO_POLISH_PLAN.md`
  - `BROWSER_QA_REPORT.md`
  - `DEMO_SCRIPT.md`
  - `DEMO_OPERATOR_CHECKLIST.md`
  - `DEMO_AUTH_RUNBOOK.md`

## Favorites fix updates

- Enabled visible favorites with the minimum safe adapter contract instead of reviving the broken `liked_items` UUID path.
- `GET /api/v1/catalog/products` now additively returns:
  - `catalog_display_id`
  - `favorite_key`
  - `favorite_product_uuid`
- Added `static/js/favorites.js` for authenticated favorite reads/writes through Supabase.
- Catalog page now toggles real favorites and preserves the current product-card layout.
- Profile and outfits now show the same favorite items using the shared `favorite_key`.
- `GET /api/health` now reports favorites as enabled when Supabase config is present.

## Exact files changed

- `IMPLEMENTATION_PLAN.md`
- `STABILIZATION_PLAN.md`
- `DEPENDENCY_MATRIX.md`
- `ENV_CHECK_REPORT.md`
- `FINAL_SMOKE_REPORT.md`
- `README.md`
- `scripts\bootstrap_local.ps1`
- `DEMO_READY_PLAN.md`
- `DEMO_POLISH_PLAN.md`
- `CHAT_RUNTIME_REPORT.md`
- `BODY_ANALYSIS_RUNTIME_REPORT.md`
- `MEASUREMENT_SETUP_GUIDE.md`
- `IMAGE_SEARCH_STATUS.md`
- `FAVORITES_MAPPING_REPORT.md`
- `FAVORITES_FIX_REPORT.md`
- `DEMO_QA_CHECKLIST.md`
- `BROWSER_QA_REPORT.md`
- `DEMO_SCRIPT.md`
- `DEMO_OPERATOR_CHECKLIST.md`
- `ai-stylist-platform\ai-stylist-platform\main.py`
- `ai-stylist-platform\ai-stylist-platform\static\js\supabase.js`
- `ai-stylist-platform\ai-stylist-platform\static\js\auth.js`
- `ai-stylist-platform\ai-stylist-platform\static\js\app-auth.js`
- `ai-stylist-platform\ai-stylist-platform\static\js\demo-ui.js`
- `ai-stylist-platform\ai-stylist-platform\static\js\favorites.js`
- `ai-stylist-platform\ai-stylist-platform\static\js\saved-outfits.js`
- `ai-stylist-platform\ai-stylist-platform\templates\base.html`
- `ai-stylist-platform\ai-stylist-platform\templates\login.html`
- `ai-stylist-platform\ai-stylist-platform\templates\register.html`
- `ai-stylist-platform\ai-stylist-platform\templates\profile.html`
- `ai-stylist-platform\ai-stylist-platform\templates\chat.html`
- `ai-stylist-platform\ai-stylist-platform\templates\tryon.html`
- `ai-stylist-platform\ai-stylist-platform\templates\analysis.html`
- `ai-stylist-platform\ai-stylist-platform\templates\catalog.html`
- `ai-stylist-platform\ai-stylist-platform\templates\outfits.html`
- `outfit_generator\outfit_generator\catalog\database.py`
- `outfit_generator\outfit_generator\models\clip_search.py`
- `outfit_generator\outfit_generator\models\qwen_chatbot.py`
- `outfit_generator\outfit_generator\models\body_analyzer.py`
- `outfit_generator\outfit_generator\main.py`
