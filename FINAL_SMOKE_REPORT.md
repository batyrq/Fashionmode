# Final Smoke Report

Date: 2026-03-29

## Results

| Test | Result | Evidence | Blocker if failed | Issue type |
|---|---|---|---|---|
| App boot | pass | Integrated app imports and responds through `fastapi.testclient.TestClient` | none | code-level |
| Homepage render | pass | `GET /` -> `200` | none | n/a |
| Login page render | pass | `GET /login` -> `200` | none | n/a |
| Register page render | pass | `GET /register` -> `200` | none | n/a |
| Catalog page render | pass | `GET /catalog` -> `200` | none | n/a |
| Chat page render | pass | `GET /chat` -> `200` | none | n/a |
| Try-on page render | pass | `GET /tryon` -> `200` | none | n/a |
| Analysis page render | pass | `GET /analysis` -> `200` | none | n/a |
| Catalog API | pass | `GET /api/v1/catalog/products` -> `200` | none | n/a |
| Chat endpoint | pass with degradation | `POST /api/v1/stylist/query` -> `200`; query `Need a casual outfit under 50000` returned 3 outfits | full Qwen mode still needs `torch` and `transformers` | environment-level |
| Health endpoint | pass | `GET /api/health` -> `200` with `features`, `route_notes`, `blockers`, backend capabilities, and measurement path checks | none | n/a |
| Canonical try-on route | pass | `POST /api/v1/claid/try-on` with tiny PNG inputs and `garment_size=M` returned `200` with a Claid output image URL | future runs still depend on external Claid availability | external-service |
| Compatibility try-on adapter | pass | `POST /api/v1/vton/try-on` with legacy field names returned the same successful Claid response | future runs still depend on external Claid availability | external-service |
| Body analysis endpoint | blocked explicitly | `POST /api/v1/stylist/analyze-body` -> `503` with `mediapipe.solutions` blocker | installed `mediapipe` wheel does not expose the legacy solutions API required by current analyzer | environment/runtime-level |
| Measurement endpoint | blocked explicitly | `POST /api/v1/body/measurements` -> `503` with resolved missing pose and segmentation file paths | local model assets missing | asset-level |
| Search-by-image endpoint | blocked explicitly | `POST /api/v1/stylist/search-by-image` -> `503` and returns backend-driven CLIP blocker | `torch` missing and FAISS index file not built | environment-level |
| Favorites UI state | pass | Catalog/profile still show favorites as unavailable instead of pretending to save | UUID mapping to Supabase `liked_items.product_id` not solved | data-level |
| UX status surfaces | pass | Homepage/footer/chat/try-on/analysis now render explicit demo-state UI markers | none | n/a |

## Key health evidence

- `app.bootable = true`
- `backend.importable = true`
- `features.catalog = true`
- `features.supabase_auth = true`
- `features.saved_outfits = true`
- `features.chat_route_callable = true`
- `features.tryon_route_callable = true`
- `features.body_analysis_callable = false`
- `features.measurement_callable = false`
- `features.search_by_image_callable = false`
- `features.favorites_enabled = false`
- `route_notes.chat_mode = heuristic_fallback`
- `route_notes.search_by_image_status = missing_clip_runtime`

## Manual browser QA still recommended

- Supabase sign-up/sign-in/sign-out in a real browser session
- try-on flow with valid real photos
- saved outfit create/delete flow against the actual Supabase project
- analysis page UX for blocked body-analysis and measurement states
- visual layout of the new footer demo-status widget on narrow screens

## Overall assessment

The app is demo-ready for the stable integrated prototype scope:

- core app boot is stable
- chat is real and returns catalog-backed outfits in fallback mode
- catalog and saved outfits work
- try-on is currently producing real Claid output in this environment
- blocked AI features are isolated cleanly and diagnosed explicitly
- page-level UX now labels limited features instead of making them feel broken
