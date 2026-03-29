# Terricon AI Stylist

## Primary runtime

- Visible app: `ai-stylist-platform\ai-stylist-platform`
- Primary entrypoint: `ai-stylist-platform\ai-stylist-platform\main.py`

Start the app with:

```powershell
uvicorn main:app --reload --app-dir "ai-stylist-platform\ai-stylist-platform"
```

If you are specifically validating full Qwen mode on Windows, prefer a single-process run:

```powershell
uvicorn main:app --app-dir "ai-stylist-platform\ai-stylist-platform" --port 8012
```

## Fast bootstrap

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\bootstrap_local.ps1"
```

## Minimum working demo

If you just need the hackathon demo to boot and show the strongest working flow:

1. Run the bootstrap script.
2. Start the app:

```powershell
uvicorn main:app --reload --app-dir "ai-stylist-platform\ai-stylist-platform"
```

3. Check readiness:

```powershell
curl http://127.0.0.1:8000/api/health
```

4. Open these tabs:
   - `/`
   - `/catalog`
   - `/chat`
   - `/tryon`
   - `/profile`

Best live-demo flow:

- pick a product in catalog
- ask chat for an outfit
- save the outfit
- run try-on
- show the saved result in profile

## Minimal install for a demo-safe local boot

This gives you:

- app boot
- main pages
- Supabase auth wiring
- catalog
- saved outfits
- health diagnostics
- stylist chat in heuristic fallback mode
- try-on route wiring

```powershell
python -m pip install -r "ai-stylist-platform\ai-stylist-platform\requirements.txt"
python -m pip install "requests>=2.31.0" "pydantic>=2.5.0" "loguru>=0.7.0" "numpy>=1.26,<2.1" "httpx"
```

## Extra installs and what they unlock

### Search foundation

```powershell
python -m pip install "faiss-cpu>=1.13.0"
```

Unlocks:

- FAISS importability
- image-search dependency path becomes diagnosable

Still not enough by itself for image search. You also need CLIP runtime plus a built index.

### Full chat mode and CLIP runtime

If the machine has a compatible NVIDIA GPU, prefer the CUDA wheel:

```powershell
nvidia-smi
python -m pip install --upgrade --force-reinstall --no-deps --index-url https://download.pytorch.org/whl/cu128 torch torchvision
python -m pip install "transformers>=4.52.4,<5.0.0" "accelerate>=0.25.0" "sentencepiece>=0.1.99" "protobuf>=3.20.0"
```

If there is no NVIDIA GPU, use the normal PyPI build instead:

```powershell
python -m pip install "torch>=2.8.0" "torchvision>=0.23.0" "transformers>=4.52.4,<5.0.0" "accelerate>=0.25.0" "sentencepiece>=0.1.99" "protobuf>=3.20.0"
```

Unlocks:

- potential full Qwen stylist mode
- CLIP runtime required for image search

Still required after install:

- model download/load
- enough local resources to initialize the models

Notes from this machine:

- CUDA is available and PyTorch sees `NVIDIA GeForce RTX 5060 Laptop GPU`
- standalone Qwen now loads on GPU successfully
- a clean single-process integrated server can also load Qwen successfully on GPU
- reload-backed Windows runs are still more likely to hit paging-file pressure (`os error 1455`)

### Body-analysis runtime attempt

```powershell
python -m pip install "mediapipe>=0.10.0" "opencv-python>=4.8.0"
```

Current note for this machine:

- those packages install cleanly
- the installed `mediapipe` wheel does not expose `mediapipe.solutions`
- the current body analyzer still depends on that API
- result: body analysis remains intentionally disabled and reports a precise blocker

## Required env vars

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` or `SUPABASE_PUBLISHABLE_KEY`
- `CLAID_API_KEY`

## Supabase demo auth note

- This project uses real Supabase auth.
- In the current live project, fresh sign-ups may require email confirmation before password login works.
- The safest demo fix is to disable `Confirm email` in the Supabase demo project only.
- If you do not disable it, prepare one confirmed demo account in advance and use it for `/login`, favorites, profile, and saved-outfit flows.
- See `DEMO_NO_EMAIL_CONFIRMATION_SETUP.md` for the exact setup and rollback steps.
- See `DEMO_AUTH_RUNBOOK.md` for the operator flow.

## Measurement setup

Supported env var aliases:

- `POSE_MODEL_PATH`
- `MEDIAPIPE_POSE_MODEL_PATH`
- `SEG_MODEL_PATH`
- `MEDIAPIPE_SEG_MODEL_PATH`

Supported default local asset locations:

- `assets\measurement\pose_landmarker_lite.task`
- `assets\measurement\pose_landmarker.task`
- `assets\measurement\image_segmenter.tflite`
- `assets\measurement\selfie_multiclass_256x256.tflite`
- `models\measurement\pose_landmarker_lite.task`
- `models\measurement\pose_landmarker.task`
- `models\measurement\image_segmenter.tflite`
- `models\measurement\selfie_multiclass_256x256.tflite`

## What works with minimal setup

- `/`
- `/login`
- `/register`
- `/catalog`
- `/chat`
- `/tryon`
- `/analysis`
- `GET /api/health`
- `GET /api/v1/catalog/products`
- `POST /api/v1/stylist/query` in heuristic fallback mode
- `POST /api/v1/claid/try-on` and `POST /api/v1/vton/try-on`
- `POST /api/v1/body/measurements` with the bundled local measurement assets
- compact demo-status widget in the footer

## What remains blocked unless you add more runtime/assets

- Full Qwen chat mode
- Body analysis
- Search-by-image

## Favorites

Favorites are now enabled in the visible demo build.

- Catalog items expose an additive `favorite_key` field alongside their existing display IDs.
- Favorite clicks persist to Supabase in `public.saved_outfits` with `source_type = "favorite_product"`.
- The canonical cross-page identity is `outfit_payload.favorite_key`.
- `/catalog`, `/profile`, and `/outfits` all read the same favorite records.

Why this shape was chosen:

- the current Supabase `public.products` table is empty in this environment
- the old `liked_items.product_id -> public.products.id` UUID path could not be used safely yet
- `saved_outfits` already has working auth/RLS and user ownership, so it was the smallest safe persistence path

## Admin catalog management

Admin catalog CRUD is now available without changing the visible app architecture.

- Admin role source: `public.profiles.role`
- Supported values already present in Supabase schema: `user`, `admin`, `moderator`
- Admin-only endpoints:
  - `GET /api/v1/admin/catalog/me`
  - `POST /api/v1/admin/catalog/products`
  - `DELETE /api/v1/admin/catalog/products/{product_id}`
- The current live app writes admin catalog changes to the JSON catalog that powers the visible runtime.
- New catalog items must be created through local image upload (`multipart/form-data` with `image_file`).
- Server-side enforcement checks the authenticated Supabase session plus the server-read profile role. The browser is not trusted by itself.

See `ADMIN_CATALOG_SETUP.md` for the exact SQL and operator steps.

## Health endpoint

Check:

```powershell
curl http://127.0.0.1:8000/api/health
```

Important fields:

- `features`
  - shows which major user-facing capabilities are callable
- `route_notes.chat_mode`
  - `heuristic_fallback` or fuller model mode
- `route_notes.search_by_image_status`
  - reports whether FAISS, CLIP runtime, or index build is the blocker
- `blockers`
  - exact current reason for chat, body analysis, measurement, image search, and favorites limitations

Favorites-specific fields to watch:

- `features.favorites_enabled`
  - `true` means the visible demo build can persist favorites through Supabase
- `config.supabase`
  - confirms the frontend has the config required for auth-backed favorite actions

## Demo-ready definition

The app is demo-ready on a local machine when:

- it boots from the single integrated entrypoint
- `/api/health` is green for the core routes
- catalog works
- Supabase login/register/logout work
- favorites can be added in catalog and shown again in profile/outfits
- chat returns real catalog-backed outfits, even if fallback mode is active
- try-on routes are callable and fail actionably
- disabled features are explicit and non-breaking

## Presenter note

For this build, the strongest demo path is:

- catalog
- favorites
- stylist chat
- Claid try-on
- saved outfits/profile

Treat body analysis and image search as explicitly out of scope for the live demo unless you have separately finished their local setup.
