# Judge Q&A Cheatsheet

## Fast Answers

### 1. What is the core architecture?

One visible FastAPI web app serves the UI, and it adapts into a second backend module set that contains catalog, AI, and try-on logic. Supabase handles auth and persistence.

### 2. What is actually AI here?

- Qwen-based stylist understanding and recommendation generation when full ML runtime is available
- CLIP-based garment/image understanding and optional similarity search
- Claid-based virtual try-on generation
- Local CV-based measurement extraction and body analysis paths

### 3. What works today in the demo build?

- real login/register with Supabase
- catalog browsing
- favorites
- saved outfits
- stylist recommendations
- real try-on through Claid
- health diagnostics

### 4. What is degraded but still usable?

The stylist chat can run in a fast heuristic fallback mode when the full Qwen runtime is not installed locally.

### 5. What is blocked right now?

- full Qwen local mode
- body analysis on this machine
- local measurement inference unless model assets are installed
- search-by-image unless CLIP + FAISS index are present

### 6. How does try-on work?

The app takes a user photo and a selected garment, builds a fit-aware prompt, uploads the assets to Claid, and returns the generated try-on result plus fit metadata.

### 7. Is the try-on fake?

No. It is a real external-service-backed try-on request through the Claid API.

### 8. How do auth and favorites work?

Auth is real Supabase auth in the browser. Favorites persist as authenticated records using a stable `favorite_key` hackathon contract, and saved outfits persist in Supabase as well.

### 9. Why this stack?

Python/FastAPI let us unify the visible UI and the AI/backend services quickly. Supabase gave us real auth and persistence. We kept the frontend lightweight to reduce rewrite risk.

### 10. What should we not overclaim?

- Don't say all ML modules are fully live on every machine.
- Don't claim image search is enabled unless `/api/health` says so.
- Don't present body analysis or measurement as active unless the current machine is configured for them.
- Don't describe the current favorites persistence as the final production schema.

## Strong Positioning Lines

- "We focused on a reliable integrated product, not isolated model demos."
- "The architecture supports richer local ML, but we intentionally degrade gracefully when optional runtimes are missing."
- "The try-on path is real, the auth is real, and saved user actions are real."
- "We treated hackathon reliability as a product requirement."

## Do Not Overclaim

- Do not imply search-by-image is live by default.
- Do not imply body analysis is currently enabled on every machine.
- Do not present the system as production-ready end to end.
- Do not describe the current favorites contract as the long-term marketplace schema.
