# Demo No Email Confirmation Setup

## Exact cause

The blocker is caused by the current Supabase project settings, not by the frontend code.

In this repo:

- registration uses real `supabase.auth.signUp(...)`
- login uses real `supabase.auth.signInWithPassword(...)`
- there is no fake auth fallback
- there is no repo-local Supabase auth config that disables email confirmation

During validation, fresh sign-up succeeded but immediate password login failed with `email_not_confirmed`. That is the expected Supabase behavior when email confirmation is enabled.

Official reference:

- [Supabase auth signup docs](https://supabase.com/docs/client/auth-signup)

## Exact fix

This is not currently repo-configurable here. It requires a safe dashboard change in the Supabase demo project.

Suggested demo-only change:

1. Open the Supabase dashboard for the demo project.
2. Go to `Authentication`.
3. Open `Settings`.
4. Find the email confirmation setting, usually labeled `Confirm email` or `Enable email confirmations`.
5. Turn it off for the demo project.
6. Save the change.

Expected result:

- fresh sign-up should create a real session immediately
- immediate password login should work without mailbox confirmation
- the app keeps using the same real Supabase auth architecture

## Is it repo-configurable?

- Repo-configurable: no
- Requires Supabase dashboard action: yes

I did not find:

- `supabase/config.toml`
- local Supabase CLI config
- repo-local auth flags for email confirmation
- any supported demo-only auth bypass in code

## Exact local/demo steps

1. Disable `Confirm email` in the Supabase demo project.
2. Start the app:
   - `powershell -ExecutionPolicy Bypass -File ".\scripts\bootstrap_local.ps1"`
   - `uvicorn main:app --reload --app-dir "ai-stylist-platform\ai-stylist-platform" --port 8012`
3. Check readiness:
   - `curl http://127.0.0.1:8012/api/health`
4. Open `/register`.
5. Create a fresh demo user.
6. Verify that registration returns an immediately usable session or that `/login` works right away for the new account.
7. Open `/profile` and `/catalog` to confirm the authenticated session is active.

## Rollback steps

After the demo:

1. Return to the Supabase dashboard.
2. Go back to `Authentication -> Settings`.
3. Re-enable `Confirm email`.
4. Save the change.

## Risks and caveats

- Apply this only to the demo/local Supabase project, not blindly to a production-facing project.
- Disabling Confirm email changes sign-up behavior for all new users in that demo project.
- If the dashboard change is not applied, the team should continue using a pre-confirmed demo account instead of attempting live sign-up.
