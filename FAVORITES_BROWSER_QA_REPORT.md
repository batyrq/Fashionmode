# Favorites Browser QA Report

Date: 2026-03-29

## Scenarios tested

- Bootstrap and local app startup
- `GET /api/health` through a live `uvicorn` process
- Page render regression for:
  - `/`
  - `/login`
  - `/register`
  - `/profile`
  - `/chat`
  - `/tryon`
  - `/analysis`
  - `/catalog`
  - `/outfits`
- Catalog contract validation for:
  - `favorite_key`
  - `catalog_display_id`
  - `favorite_product_uuid`
- Favorites code-path review for:
  - auth restoration
  - duplicate reads
  - repeated toggle clicks
  - unauthenticated UX
  - profile/outfits consistency
- Supabase auth reality check with a fresh sign-up attempt

## Failures found

1. Duplicate favorite cards could still appear if multiple `favorite_product` rows existed for the same `favorite_key`.
2. Removing a favorite deleted only one matching row, so duplicate rows could survive and reappear after refresh.
3. Catalog favorite buttons did not guard strongly enough against rapid repeated clicks.
4. Catalog favorite state did not explicitly refresh when Supabase auth state changed after initial page load.
5. Real browser login/favorite persistence could not be completed in this environment because the Supabase project requires confirmed email and no confirmed demo account was provided.

## Fixes applied

- Added dedupe-on-read in `static/js/favorites.js`, keyed by `favorite_key`.
- Changed favorite removal to delete all matching `favorite_product` rows for the same `favorite_key`.
- Added a session-first fallback in `static/js/app-auth.js` so user restoration is less sensitive to `getUser()` timing.
- Hardened `catalog.html` with:
  - per-item pending guards for favorite toggles
  - disabled favorite buttons while requests are in flight
  - disabled unauthenticated favorite buttons
  - inline banner feedback instead of relying only on alerts
  - auth-state-change refresh of favorite state

## Validation evidence

- `powershell -ExecutionPolicy Bypass -File ".\scripts\bootstrap_local.ps1"` completed successfully.
- Live health check via `uvicorn` returned `features.favorites_enabled = true`.
- Import-based smoke check returned `200` for all main pages.
- Supabase sign-up test succeeded, confirming public auth wiring is reachable.
- Supabase password sign-in for that fresh user returned `email_not_confirmed`, which blocked a real logged-in browser QA pass in this thread.

## Remaining risks

- A full browser add/remove/refresh cycle still needs one confirmed Supabase test account.
- Because there is no DB uniqueness constraint on `favorite_key`, true cross-tab race conditions are still mitigated in the client, not enforced in the database.
- This flow still relies on `saved_outfits` behavior in the live Supabase project matching the current demo environment.
