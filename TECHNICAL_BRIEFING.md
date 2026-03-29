# Technical Briefing

## Executive Summary

This project is a hackathon-safe fashion AI web app with one visible runtime:

- User-facing app: `ai-stylist-platform/ai-stylist-platform/main.py`
- Backend logic source: `outfit_generator/outfit_generator/main.py`

The visible app is a FastAPI + Jinja web app that serves the demo UI and forwards AI/catalog requests through adapter routes into the backend modules from `outfit_generator`. The system is intentionally designed to keep optional ML features from crashing the whole app: chat can fall back to heuristic recommendations, try-on can stay available even if search/image-analysis extras are missing, and blocked features report explicit status through `/api/health`.

What is strongest in the current build:

- Real Supabase auth and session-based saved data
- Real catalog-backed stylist recommendations
- Real Claid-based virtual try-on
- Clear health/capability diagnostics
- Graceful degradation for optional ML paths

What is still limited:

- Full Qwen model mode is optional and currently falls back when `torch` / `transformers` are unavailable
- Body analysis depends on the legacy `mediapipe.solutions` API and is blocked in the current environment
- Measurement extraction needs local model assets
- Search-by-image needs CLIP runtime plus a built FAISS index

## Architecture Overview

### Runtime Shape

The project currently runs as a single web product, but it is built from two codebases:

1. `ai-stylist-platform`
   - Owns the visible pages, navigation, template rendering, auth UI, saved/favorites UI, and demo-safe status UX.
   - Exposes the primary local entrypoint.

2. `outfit_generator`
   - Owns the catalog engine, chat intent parsing and outfit generation, try-on backend logic, optional body analysis, optional image search, and Claid API integration.

The frontend runtime dynamically imports the backend module and exposes a unified API surface to the browser. That means the judges can be told truthfully:

- “We preserved one clean visible app for the demo.”
- “The backend AI and catalog logic is modular and mounted behind adapter routes.”
- “Optional ML subsystems are isolated so the app still boots if a specific local extra is missing.”

### High-Level Request Flow

1. Browser hits `ai-stylist-platform` FastAPI app.
2. Jinja templates render pages and inject Supabase public config.
3. Frontend JS calls:
   - Supabase directly for auth and saved data
   - local API routes for catalog, chat, try-on, body analysis, measurements, and health
4. Those local API routes either:
   - serve directly from the frontend runtime, or
   - call into backend services loaded from `outfit_generator`
5. Backend services use:
   - JSON catalog data
   - optional ML libraries/models
   - external Claid API for try-on
   - Supabase for auth/session-owned persistence on the frontend side

## AI Models Used

This section separates active runtime usage from optional or blocked components.

### 1. Qwen2.5-VL-3B-Instruct

- Model: `Qwen/Qwen2.5-VL-3B-Instruct`
- Referenced in: `outfit_generator/outfit_generator/config.py`, `outfit_generator/outfit_generator/models/qwen_chatbot.py`
- Purpose:
  - Analyze user fashion requests
  - Extract style intent, colors, budget, category, occasion, sizes
  - Generate outfit recommendations from catalog items
- Runtime status:
  - Optional
  - Degraded in current demo build when `torch` / `transformers` are unavailable
- Dependency/runtime needs:
  - `torch`
  - `transformers`
- What happens if unavailable:
  - `QwenStylistChatbot` enters `mock_mode`
  - query parsing falls back to rule-based heuristics
  - outfit generation falls back to deterministic `OutfitCombiner`

### 2. CLIP Vision/Text Embeddings

- Model family: Hugging Face CLIP
- Model: `openai/clip-vit-base-patch32`
- Referenced in: `outfit_generator/outfit_generator/config.py`, `outfit_generator/outfit_generator/models/clip_search.py`
- Purpose:
  - Analyze garment images for try-on prompt generation
  - Extract image/text embeddings
  - Support optional similarity/image search
- Runtime status:
  - Optional
  - Partially used conceptually by try-on flow
  - Search-by-image is blocked unless CLIP runtime is available and an index is built
- Dependency/runtime needs:
  - `torch`
  - `transformers`
  - PIL
  - optional `faiss-cpu` for search
- What happens if unavailable:
  - `ClipFashionSearch` stays import-safe
  - garment analysis can return fallback “unknown” analysis
  - search-by-image returns unavailable/empty behavior instead of crashing boot

### 3. FAISS

- Library/model family: FAISS vector index
- Referenced in: `outfit_generator/outfit_generator/catalog/database.py`, `outfit_generator/outfit_generator/models/clip_search.py`, `outfit_generator/outfit_generator/config.py`
- Purpose:
  - Optional vector similarity search for catalog embeddings
- Runtime status:
  - Optional
  - Not required for app boot
  - Search-by-image remains blocked unless index data exists
- Dependency/runtime needs:
  - `faiss-cpu`
  - CLIP embeddings
  - built index file at `outfit_generator/outfit_generator/data/faiss_index.index`
- What happens if unavailable:
  - vector search capability is reported as unavailable
  - search route remains isolated and non-fatal

### 4. MediaPipe Pose + Segmentation Tasks

- Model family: MediaPipe Tasks vision models
- Referenced in: `measure_from_image.py`
- Purpose:
  - Front-view body measurement extraction from an uploaded image
  - Size recommendation from silhouette and pose
- Runtime status:
  - Optional
  - Blocked unless local model assets are installed
- Dependency/runtime needs:
  - `mediapipe`
  - `opencv-python`
  - local pose landmarker asset
  - local segmentation asset
- What happens if unavailable:
  - measurement endpoint reports explicit setup-required errors
  - try-on still works without fit measurements

### 5. MediaPipe Legacy Solutions Pose

- Model/API family: MediaPipe legacy `mediapipe.solutions.pose`
- Referenced in: `outfit_generator/outfit_generator/models/body_analyzer.py`
- Purpose:
  - Coarse body type classification
  - Shoulder/hip/waist/leg ratio estimates
- Runtime status:
  - Optional
  - Blocked in the current environment because the installed package does not expose the legacy `mediapipe.solutions` API
- Dependency/runtime needs:
  - `mediapipe` with legacy solutions API
  - `opencv-python`
- What happens if unavailable:
  - body analysis route returns explicit unavailable diagnostics
  - page stays render-safe

### 6. Claid External AI Service

- Service: Claid API
- Referenced in: `outfit_generator/outfit_generator/utils/claid_client.py`, backend main, frontend runtime health checks
- Purpose:
  - Real virtual try-on / AI fashion model generation
- Runtime status:
  - Active in the current demo build if `CLAID_API_KEY` is configured
- Dependency/runtime needs:
  - `requests`
  - valid `CLAID_API_KEY`
  - network access to Claid endpoints
- What happens if unavailable:
  - try-on route returns explicit actionable errors
  - other app routes keep working

### 7. Deterministic Fashion Logic

- Modules:
  - `outfit_generator/outfit_generator/outfit/combiner.py`
  - `outfit_generator/outfit_generator/outfit/color_rules.py`
  - `outfit_generator/outfit_generator/catalog/database.py`
  - `outfit_generator/outfit_generator/models/tryon_prompt.py`
- Purpose:
  - Rule-based outfit composition
  - Color compatibility
  - Catalog filtering
  - Fit-aware try-on prompt engineering
- Runtime status:
  - Active
  - Critical for graceful fallback and demo stability

## Frameworks, Libraries, Services, and Tools

### Backend / Web Runtime

- FastAPI
  - Used in both runtimes
  - Powers page routes, JSON APIs, file uploads, and adapters
  - Critical

- Uvicorn
  - ASGI server for local runtime
  - Critical for local demo run

- Jinja2
  - Server-side template rendering for visible pages
  - Critical for current frontend approach

- Python Multipart
  - Handles upload forms for images/files
  - Critical for try-on, chat image input, and measurement routes

### Frontend Approach

- Server-rendered HTML templates + vanilla ES modules
  - No React/Vue/Next package manifest is present
  - Frontend logic is in template scripts and `static/js/*.js`
  - Critical

- Tailwind via CDN
  - Used for styling
  - Helpful but not architecturally critical

- Font Awesome via CDN
  - Iconography
  - Optional UX dependency

### Auth / Data / Persistence

- Supabase Auth
  - Used directly in browser JS through `@supabase/supabase-js`
  - Critical for login/register/profile/session flows

- Supabase Postgres + RLS
  - Referenced through migration SQL and frontend table usage
  - Critical for:
    - `profiles`
    - `saved_outfits`
    - other future-ready user/catalog tables

- Supabase Storage
  - Present in migration schema for `catalog-images`, `user-uploads`, `tryon-results`
  - Planned/partially scaffolded
  - Not the central path of the current visible demo

### AI / ML Libraries

- `transformers`
  - Needed for Qwen and CLIP
  - Optional for base boot, required for full local model runtime

- `torch`
  - Needed for Qwen and CLIP inference
  - Optional for base boot

- `faiss-cpu`
  - Optional similarity/index search
  - Not required for base boot

- `mediapipe`
  - Used by measurement and body analysis paths
  - Optional; current environment is partially incompatible for body analysis

- `opencv-python`
  - Used in measurement/body-analysis CV pipelines
  - Optional

- Pillow
  - Used throughout image ingestion/preprocessing
  - Critical for image-handling flows

- NumPy
  - Used in catalog vector support and CV/math paths
  - Important runtime dependency

### HTTP / Integration

- `requests`
  - Used for Claid API and remote image fetching
  - Critical for try-on integration

- `httpx`
  - Mentioned in bootstrap/runtime support
  - Helpful utility dependency for validation/runtime support

### Local Runtime / Ops

- PowerShell bootstrap script
  - `scripts/bootstrap_local.ps1`
  - Installs minimal runtime dependencies and documents optional extras
  - Critical for demo operability

- `/api/health`
  - Structured runtime diagnostics
  - Critical for demo reliability and operator confidence

## End-to-End System Explanation

### Landing and Navigation

- The browser opens the FastAPI app in `ai-stylist-platform`.
- Templates render the homepage and route users to:
  - chat
  - try-on
  - catalog
  - analysis
  - outfits/profile
- The footer shows a compact demo-health widget backed by `/api/health`.

Presenter-friendly explanation:

> “The visible site is one integrated web app. It serves the pages, checks system readiness, and routes feature requests into the backend logic.”

### Auth Flow

- Browser loads Supabase config from the page.
- `static/js/supabase.js` initializes a real Supabase client.
- `auth.js` uses:
  - `signUp`
  - `signInWithPassword`
  - `signOut`
  - `getSession`
  - `getUser`
- `app-auth.js` updates nav state and protects profile/outfits pages.
- Auth is real, session-based, and no longer uses `localStorage` as the source of truth.

Current limitation:

- Email confirmation behavior depends on Supabase project settings.

### Catalog Flow

- Browser requests `GET /api/v1/catalog/products`.
- Frontend runtime either:
  - uses the integrated backend product DB, or
  - falls back safely if needed
- Product data is normalized and augmented with:
  - existing `id`
  - `catalog_display_id`
  - `favorite_key`
  - `favorite_product_uuid`
- The catalog page supports:
  - search
  - category filtering
  - max-price filtering
  - selection of up to three items for try-on via browser `localStorage`

### Favorites Flow

- Favorites now use a hackathon-safe canonical `favorite_key`.
- They are stored in Supabase through `saved_outfits` with:
  - `source_type = "favorite_product"`
- This avoids relying on `liked_items.product_id` UUID mapping, which the visible catalog does not safely provide.
- Catalog, profile, and outfits pages all use the same canonical favorite identity.
- The client dedupes favorites and handles auth-required cases gracefully.

Presenter-friendly explanation:

> “Favorites are real user-linked records in Supabase. We used a stable catalog-side key instead of forcing a brittle UUID sync for the hackathon build.”

### Chat Flow

1. User enters text, optional budget, optional image.
2. Frontend calls `POST /api/v1/stylist/query`.
3. Backend parses either JSON or multipart input.
4. Backend gets the stylist engine:
   - full Qwen mode if runtime is available
   - heuristic fallback otherwise
5. User intent is extracted:
   - style
   - colors
   - budget
   - category
   - occasion
   - sizes
6. Catalog is filtered with `ProductDatabase.search_by_attributes(...)`.
7. Outfits are generated by:
   - Qwen generation when available, merged with fallback candidates, or
   - `OutfitCombiner` directly in fallback mode
8. Frontend renders outfits and lets the user:
   - save to Supabase
   - send selected items to try-on

### Try-On Flow

1. User picks a garment and uploads a model photo.
2. User can optionally provide height for fit/measurement support.
3. Frontend may call `/api/v1/body/measurements` first if local measurement models are available.
4. Frontend calls canonical `POST /api/v1/claid/try-on`.
5. Backend:
   - parses model/clothing input
   - can analyze garment attributes with CLIP if available
   - builds a fit-aware prompt with `ClaidTryOnPromptBuilder`
   - uploads assets to Claid
   - creates the try-on task
   - polls for completion
6. Frontend renders:
   - output image
   - fit warning
   - fit analysis metadata
7. User can save the result as a normal saved outfit in Supabase.

Important truth:

- The current wow moment is real external try-on, not a fake mock.

### Analysis / Body Measurement Flow

There are two separate paths:

1. Body analysis
   - Endpoint: `POST /api/v1/stylist/analyze-body`
   - Uses `BodyTypeAnalyzer`
   - Coarse body type recommendations
   - Currently blocked in this environment because of MediaPipe legacy API mismatch

2. Measurement extraction
   - Endpoint: `POST /api/v1/body/measurements`
   - Uses `measure_from_image.py`
   - Needs local pose + segmentation model assets
   - Returns measurement JSON and size recommendation
   - Intended to improve fit logic for try-on

The analysis page is deliberately demo-safe:

- It renders
- It explains current availability
- It does not pretend blocked ML features are working

### Profile and Outfits Flow

- These pages require a real authenticated Supabase session.
- Saved outfits:
  - read from `saved_outfits`
  - exclude `source_type = "favorite_product"`
- Favorite products:
  - read from `saved_outfits`
  - include only `source_type = "favorite_product"`
- Users can:
  - remove saved outfits
  - remove favorites
  - send favorites to try-on

### Health and Fallback Reporting

`GET /api/health` reports:

- app boot status
- backend importability
- Supabase config presence
- Claid API config presence
- measurement model readiness
- chat mode
- route callability
- blocked subsystem reasons
- favorites status
- catalog source

This is central to how the system stays demo-safe.

## Feature Status Matrix

| Feature | Page / Route | Backend / API | Core Dependencies | Status | Reason | Safe Demo Wording |
|---|---|---|---|---|---|---|
| Landing / navigation | `/` | frontend runtime only | FastAPI, Jinja, Tailwind | working | Stable page render | “This is our integrated demo shell and navigation layer.” |
| Register | `/register` | Supabase Auth client | Supabase JS, Supabase Auth | working | Real sign-up flow | “Registration is real Supabase auth.” |
| Login | `/login` | Supabase Auth client | Supabase JS, Supabase Auth | working | Real sign-in flow; confirmation depends on project settings | “Login is real Supabase auth; demo account readiness depends on Supabase confirmation settings.” |
| Profile | `/profile` | Supabase session + `saved_outfits` | Supabase Auth, Postgres RLS | working | Requires auth | “Profile shows real user-scoped data.” |
| Catalog | `/catalog` | `GET /api/v1/catalog/products` | FastAPI, ProductDatabase, sample catalog JSON | working | Stable catalog path | “Catalog is live and powers the recommendation flows.” |
| Favorites | `/catalog`, `/profile`, `/outfits` | Supabase `saved_outfits` | Supabase Auth, Postgres | working | Uses hackathon-safe `favorite_key` contract | “Favorites are real and persisted; we used a stable catalog key for the hackathon build.” |
| Saved outfits | `/profile`, `/outfits` | Supabase `saved_outfits` | Supabase Auth, Postgres | working | Real persistence | “Users can save and revisit results.” |
| Stylist chat | `/chat`, `POST /api/v1/stylist/query` | backend stylist route | ProductDatabase, Qwen optional, OutfitCombiner fallback | degraded | Full Qwen optional; fallback is active when ML extras are missing | “The stylist is live; this build may run in fast fallback mode for reliability.” |
| Full Qwen chat mode | same | same | torch, transformers, Qwen weights | blocked/optional | Not guaranteed in base environment | “Full model mode is supported by the architecture but not required for the demo.” |
| Virtual try-on | `/tryon`, `POST /api/v1/claid/try-on` | backend Claid flow | Claid API, requests, prompt builder | working | Real external service-backed route | “This is a real try-on request, not a mocked image swap.” |
| Legacy VTON adapter | frontend compatibility path | `POST /api/v1/vton/try-on` | frontend runtime adapter | working | Kept for compatibility | “We preserved a compatibility route while standardizing on the Claid path.” |
| Body analysis | `/analysis`, `POST /api/v1/stylist/analyze-body` | BodyTypeAnalyzer | mediapipe legacy solutions, opencv | blocked | Current MediaPipe package mismatch | “The flow exists, but this machine still needs the compatible MediaPipe runtime.” |
| Measurement from image | `/analysis`, `/tryon`, `POST /api/v1/body/measurements` | `measure_from_image.py` adapter | mediapipe tasks, opencv, local model assets | blocked | Missing local pose/segmentation assets | “Measurement is a real local CV path that needs local model files.” |
| Search by image | hidden from normal UX, `POST /api/v1/stylist/search-by-image` | CLIP + FAISS | torch, transformers, faiss, built index | blocked | Runtime/index prerequisites not met | “We intentionally disabled image search instead of pretending it works.” |
| Health diagnostics | `/api/health` | frontend runtime + backend capability probe | FastAPI, lazy backend import | working | Critical demo operator tool | “We built explicit readiness diagnostics so optional ML issues never crash the demo.” |

## Technical Tradeoffs

### Why this architecture?

- It preserved the existing visible frontend during the hackathon.
- It reused the real AI/backend modules instead of rewriting them.
- It avoided global boot failures by using lazy imports and capability checks.
- It gave the team one demoable product instead of two disconnected apps.

### Why not make every ML feature mandatory?

- Because hackathon reliability matters more than theoretical completeness.
- Optional imports let:
  - chat keep working in fallback mode
  - catalog and auth stay available
  - try-on remain demoable
- The result is a system that tells the truth about missing pieces instead of failing unpredictably.

### Why are favorites stored in `saved_outfits` instead of `liked_items`?

- The visible catalog items currently have demo/catalog IDs, not guaranteed UUID rows in `public.products`.
- For the hackathon, using a stable `favorite_key` in authenticated `saved_outfits` was the safest real persistence path.
- That keeps favorites real without corrupting data or inventing UUID mappings.

### Why server-rendered templates instead of a JS SPA?

- The repo already had a visible template-based frontend.
- Keeping that structure reduced rewrite risk.
- It also made the app easy to boot locally with a single Python runtime.

## Demo-Safe Explanation

### What is production-like

- Real user auth via Supabase
- Real persistence of saved outfits and favorites
- Real catalog-backed recommendation endpoint
- Real try-on backend integration with an external AI service
- Explicit health and readiness reporting

### What is hackathon-safe

- Adapter-based integration between the visible app and backend modules
- Favorites stored through a pragmatic stable key contract
- Chat fallback mode
- Local storage only for temporary “selected products for try-on” browser convenience

### What is honestly degraded or blocked

- Full local LLM mode
- Body analysis on this environment
- Local measurement models unless assets are installed
- Search-by-image until CLIP + FAISS index are ready

### What should not be overstated

- Do not claim the current build has full production-grade recommendation intelligence in all environments.
- Do not claim body analysis and measurement are active unless the machine health endpoint says they are.
- Do not claim image search is live unless the index and CLIP runtime are actually enabled.
- Do not describe the favorites model as final production schema design; it is a practical hackathon-safe persistence layer.

## Likely Jury Questions and Answers

### What is the core architecture?

The visible runtime is a FastAPI app serving Jinja templates. It mounts or adapts backend services from a second module set that contains the catalog, stylist, try-on, and optional CV/ML logic. Supabase handles auth and persistence.

### Why this stack?

Python/FastAPI let us unify the visible UI and the AI/backend services quickly. Supabase gave us real auth and persistence without building a separate auth system. We kept the frontend lightweight to minimize rewrite risk during the hackathon.

### What part is truly AI?

Three main areas:

- stylist understanding and generation through Qwen when available
- CLIP-based garment analysis and embedding/search paths
- Claid-based virtual try-on

There is also real local CV logic for measurement extraction and body analysis, though not every optional model path is enabled in the current environment.

### What part is product/integration rather than pure AI?

- catalog filtering
- outfit combination and color rules
- favorites and saved-results persistence
- auth/session handling
- diagnostics and degraded-mode handling

Those pieces are important because they make the AI usable and demo-reliable.

### How does try-on work?

The user picks a garment and uploads a model photo. The backend optionally analyzes garment attributes, builds a fit-aware Claid prompt, uploads the images to Claid, polls the result, and returns the generated try-on image plus fit metadata.

### How does chat work in this build?

The chat endpoint is real. It parses the request, filters the live catalog, and returns outfits. If the full Qwen runtime is available it can use it; otherwise it falls back to a deterministic heuristic pipeline so the demo still works.

### How do auth and favorites work?

Auth is real Supabase auth in the browser. Favorites are stored as authenticated records in `saved_outfits` using a stable `favorite_key`, which keeps the visible catalog and the saved state consistent without requiring fragile UUID mapping during the hackathon.

### What works locally versus through an external service?

Local:

- page rendering
- auth/session handling
- catalog
- favorites/saved outfits
- fallback stylist recommendations
- health diagnostics
- measurement/body-analysis code paths when the right local extras and assets are installed

External:

- try-on result generation through Claid

### What are the current technical limitations?

- Full Qwen mode is optional, not guaranteed in base setup
- Body analysis depends on a compatible MediaPipe runtime
- Measurement needs local model assets
- Search-by-image needs CLIP runtime and a built FAISS index
- Some demo auth behavior depends on Supabase project settings like email confirmation

### What would you finish next with more time?

- finalize the production catalog-to-products UUID mapping
- enable and operationalize image search with a real index build pipeline
- make body analysis compatible with the current MediaPipe tasks runtime
- bundle or automate measurement model asset setup
- add more backend persistence around recommendation runs and try-on jobs

### How did you design for demo reliability?

- one visible app entrypoint
- lazy/isolated optional ML imports
- route-scoped failures instead of global crashes
- honest frontend blocked-state UX
- structured `/api/health` diagnostics
- compatibility adapters to avoid rewriting the UI late in the hackathon

## Next Steps

Most valuable next engineering steps, based on the current repo:

1. Enable full Qwen runtime in a repeatable environment.
2. Replace or upgrade the body-analysis path to the current MediaPipe tasks API.
3. Add model asset packaging or download scripts for measurement.
4. Implement a proper CLIP embedding/index build workflow for image search.
5. Converge the catalog onto true Supabase `products` rows if moving beyond hackathon mode.
