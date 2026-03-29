# Favorites Mapping Report

## Current schema involved

- Frontend visible catalog IDs come from the backend/sample catalog payload.
- Supabase legacy favorites table: `public.liked_items`
- `public.liked_items.product_id` type: `uuid`
- Supabase source of truth for UUID-backed products: `public.products.id`
- Active live persistence path for visible favorites: `public.saved_outfits`
- Migration reference: `outfit_generator\outfit_generator\supabase\migrations\20260328_0001_auth_catalog_rls.sql`

## Mapping status

- Mapping achieved: yes, via an adapter contract
- Favorites are enabled in the visible UI and persisted in Supabase

## Root cause

The visible catalog items still use demo/backend string identifiers, while the original favorites path expected `liked_items.product_id` to point at `public.products.id` UUIDs. In this local Supabase project, `public.products` is currently empty, so there is no safe UUID target for the visible catalog.

## Chosen mapping contract

Instead of fabricating UUIDs or writing broken `liked_items` rows, the app now uses an additive contract:

- Catalog API still returns existing display identifiers.
- Catalog API also returns `favorite_key`, a canonical stable favorite-safe identifier.
- Favorites persist in `public.saved_outfits` with:
  - `source_type = "favorite_product"`
  - `outfit_payload.favorite_key`
  - `outfit_payload.product_snapshot`

## Why this was the safest live fix

- It preserves the current architecture and UI.
- It uses an existing authenticated Supabase table with working RLS.
- It avoids inventing product UUIDs.
- It keeps the contract additive and reversible if `public.products` is populated later.

## Current cross-page identity

- Visible catalog identity for rendering: existing `id`
- Canonical favorite identity for persistence and toggling: `favorite_key`
- Future UUID bridge, if available later: `favorite_product_uuid`

## Remaining caveat

`public.liked_items` is still not used by the visible app. If the team later loads real UUID-backed rows into `public.products`, favorites can be migrated to `liked_items` or dual-written behind the same `favorite_key` contract.
