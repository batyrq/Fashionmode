# Codebase Integration Audit

## 1. Executive summary

### What frontend exists

- The visible user-facing app is [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py): a FastAPI server that renders Jinja templates, not a separate React/Vue SPA.
- Pages exist for landing, chat, try-on, body analysis, catalog, outfits, login, register, and profile.
- Most frontend behavior is demo-only. Login/register/profile/favorites/saved outfits use `localStorage`; catalog/chat/outfits are mostly mock arrays embedded in template scripts.
- Only two visible frontend pages actually call backend endpoints today:
  - `analysis.html` -> `POST /api/v1/stylist/analyze-body`
  - `tryon.html` -> `POST /api/v1/vton/try-on`
- The chat page, catalog page, outfits page, and auth pages are not wired to a real backend.

### What backend exists

- The more serious backend lives in [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\main.py).
- It exposes real FastAPI endpoints for:
  - outfit recommendation
  - body analysis
  - image similarity search
  - Claid-based virtual try-on
  - catalog product listing
- Runtime data comes from local JSON catalog files plus in-memory processing. Supabase is not used by the Python backend at runtime.
- There is also a standalone script [`C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py) for body measurements and coarse size recommendation.

### What AI capabilities exist

- `QwenStylistChatbot` can parse user outfit requests and generate outfits, with mock fallback if model loading fails.
- `ClipFashionSearch` can analyze garments and search for similar products, but similarity search is effectively incomplete because no FAISS index is built anywhere in runtime startup.
- `BodyTypeAnalyzer` classifies body type from a full-body photo using MediaPipe Pose.
- `measure_from_image.py` performs richer measurement extraction plus size recommendation, but it is standalone, requires extra model asset paths, and is not exposed by any backend route.
- `ClaidTryOnPromptBuilder` builds fit-aware prompts for Claid virtual try-on and expects detailed body-measurement JSON.

### What Supabase capabilities exist

- Supabase work exists as:
  - browser auth helpers in [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\supabase.js`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\supabase.js) and [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\auth.js`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\auth.js)
  - a substantial migration in [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\supabase\migrations\20260328_0001_auth_catalog_rls.sql`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\supabase\migrations\20260328_0001_auth_catalog_rls.sql)
- The migration defines profiles, catalog tables, likes, saved outfits, uploads, try-on jobs, recommendation runs, storage buckets, and RLS.
- None of that is connected to the current frontend app or Python API handlers yet.

### Top blockers to full integration

1. The visible frontend talks to the demo app in `ai-stylist-platform`, while the real AI work lives in `outfit_generator`.
2. Frontend try-on calls `/api/v1/vton/try-on`; the real backend implements `/api/v1/claid/try-on`.
3. Frontend try-on sends `user_photo` and `clothing_photo`; real backend expects `model_file`/`clothing_file` or URLs plus required `garment_size`.
4. Frontend chat never calls the real `/api/v1/stylist/query`.
5. Frontend auth is `localStorage` only; real auth utilities are separate and unused.
6. Python backend does not read or write Supabase tables, auth session, or storage.
7. `search-by-image` is only partially implemented because CLIP similarity search has no built index at runtime.
8. The richer measurement pipeline in `measure_from_image.py` is not exposed via API and requires model assets not present in the repo.
9. Claid try-on expects detailed body measurements, but the current `analyze-body` endpoint returns body-type heuristics, not the measurement schema expected by try-on.
10. There are duplicate/demo/legacy codepaths, including commented old code and parallel frontend attempts.

## 2. Frontend inventory

### Framework and entrypoint

- Framework: FastAPI + Jinja2 templates + plain browser JavaScript.
- Entrypoint: [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py)
- Base layout: [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\base.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\base.html)
- Shared JS: [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\static\js\main.js`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\static\js\main.js)

### Routes/pages/screens

| Route | File | Purpose | Data expected | Status |
|---|---|---|---|---|
| `/` | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\index.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\index.html) | Landing/marketing page | None | Static |
| `/chat` | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\chat.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\chat.html) | Stylist chat UI | Query text, optional uploaded user clothing photo | Mocked |
| `/tryon` | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\tryon.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\tryon.html) | Virtual try-on flow | Uploaded user photo + selected products from `localStorage` | Partially connected to mock backend |
| `/analysis` | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\analysis.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\analysis.html) | Body type analysis | Uploaded full-body photo | Connected to mock endpoint |
| `/catalog` | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\catalog.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\catalog.html) | Product listing/filtering | Embedded mock product array | Mocked |
| `/outfits` | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\outfits.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\outfits.html) | Saved outfit gallery | Embedded mock outfit array | Mocked |
| `/login` | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\login.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\login.html) | Login form | Email/password | Mocked via `localStorage` |
| `/register` | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\register.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\register.html) | Signup form | Name, phone, email, password | Mocked via `localStorage` |
| `/profile` | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\profile.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\profile.html) | Account page with liked items and saved outfits | `localStorage.user` | Mocked/local-only |

### Auth-related UI

- Login:
  - File: [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\login.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\login.html)
  - Behavior: accepts any non-empty email/password, stores `user` in `localStorage`, redirects to `/profile`
  - Backend hookup: none
- Registration:
  - File: [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\register.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\register.html)
  - Behavior: stores profile-like object in `localStorage`
  - Backend hookup: none
- Logout:
  - File: [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\profile.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\profile.html)
  - Behavior: removes `localStorage.user`
  - Backend hookup: none
- Forgot/reset password:
  - Only a dead anchor in `login.html`
  - No page, no token flow, no API
- Profile/account:
  - File: [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\profile.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\profile.html)
  - Uses local saved outfits and liked items only

### User flows that clearly need backend integration

| Flow | Current frontend behavior | What it should hit later | Current status |
|---|---|---|---|
| Upload image for stylist help | `chat.html` previews local file only | likely `/api/v1/stylist/query` multipart or `/api/v1/stylist/search-by-image` | Missing |
| Generate outfit/stylist recommendation | `chat.html` uses `setTimeout` then mock outfits | `/api/v1/stylist/query` | Missing |
| Measure from image | no dedicated UI for `measure_from_image.py` | new endpoint around `measure_from_image.py` | Missing |
| Analyze body type | `analysis.html` posts photo | `/api/v1/stylist/analyze-body` | Connected to mock app; potentially compatible with real backend response shape |
| Virtual try-on | `tryon.html` posts wrong fields to wrong route for real backend | `/api/v1/claid/try-on` | Partially connected to demo-only endpoint |
| Save result | save button in `tryon.html` does nothing | Supabase storage + DB row | Missing |
| User history | no real history UI except local liked/saved placeholders | Supabase tables such as `search_history`, `recommendation_runs`, `tryon_jobs` | Missing |
| Favorites | catalog/chat like buttons mutate `localStorage.user.likedItems` | Supabase `liked_items` | Mocked |
| Wardrobe | not present | new feature | Missing |
| Saved outfits | profile/outfits pages use local arrays only | Supabase `saved_outfits` | Mocked |

### Current API usage in frontend

#### In the visible `ai-stylist-platform` frontend

| File | Call | Target | Purpose | Assessment |
|---|---|---|---|---|
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\analysis.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\analysis.html) | `fetch` | `/api/v1/stylist/analyze-body` | Upload full-body photo | Works only against whichever FastAPI app serves that route; currently demo app uses mock data |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\tryon.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\tryon.html) | `fetch` | product `image_url` | Downloads first selected product image to send as clothing blob | Fragile demo workaround |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\tryon.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\tryon.html) | `fetch` | `/api/v1/vton/try-on` | Try-on submission | Works only with demo app; incompatible with real backend contract |

#### In the separate `outfit_generator` frontend helpers

| File | Call | Target | Purpose | Assessment |
|---|---|---|---|---|
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\tryon.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\tryon.html) | `fetch` | `/api/v1/claid/try-on` | Real try-on demo page | Valid for the real backend |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\frontend\src\tryonClient.js`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\frontend\src\tryonClient.js) | `fetch` | `/api/v1/claid/try-on` | Reusable client wrapper | Valid but unused by current visible frontend |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\auth.js`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\auth.js) | Supabase client SDK | remote Supabase Auth | sign up/sign in/sign out/session | Helper only; not used by current UI |

### Frontend conclusions

- The visible frontend is a demo shell.
- The real backend has a different try-on route and request schema than the visible UI expects.
- The chat, auth, history, saved results, and favorites flows are not using real APIs or Supabase yet.

## 3. Backend inventory

### Real backend entrypoints, services, scripts, and modules

#### `ai-stylist-platform` demo server

- Entrypoint: [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py)
- Role: serves pages and mock API responses
- Status: demo-only; not production-ready

#### `outfit_generator` real backend

- Entrypoint: [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\main.py)
- Supporting modules:
  - catalog DB wrapper: [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\catalog\database.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\catalog\database.py)
  - scraper: [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\catalog\scraper.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\catalog\scraper.py)
  - Qwen stylist: [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\qwen_chatbot.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\qwen_chatbot.py)
  - CLIP search/analyzer: [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\clip_search.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\clip_search.py)
  - body analyzer: [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\body_analyzer.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\body_analyzer.py)
  - try-on prompt builder: [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\tryon_prompt.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\tryon_prompt.py)
  - outfit combiner: [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\outfit\combiner.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\outfit\combiner.py)
  - Claid API client: [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\utils\claid_client.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\utils\claid_client.py)
- Status: partially production-capable for stateless inference endpoints; not fully integrated with auth, DB persistence, storage, or frontend.

#### Standalone script

- [`C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py)
- Role: standalone CLI for front-image measurements and size recommendation
- Status: standalone only; not wired into backend or frontend

### Callable backend endpoints and interfaces

| File | Route/function | Input | Output | Assessment |
|---|---|---|---|---|
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\main.py`](C:\Users\батыр\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\main.py) | `GET /` | none | `tryon.html` or JSON ready message | Partial |
| same | `GET /try-on` | none | static try-on test page | Partial |
| same | `POST /api/v1/claid/try-on` | multipart or JSON: `clothing_url` or `clothing_file`, optional `model_url` or `model_file`, optional `body_measurements`, required `garment_size`, optional `pose/background/aspect_ratio` | `TryOnResponse` with `output_images`, `clip_analysis`, `claid_prompt`, `fit_analysis`, `fit_warning` | Most production-ready endpoint in repo; still no Supabase persistence |
| same | `POST /api/v1/stylist/query` | JSON or multipart with `query`, optional `budget`, optional `sizes`, optional `image` | `OutfitResponse` | Partial; uses local JSON catalog, optional Qwen, no user persistence |
| same | `POST /api/v1/stylist/search-by-image` | uploaded image file | `SimilarSearchResponse` | Partial-to-broken; endpoint exists but similarity search needs FAISS index build not done in runtime |
| same | `POST /api/v1/stylist/analyze-body` | uploaded image file | `BodyAnalysisResponse` | Partial; works for body-type classification only |
| same | `GET /api/v1/catalog/products` | optional `category`, `style`, `max_price`, `limit` | filtered products | Partial; reads local sample catalog only |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py) | `measure_from_front_image(...)` | image path, `height_cm`, pose model path, seg model path, optional overlay path | detailed measurements + `size_recommendation` dict | Standalone only |
| same | CLI `main()` | `--image --height_cm --pose_model --seg_model --overlay_out` | printed JSON + saved overlay | Standalone only |

### Data flow in the real backend

#### Stylist query

1. request parsed in `main.py`
2. `QwenStylistChatbot.analyze_query(...)`
3. `ProductDatabase.search_by_attributes(...)` against local `sample_catalog.json`
4. `QwenStylistChatbot.generate_outfit_recommendations(...)`
5. fallback to `OutfitCombiner.create_outfits(...)`

#### Search by image

1. uploaded image opened with PIL
2. `ClipFashionSearch.search_similar(...)`
3. lookup matching products from local catalog DB
4. optional complementary item selection

Important issue:
- `ClipFashionSearch.faiss_index` is never built in startup or endpoint code.
- Result: endpoint likely returns no results even though the route exists.

#### Analyze body

1. uploaded image opened with PIL
2. `BodyTypeAnalyzer.analyze_full(...)`
3. MediaPipe Pose keypoints
4. heuristic body-type classification and recommendations

#### Claid try-on

1. request parsing supports URLs or file upload
2. clothing image analyzed by CLIP
3. `ClaidTryOnPromptBuilder.build_prompt(...)`
4. Claid upload proxy through `ClaidClient`
5. task polling
6. response returns output URL plus prompt/fit diagnostics

### What is actually used for auth, database, storage, AI inference, image processing

- Supabase:
  - Used only in browser helper JS and SQL migration files.
  - Not used in Python request handlers.
- Auth:
  - Visible frontend: `localStorage`.
  - Separate helper path: Supabase client-side auth JS.
  - Python backend: no auth enforcement.
- Database:
  - Runtime backend uses local JSON catalog through `ProductDatabase`.
  - Supabase schema exists but unused at runtime.
- Storage/image upload:
  - Runtime try-on uploads images to Claid temporary storage, not Supabase storage.
  - Frontend uploads never persist to Supabase buckets.
- AI inference:
  - Qwen via Hugging Face Transformers
  - CLIP via Transformers
  - MediaPipe Pose in `body_analyzer.py`
  - MediaPipe Tasks + segmentation in standalone `measure_from_image.py`
  - Claid external API for try-on
- Image processing:
  - PIL throughout backend
  - OpenCV + MediaPipe in body measurement script

### Environment variables and config dependencies

#### `ai-stylist-platform`

- File: [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\.env`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\.env)
- Detected variable names:
  - `HF_TOKEN`
- Actual runtime use:
  - not used by current active demo code

#### `outfit_generator`

- File: [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\.env`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\.env)
- Detected variable names:
  - `CLAID_API_KEY`
- Runtime dependency:
  - required by `POST /api/v1/claid/try-on`

#### Code-level config

- [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\config.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\config.py)
  - local paths
  - model names
  - catalog categories
  - body/style/color rules
- [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\supabase.js`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\supabase.js)
  - contains hard-coded default Supabase URL and publishable anon key override path

### Backend pieces missing for end-to-end frontend operation

- No runtime auth/session bridge between frontend and backend
- No Supabase DB reads/writes in Python API
- No upload persistence to Supabase buckets
- No save/favorites/history endpoints
- No API exposing `measure_from_image.py`
- No body-measurement endpoint that returns the schema Claid fit logic expects
- No built CLIP index startup or embedding persistence
- No catalog CRUD/admin ingestion path against Supabase tables

## 4. AI inventory

### AI-related entrypoints

| File | Main callable entrypoint | Inputs | Outputs | Callable from backend today | Status |
|---|---|---|---|---|---|
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\qwen_chatbot.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\qwen_chatbot.py) | `QwenStylistChatbot.analyze_query` | user query, optional image, budget, sizes | normalized style intent | Yes, via `/api/v1/stylist/query` | Partial |
| same | `QwenStylistChatbot.generate_outfit_recommendations` | style intent, product list | outfit list | Yes, via `/api/v1/stylist/query` | Partial |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\clip_search.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\clip_search.py) | `ClipFashionSearch.analyze_garment` | garment image | category/colors/pattern/material/fit analysis | Yes, via `/api/v1/claid/try-on` | Usable |
| same | `ClipFashionSearch.search_similar` | image or text + FAISS index | ranked similar product ids | Yes, via `/api/v1/stylist/search-by-image` | Partial/broken without index |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\body_analyzer.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\body_analyzer.py) | `BodyTypeAnalyzer.analyze_full` | full-body image | body type + recommendations + approximate measurements | Yes, via `/api/v1/stylist/analyze-body` | Partial |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\tryon_prompt.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\tryon_prompt.py) | `ClaidTryOnPromptBuilder.build_prompt` | garment analysis, model context, fit context | try-on prompt + fit analysis + fit scale | Yes, via `/api/v1/claid/try-on` | Usable |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\outfit\combiner.py`](C:\Users\батыр\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\outfit\combiner.py) | `OutfitCombiner.create_outfits` | candidate products, style, budget | deterministic outfit list | Yes, fallback in `/api/v1/stylist/query` | Usable |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py) | `measure_from_front_image` | image path, height, pose model path, seg model path | detailed body measurements + size recommendation | No | Standalone only |

### Gaps to production usage

#### Qwen stylist

- Good:
  - wrapped in reusable class
  - has mock fallback when model unavailable
- Gaps:
  - no startup warmup, caching, or model service boundary
  - relies on local sample catalog
  - no persistence of recommendations

#### CLIP garment analysis and similarity

- Good:
  - garment attribute analysis is usable immediately for try-on prompt construction
- Gaps:
  - similarity search needs FAISS index build; current runtime never calls `build_index`
  - no persisted embeddings in Supabase despite migration defining `product_embeddings`

#### Body analysis

- `BodyTypeAnalyzer` output is useful for styling tips, but not sufficient for fit-aware try-on sizing.
- `measure_from_image.py` is the richer fit pipeline, but:
  - not exposed by API
  - requires `height_cm`
  - requires pose/segmentation model asset files not found in repo
  - depends on CLI/local filesystem rather than uploaded image bytes

#### Claid try-on

- This is the most complete AI path in the repo.
- Gaps:
  - no persistence to `tryon_jobs` or storage buckets
  - no authenticated user ownership
  - no reuse by current visible frontend

### Duplicated / obsolete / experimental AI wrappers

- Duplicate body-analysis paths:
  - [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\body_analyzer.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\body_analyzer.py)
  - [`C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py)
- Duplicate app layers:
  - demo app in `ai-stylist-platform`
  - real API in `outfit_generator`
- Commented legacy implementation still present in:
  - [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py)
  - [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\config.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\config.py)

## 5. Supabase inventory

### Where Supabase appears

- Browser helper client:
  - [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\supabase.js`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\supabase.js)
  - [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\auth.js`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\auth.js)
- Setup docs:
  - [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\supabase\README.md`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\supabase\README.md)
- Migration:
  - [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\supabase\migrations\20260328_0001_auth_catalog_rls.sql`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\supabase\migrations\20260328_0001_auth_catalog_rls.sql)

### Auth flow

- Intended auth flow:
  - Supabase email/password auth
  - `auth.users` mirrored into `public.profiles` by trigger
- Actual visible frontend flow:
  - `localStorage` only
- Actual backend flow:
  - no auth/session use

### Tables/schema references visible in code

- `profiles`
- `user_preferences`
- `user_sizes`
- `products`
- `product_variants`
- `product_images`
- `product_attributes`
- `product_embeddings`
- `saved_outfits`
- `liked_items`
- `search_history`
- `uploaded_photos`
- `tryon_jobs`
- `recommendation_runs`

### Storage buckets

- `catalog-images`
- `user-uploads`
- `tryon-results`

### Row-level security assumptions

- Catalog tables are public-read.
- User-owned tables are auth-owned.
- Admin writes are gated through `profiles.role = 'admin'`.
- Storage policies assume owner-based access for user uploads and try-on results.

### Session handling

- Browser helper JS enables:
  - `persistSession`
  - `autoRefreshToken`
  - `detectSessionInUrl`
- No current page in the visible frontend imports or uses those helpers.

### Alignment between frontend auth and backend

- Not aligned.
- Visible frontend:
  - does not use Supabase auth
  - does not carry access tokens
  - does not load user from Supabase
- Backend:
  - has no Supabase session verification
  - has no protected routes

### Missing pieces / misuse

- Login/register UI exists but is not wired to Supabase helpers.
- DB tables are defined but unused by Python handlers.
- Storage flow is defined in SQL but unused in frontend/backend runtime.
- Client/server split is incomplete:
  - client-side Supabase auth helpers exist
  - server-side Supabase access layer does not exist
- Hard-coded publishable Supabase config in `static/js/supabase.js` is a brittle integration path.
- Migration `tryon_jobs.provider` defaults to `replicate`, but actual backend provider is Claid. This schema/runtime mismatch should be fixed before production wiring.

## 6. Frontend ↔ Backend ↔ AI mapping table

| Frontend page/action | Frontend file(s) | Expected backend/API | Actual backend file/function found | Actual AI file/function found | Supabase dependency | Status | Notes |
|---|---|---|---|---|---|---|---|
| Landing page CTA -> start stylist | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\index.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\index.html) | none or navigate to chat | page route only | none | none | Connected | pure navigation |
| Chat submit for outfit recommendation | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\chat.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\chat.html) | `POST /api/v1/stylist/query` | [`main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\main.py) `stylist_query` | [`qwen_chatbot.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\qwen_chatbot.py), [`combiner.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\outfit\combiner.py) | maybe `search_history`, `recommendation_runs`, `saved_outfits` later | Missing | current chat never calls API |
| Upload image in chat | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\chat.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\chat.html) | multipart `stylist/query` or `search-by-image` | same `stylist_query` or `search_by_image` | Qwen image-conditioned analysis or CLIP similarity | `uploaded_photos` later | Missing | file is preview-only today |
| Body analysis upload | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\analysis.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\analysis.html) | `POST /api/v1/stylist/analyze-body` | [`main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\main.py) `analyze_body` | [`body_analyzer.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\body_analyzer.py) | maybe `uploaded_photos`, `user_sizes` later | Partially connected | current visible app uses demo endpoint; real response shape is close enough for this page |
| Measurement from image | no page yet | new measurement endpoint | none | [`measure_from_image.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\measure_from_image.py) | likely `user_sizes`, `uploaded_photos` | Missing | standalone script only |
| Catalog browse/filter | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\catalog.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\catalog.html) | `GET /api/v1/catalog/products` | [`main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\main.py) `get_products` | none | `products`, `product_images`, variants later | Missing | page uses embedded mock array |
| Select product for try-on | [`catalog.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\catalog.html), [`tryon.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\tryon.html) | product lookup or stored selections | none | none | maybe `saved_outfits` or client state only | Mocked | uses `localStorage.selectedProducts` |
| Virtual try-on submit | [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\tryon.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\tryon.html) | `POST /api/v1/claid/try-on` with `garment_size` and compatible field names | real backend route exists in [`main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\main.py) as `claid_try_on`; demo app has `/api/v1/vton/try-on` | [`clip_search.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\clip_search.py), [`tryon_prompt.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\models\tryon_prompt.py), Claid external API | `uploaded_photos`, `tryon_jobs`, `tryon-results` | Partially connected | visible frontend is wired to the wrong route and wrong request contract |
| Save try-on result | save button in [`tryon.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\tryon.html) | storage upload + DB row | none | none | `tryon-results`, `tryon_jobs`, `saved_outfits` | Missing | button has no implementation |
| Favorites / likes | [`catalog.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\catalog.html), [`chat.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\chat.html), [`profile.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\profile.html) | likes CRUD | none | none | `liked_items` | Mocked | localStorage only |
| Saved outfits page | [`outfits.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\outfits.html), [`profile.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\profile.html) | saved outfits CRUD | none | may consume stylist output | `saved_outfits` | Mocked | local arrays only |
| Login/register/logout/profile | [`login.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\login.html), [`register.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\register.html), [`profile.html`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\templates\profile.html) | Supabase auth JS or server auth API | Supabase helper files exist but are unused | none | `auth.users`, `profiles` | Missing | visible auth path is completely disconnected from Supabase |

## 7. Missing integrations

- Wire the visible frontend to the real backend instead of the demo app.
- Replace chat mock logic with real calls to `/api/v1/stylist/query`.
- Decide whether chat image upload goes to `stylist/query` multipart or `search-by-image`, then implement it.
- Replace catalog embedded mock products with `/api/v1/catalog/products`.
- Rework visible try-on page to use `/api/v1/claid/try-on`.
- Add required `garment_size` selection to visible try-on UI.
- Align request field names:
  - current UI sends `user_photo` and `clothing_photo`
  - real backend expects `model_file` and `clothing_file`
- Expose `measure_from_image.py` through a backend endpoint if fit-aware sizing is required.
- Align body-analysis output with try-on fit input:
  - current `analyze-body` returns body type recommendations
  - Claid prompt builder expects detailed measurements and size recommendation
- Add Supabase auth wiring to login/register/logout/profile flows.
- Add server-side or client-side flows for `liked_items`, `saved_outfits`, `search_history`, `uploaded_photos`, `tryon_jobs`, and `recommendation_runs`.
- Add Supabase storage uploads for user photos and try-on results if persistence is needed.
- Build or persist CLIP FAISS index so `/api/v1/stylist/search-by-image` can return real results.
- Replace local JSON catalog dependency with Supabase tables or formal ingestion path.
- Resolve schema/runtime mismatch in `tryon_jobs.provider` default (`replicate` vs actual `Claid` usage).

## 8. Cleanup candidates

| File/folder | Why likely unused or disconnected | Confidence |
|---|---|---|
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\main.py) commented legacy block | large commented-out older implementation duplicates real backend concerns | High |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\config.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\config.py) commented legacy block | old ML-oriented config retained inside demo app | High |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\frontend\README.md`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\frontend\README.md) + `frontend/src/tryonClient.js` | frontend handoff layer exists but is not used by visible app | High |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\frontend\contracts`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\frontend\contracts) | contract docs only, no consumer in repo | High |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\frontend\samples`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\frontend\samples) | sample payloads only | High |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\auth.js`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\auth.js) | Supabase auth helper is not imported by any current page | High |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\supabase.js`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\static\js\supabase.js) | same as above; helper exists without active UI integration | High |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\utils\image_processor.py`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\utils\image_processor.py) | empty file | High |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\__pycache__`](C:\Users\batyr\Документы\coding\hackathons\terricon\ai-stylist-platform\ai-stylist-platform\__pycache__) | generated artifacts | High |
| [`C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\__pycache__`](C:\Users\batyr\Документы\coding\hackathons\terricon\outfit_generator\outfit_generator\__pycache__) and subfolder `__pycache__` dirs | generated artifacts | High |
| duplicate app split: `ai-stylist-platform` vs `outfit_generator` | not a deletion candidate by itself yet, but a major consolidation target | Medium |
| `CLAID_SAMPLE_MODEL_URL` and `CLAID_SAMPLE_CLOTHING_URLS` constants in real backend `main.py` | defined but not used by endpoint code or static page | Medium |

## 9. Recommended next integration order

### Phase 1: auth

- Choose one auth path and standardize on it: Supabase auth is already the only non-demo path present.
- Replace `localStorage` login/register/profile flows with `static/js/auth.js` or equivalent integrated UI.
- Mirror the visible frontend profile page to `profiles`, not `localStorage`.
- Ensure logout clears Supabase session, not just local data.

### Phase 2: core API wiring

- Point visible chat page to `/api/v1/stylist/query`.
- Point visible catalog page to `/api/v1/catalog/products`.
- Remove embedded mock arrays from visible pages once API wiring is stable.
- Decide whether the visible frontend should be served by `outfit_generator` or whether its templates should be moved there.

### Phase 3: AI inference connection

- Rework visible try-on page to call `/api/v1/claid/try-on` with correct field names and a required garment size selector.
- Add a real frontend flow for body measurements if Claid fit-awareness is required.
- Expose `measure_from_image.py` behind an API if size-aware try-on is part of the product.
- Build or preload CLIP product index before using `search-by-image`.

### Phase 4: storage/history/save flows

- Persist uploads to Supabase buckets.
- Persist try-on jobs/results to `tryon_jobs`.
- Persist saved outfits to `saved_outfits`.
- Persist likes to `liked_items`.
- Persist search/recommendation runs to `search_history` and `recommendation_runs`.

### Phase 5: cleanup

- Remove or archive demo-only duplicate codepaths after real routing is stable.
- Delete empty/disconnected utilities and generated caches.
- Consolidate one canonical app entrypoint and one canonical frontend path.
