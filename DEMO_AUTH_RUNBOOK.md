# Demo Auth Runbook

## Required account state

- Use a real Supabase account.
- Preferred demo mode: the Supabase demo project has `Confirm email` turned off, so a fresh account can sign in immediately.
- If `Confirm email` is still enabled, use a real confirmed account with working email/password login.

## Exact demo login flow

1. Start the app:
   - `powershell -ExecutionPolicy Bypass -File ".\scripts\bootstrap_local.ps1"`
   - `uvicorn main:app --reload --app-dir "ai-stylist-platform\ai-stylist-platform"`
2. Check readiness:
   - `curl http://127.0.0.1:8012/api/health`
3. Open `/login`.
4. Sign in with the demo account.
5. Open `/profile`.
6. Open `/catalog` and demo favorites from that authenticated session.

## What to do if sign-up says confirmation is required

- First check whether `Confirm email` is still enabled in the Supabase demo project.
- If it is enabled:
  - disable it in the demo project before the presentation, or
  - switch to a pre-confirmed demo account.
- Do not rely on a brand-new unconfirmed account during the live demo.

## What not to do during demo

- Do not create a brand-new account on stage unless you have already verified `Confirm email` is disabled in the demo project.
- Do not spend live-demo time debugging `email_not_confirmed`.
- Do not sign out before the favorites/profile segment unless you intentionally want to show the unauthenticated UX.

## Fallback demo order if auth fails

1. `/`
2. `/catalog`
3. `/chat`
4. `/tryon`
5. `/api/health`

If auth is unavailable, skip favorites/profile and present them as Supabase-backed features that require the demo project auth setting to be finished.
