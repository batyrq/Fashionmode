# Favorites Fix Report

## Root cause

The visible catalog used display/demo identifiers, but the original Supabase favorites path expected `liked_items.product_id` to reference `public.products.id` UUIDs. In the active Supabase project, `public.products` is empty, so there was no safe UUID-backed row to favorite.

## Chosen fix

The app now uses an additive adapter contract instead of forcing `liked_items`:

- `GET /api/v1/catalog/products` keeps existing display IDs and also returns:
  - `catalog_display_id`
  - `favorite_key`
  - `favorite_product_uuid` when available
- The frontend favorite toggle uses `favorite_key` as the canonical identity.
- Favorites are persisted in `public.saved_outfits` with:
  - `source_type = "favorite_product"`
  - `outfit_payload.favorite_key`
  - `outfit_payload.product_snapshot`
- Normal saved outfits continue to use the same table, but the visible app filters them away from favorites via `source_type`.

## Files changed

- `ai-stylist-platform\ai-stylist-platform\main.py`
- `ai-stylist-platform\ai-stylist-platform\static\js\favorites.js`
- `ai-stylist-platform\ai-stylist-platform\static\js\saved-outfits.js`
- `ai-stylist-platform\ai-stylist-platform\static\js\demo-ui.js`
- `ai-stylist-platform\ai-stylist-platform\templates\catalog.html`
- `ai-stylist-platform\ai-stylist-platform\templates\profile.html`
- `ai-stylist-platform\ai-stylist-platform\templates\outfits.html`
- `FAVORITES_MAPPING_REPORT.md`
- `README.md`
- `INTEGRATION_CHANGELOG.md`

## API/data contract before vs after

### Before

- Catalog responses exposed only display/demo IDs used by the UI.
- Visible favorites were blocked because those IDs did not safely map to `liked_items.product_id uuid`.
- `/api/health` reported favorites as disabled.

### After

- Catalog responses still expose existing IDs for rendering and add:
  - `catalog_display_id`
  - `favorite_key`
  - `favorite_product_uuid`
- Favorites use `favorite_key` across catalog, profile, and outfits.
- Supabase persistence uses `saved_outfits` rows tagged with `source_type = "favorite_product"`.
- `/api/health` reports favorites as enabled when Supabase config is present.

## Remaining caveats

- This fix does not populate or use `public.liked_items`.
- If the same favorite is clicked from multiple tabs at the same time, duplicate rows are still theoretically possible because `saved_outfits` has no uniqueness constraint on `favorite_key`.
- If the team later syncs the visible catalog into `public.products`, the UI can keep using `favorite_key` while the persistence layer is migrated behind it.
