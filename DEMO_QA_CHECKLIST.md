# Demo QA Checklist

## Pages

- [ ] Open `/`
- [ ] Open `/login`
- [ ] Open `/register`
- [ ] Open `/catalog`
- [ ] Open `/chat`
- [ ] Open `/tryon`
- [ ] Open `/analysis`
- [ ] Confirm none of these pages crash on load

## Auth

- [ ] Confirm whether `Confirm email` is enabled in the Supabase demo project before demo day
- [ ] Preferred: disable `Confirm email` in the demo project before the presentation
- [ ] If you keep it enabled, prepare one confirmed Supabase demo account before the presentation
- [ ] Sign up with Supabase-backed registration only if you are explicitly testing the confirmation flow
- [ ] Sign in with the demo account
- [ ] Open `/profile`
- [ ] Confirm logout works

## Catalog and saved outfits

- [ ] Catalog products load
- [ ] Selecting products for try-on still works
- [ ] Saving an outfit from chat works for an authenticated user
- [ ] Saved outfits render on `/profile`
- [ ] Favorites can be added from `/catalog` and appear consistently in `/profile` and `/outfits`
- [ ] Refresh `/catalog`, `/profile`, and `/outfits` and confirm favorite state persists without duplicate cards
- [ ] Sign out and confirm catalog favorite controls stay graceful and non-breaking

## AI/demo flows

- [ ] `GET /api/health` returns `200`
- [ ] Confirm `route_notes.chat_mode` is visible and accurate
- [ ] Submit a chat request and confirm outfits are returned
- [ ] Confirm chat response message mentions fallback mode when Qwen is unavailable
- [ ] Call canonical try-on route from the UI
- [ ] Confirm try-on errors are actionable if the input image or external service fails
- [ ] On analysis page, confirm body-analysis failure message is explicit if still blocked
- [ ] On analysis page, confirm measurement failure message points to missing model assets if still blocked
- [ ] Confirm no page implies image search is available

## Demo-ready health expectations

- [ ] `app.bootable = true`
- [ ] `backend.importable = true`
- [ ] `features.catalog = true`
- [ ] `features.supabase_auth = true`
- [ ] `features.saved_outfits = true`
- [ ] `features.chat_route_callable = true`
- [ ] `features.tryon_route_callable = true`
- [ ] `blockers` section is populated for any disabled feature
