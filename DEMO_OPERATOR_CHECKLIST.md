# Demo Operator Checklist

## Before starting

- Verify env vars:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY` or `SUPABASE_PUBLISHABLE_KEY`
  - `CLAID_API_KEY`
- Optional extras to verify only if you plan to use them:
  - `POSE_MODEL_PATH` / `MEDIAPIPE_POSE_MODEL_PATH`
  - `SEG_MODEL_PATH` / `MEDIAPIPE_SEG_MODEL_PATH`

## Start command

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\bootstrap_local.ps1"
uvicorn main:app --reload --app-dir "ai-stylist-platform\ai-stylist-platform"
```

## Health check

Open:

```powershell
curl http://127.0.0.1:8000/api/health
```

Confirm:

- `features.chat_route_callable = true`
- `features.tryon_route_callable = true`
- `route_notes.chat_mode = heuristic_fallback` or `full`
- `features.favorites_enabled = false`
- `blockers` only list the expected demo limitations

## Tabs to open before presenting

- `/`
- `/catalog`
- `/chat`
- `/tryon`
- `/profile`
- optional backup tab: `/api/health`

## Sample assets to have ready

- One presenter/model photo for try-on
- One backup presenter/model photo
- One backup screenshot or saved result in case network or Claid is slow

## Safe live-demo path

1. Show homepage
2. Pick an item in catalog
3. Run a chat query
4. Save an outfit
5. Run try-on
6. Show saved result in profile

## Quick recovery steps

- If chat returns no outfits:
  - remove tight budget constraints
  - use `Need a casual outfit under 50000`
- If try-on is slow:
  - reload `/tryon`
  - retry with the backup model photo
- If Supabase auth feels inconsistent:
  - sign out
  - refresh once
  - sign back in
- If someone asks about blocked features:
  - open `/api/health`
  - point to the explicit blocker fields

## Things not to promise live

- favorites in this build
- image search in this build
- body analysis in this build
- measurement inference unless the local assets are confirmed installed
