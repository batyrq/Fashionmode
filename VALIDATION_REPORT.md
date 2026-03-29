# Validation Report

## What was tested

- Python syntax compilation for `ai-stylist-platform\ai-stylist-platform\main.py`
- App import and route registration
- Bootstrap script execution with `powershell -ExecutionPolicy Bypass -File ".\scripts\bootstrap_local.ps1"`
- Page render smoke test with FastAPI test client:
  - `/`
  - `/login`
  - `/register`
  - `/chat`
  - `/tryon`
  - `/analysis`
  - `/catalog`
  - `/outfits`
  - `/profile`
  - `/api/health`
- Catalog contract smoke test for:
  - `catalog_display_id`
  - `favorite_key`
  - `favorite_product_uuid`
- Favorites flow hardening review for:
  - dedupe-on-read
  - remove-all-on-unfavorite
  - auth-restoration fallback
  - rapid-click guards
- Measurement endpoint existence check at `POST /api/v1/body/measurements`
- Try-on route existence checks for:
  - `POST /api/v1/claid/try-on`
  - `POST /api/v1/vton/try-on`
- Static code verification that:
  - login uses `signIn`
  - register uses `signUp`
  - chat calls `/api/v1/stylist/query`
  - try-on calls `/api/v1/claid/try-on`
  - try-on can call `/api/v1/body/measurements`
- Auth-page render verification that `/login` and `/register` contain explicit demo guidance about confirmed Supabase accounts
- Repo/config inspection for a local Supabase setting that disables email confirmation

## Passed

- `python -m py_compile ai-stylist-platform\ai-stylist-platform\main.py`
- `scripts\bootstrap_local.ps1` now runs successfully without PowerShell parsing errors.
- App import succeeds after installing the lightweight web dependencies.
- All main pages returned `200` in test-client smoke tests.
- `GET /api/health` returned `200`.
- `GET /api/health` now reports `features.favorites_enabled = true`.
- `GET /api/v1/catalog/products` returned `200` and catalog items now expose a canonical favorite-safe identifier via `favorite_key`.
- `POST /api/v1/body/measurements` is registered and returned validation errors when required form fields were missing, confirming endpoint presence.
- `POST /api/v1/claid/try-on` now returns a clean `400` for an empty request instead of a `500`.
- `POST /api/v1/vton/try-on` still returns request-validation errors for missing required files, confirming compatibility-route registration.
- Frontend templates now reference the intended real auth/API paths.
- Favorites now dedupe consistently through the shared `listFavoriteProducts()` helper used by `/catalog`, `/profile`, and `/outfits`.
- Unfavoriting now removes all matching duplicate `favorite_product` rows for the same `favorite_key`.
- Catalog favorite buttons now have request-pending guards and refresh when Supabase auth state changes.
- Public Supabase sign-up endpoint is reachable from this environment.
- Login and register pages now explicitly warn the operator when a confirmed Supabase account is needed for the live demo.
- Register page now distinguishes between:
  - account created and ready to use now
  - account created but blocked on email confirmation
- Rendered `/login` and `/register` HTML both contain the new `Supabase` and `live-demo` guidance copy.
- No repo-local Supabase config or env-based switch was found for disabling email confirmation.
- The safest path identified is a demo-only Supabase dashboard change, documented in `DEMO_NO_EMAIL_CONFIRMATION_SETUP.md`.

## Failed or blocked

- Full browser-level favorites validation still requires a real authenticated Supabase session in the browser.
- A fresh Supabase sign-up was created successfully, but password sign-in was blocked with `email_not_confirmed`, so a complete logged-in browser pass could not be finished in this thread.
- No preconfigured confirmed demo-account flow or credentials were found in the repo.
- Fresh registration plus immediate login still does not work in the current live project because the dashboard setting has not been changed from this repo.
- The measurement endpoint cannot complete inference without configured model asset paths.
- End-to-end browser validation for Supabase login/save flows was not executed automatically because it requires real browser interaction plus valid Supabase project setup.

## Manual setup still required

- For full stylist-model mode and CLIP runtime, install:
  - `torch`
  - `transformers`
- For measurement inference, provide model assets:
  - `POSE_MODEL_PATH` or `MEDIAPIPE_POSE_MODEL_PATH`
  - `SEG_MODEL_PATH` or `MEDIAPIPE_SEG_MODEL_PATH`
- For browser validation, use a real Supabase user account to exercise add/remove favorite persistence
- If email confirmation is enabled, use a pre-confirmed account or confirm the mailbox before running the favorites demo path
- Use `DEMO_AUTH_RUNBOOK.md` as the presenter/operator path for auth-sensitive demo steps
- Use `DEMO_NO_EMAIL_CONFIRMATION_SETUP.md` for the exact demo-project setup and rollback steps
- No repo-local demo-account credential or bypass flow was added; the demo still depends on a real confirmed Supabase user
- Configure measurement model assets:
  - `POSE_MODEL_PATH` or `MEDIAPIPE_POSE_MODEL_PATH`
  - `SEG_MODEL_PATH` or `MEDIAPIPE_SEG_MODEL_PATH`
- Ensure Supabase environment values are correct for the target deployment:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY` or `SUPABASE_PUBLISHABLE_KEY`
- Ensure `CLAID_API_KEY` remains configured for real try-on execution

## 2026-03-29 admin and AI runtime validation

### Environment and CUDA

- `nvidia-smi` returned a healthy NVIDIA runtime for `NVIDIA GeForce RTX 5060 Laptop GPU`
- `python -c "import torch; ..."` returned:
  - `torch 2.8.0+cu128`
  - `cuda_available True`
  - `device_count 1`

### Live integrated app checks on port `8012`

- `GET /` -> `200`
- `GET /catalog` -> `200`
- `GET /outfits` -> `200`
- `GET /api/health` -> `200`
- `GET /api/v1/admin/catalog/me` without auth -> `401`
- `POST /api/v1/admin/catalog/products` without auth -> `401`
- `DELETE /api/v1/admin/catalog/products/nonexistent` without auth -> `401`

### Catalog and favorites regression surface

- `GET /api/v1/catalog/products` returned `10` products
- catalog payload still includes:
  - `id`
  - `catalog_display_id`
  - `favorite_key`
  - `favorite_product_uuid`

### AI route checks

- `POST /api/v1/stylist/query` -> `200`
  - response message: `Generated 3 outfits using heuristic fallback mode`
- `POST /api/v1/stylist/search-by-image` -> `200`
  - returned `similar_products`
- `POST /api/v1/stylist/analyze-body` -> `503`
  - blocker: installed `mediapipe` package does not expose `mediapipe.solutions`
- `POST /api/v1/body/measurements` -> `503`
  - blocker: missing pose/segmentation model asset files

### Standalone backend model checks

- standalone `QwenStylistChatbot()` initialization succeeded on `device='cuda'`
- standalone capability status returned:
  - `mock_mode: false`
  - `model_loaded: true`

### Remaining validation blockers

- Admin add/delete was not exercised with a real authenticated admin session in this thread
- Full live integrated Qwen mode remains unverified because the running app still reports heuristic fallback despite successful standalone GPU loading

## 2026-03-29 live Qwen follow-up

### What was tested

- fresh reload-backed integrated servers on ports `8014`, `8015`, `8016`, `8018`, `8019`, and `8020`
- `GET /api/health` before chat initialization
- `POST /api/v1/stylist/query`
- backend stderr logs for Qwen initialization

### What passed

- standalone Qwen load still succeeds on CUDA
- fresh integrated reload servers now expose richer chat capability status:
  - `device`
  - `load_error`
- fallback recovery logic is now present if the app is holding a stale mock chatbot while Qwen runtime is available

### What failed or remained blocked

- live integrated chat still falls back on this machine in fresh reload servers
- the blocker is now explicit in `/api/health`:
  - `The paging file is too small for this operation to complete. (os error 1455)`
- live route responses remain:
  - `Generated 3 outfits using heuristic fallback mode`

### Evidence

- fresh port `8020`:
  - `GET /api/health` before chat init -> `mode: not_initialized`
  - `POST /api/v1/stylist/query` -> `200`
  - response message -> `Generated 3 outfits using heuristic fallback mode`
  - `GET /api/health` after chat init -> `mode: heuristic_fallback`
  - `load_error` -> `The paging file is too small for this operation to complete. (os error 1455)`

## 2026-03-29 live Qwen no-reload validation

### What was tested

- terminated leftover `python.exe` server workers from earlier reload experiments
- started a fresh integrated server without `--reload` on port `8022`
- checked `/api/health` before first chat request
- posted `{"query": "casual outfit"}` to `/api/v1/stylist/query`
- checked `/api/health` after chat initialization

### What passed

- `GET /api/health` before chat init -> `mode: not_initialized`
- `POST /api/v1/stylist/query` -> `200`
- response message did not include `heuristic fallback mode`
- `GET /api/health` after chat init -> `mode: full`
- `model_loaded: true`
- `device: cuda`
- `load_error: null`

### Operator conclusion

- no-reload mode materially helped on this machine
- the strongest operational path for full Qwen is a single-process integrated server
- reload-backed mode remains higher risk because it amplifies Windows virtual-memory pressure

## 2026-03-29 local measurement and admin-upload validation

### What was changed before validation

- downloaded measurement assets into `assets\measurement`
- enabled automatic discovery of `pose_landmarker_lite.task`
- switched measurement execution to an ASCII-safe subprocess runtime
- changed admin catalog creation to require `multipart/form-data` with a local `image_file`

### Runtime checks

- `powershell -ExecutionPolicy Bypass -File ".\scripts\bootstrap_local.ps1"` -> passed
- `GET /api/health` on port `8012` -> `200`
- health now reports:
  - `features.measurement_callable = true`
  - `config.measurement.ready = true`
  - `config.measurement.execution_mode = subprocess_ascii_runtime`
  - `features.body_analysis_callable = false`

### Analysis and measurement routes

- `GET /analysis` -> `200`
- `POST /api/v1/body/measurements` with `tmp_search_image.jpg` and `height_cm=170` -> `200`
  - returned real measurements and `fit_ready = true`
- `POST /api/v1/stylist/analyze-body` with the same image -> `503`
  - blocker remains: installed `mediapipe` package does not expose `mediapipe.solutions`

### Admin catalog create/delete boundary checks

- `GET /catalog` -> `200`
- `POST /api/v1/admin/catalog/products` without auth and with a local uploaded file -> `401`
- `DELETE /api/v1/admin/catalog/products/nonexistent` without auth -> `401`
- `POST /api/v1/admin/catalog/products` with URL-only fields and no file -> `422`
  - proves `image_file` is now required for admin creation

### Remaining validation gap

- a real authenticated admin create/delete flow was not exercised in this thread because no admin Supabase session was supplied
