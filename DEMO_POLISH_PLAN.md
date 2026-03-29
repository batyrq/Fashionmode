# Demo Polish Plan

## User-facing issues to polish

- Show a clear fallback-mode badge on chat.
- Replace raw backend-style error strings with friendlier page messages.
- Make favorites look intentionally disabled instead of clickable-but-broken.
- Make analysis and measurement states clearly say "not available in this build" or "local assets required".
- Add a compact local status widget so operators can confirm readiness without opening raw JSON.
- Tighten quickstart and presenter docs.

## Hide vs disable vs label

- Favorites: visible but disabled and labeled as unavailable in this build.
- Search-by-image: not exposed as an active UI feature; documented as unavailable.
- Body analysis: visible on analysis page, but labeled as unavailable in this build when health says so.
- Measurement: visible on analysis/try-on pages, but labeled as requiring local assets when health says so.
- Full chat mode: visible as a small "quick mode" / fallback badge rather than hidden.

## Acceptance criteria for presentable demo UX

- A new user can tell what works from the page itself.
- Blocked features do not look like broken buttons.
- Working flows have reassuring, short success or loading messages.
- Operator can confirm readiness from the UI plus `/api/health`.
- README, demo script, and operator checklist are enough for a teammate to run and present the app quickly.
