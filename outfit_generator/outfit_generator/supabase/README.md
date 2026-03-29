# Supabase setup

This folder contains the database migration for the AI Stylist / Virtual Try-On hackathon app.

## What it creates

- Supabase Auth profile mirroring in `public.profiles`
- Catalog tables for products, variants, images, attributes, and embeddings
- User-owned tables for preferences, sizes, likes, saved outfits, uploads, try-on jobs, and recommendation runs
- RLS policies for public catalog browsing and per-user private access
- Storage buckets for catalog assets and user-generated files

## How to apply

1. Open Supabase.
2. Create a new migration from `supabase/migrations/20260328_0001_auth_catalog_rls.sql`.
3. Run it in the SQL editor or through the Supabase CLI.
4. Make sure email/password auth is enabled in Supabase Auth.

## Notes

- `profiles.id` is the same UUID as `auth.users.id`.
- The signup trigger auto-creates one `profiles` row per auth user.
- Catalog tables are readable by anonymous visitors, while user tables require authentication.
- Admin catalog writes are gated by `profiles.role = 'admin'`.
