# Admin Catalog Setup

## Chosen role model

- Role source: `public.profiles.role`
- Why this model: the existing Supabase schema already includes `profiles.role` with allowed values `user`, `admin`, and `moderator`
- Why this was the safest option: no new auth system, no hardcoded admin emails, and no browser-only trust

## Runtime enforcement

- Visible runtime: `ai-stylist-platform\ai-stylist-platform\main.py`
- Server-side admin check:
  - verifies the Supabase bearer token with `GET /auth/v1/user`
  - reads the authenticated user's `public.profiles` row
  - only allows catalog writes when `role = 'admin'`
- Admin-only endpoints:
  - `GET /api/v1/admin/catalog/me`
  - `POST /api/v1/admin/catalog/products`
  - `DELETE /api/v1/admin/catalog/products/{product_id}`

## What the admin flow currently manages

- Backing catalog for the live demo app: `outfit_generator\outfit_generator\catalog\sample_catalog.json`
- Supported admin actions in this pass:
  - add a catalog item
  - delete a catalog item

This is intentionally scoped to the catalog source that the visible app is already using today. It does not migrate the app to `public.products`.

## Supabase setup steps

### 1. Confirm the schema is applied

Apply the existing migration if your Supabase project does not already have it:

- File: `outfit_generator\outfit_generator\supabase\migrations\20260328_0001_auth_catalog_rls.sql`

The relevant part for admin roles is:

- `public.profiles.role text not null default 'user' check (role in ('user', 'admin', 'moderator'))`

### 2. Promote a user to admin

Use the Supabase SQL editor or table editor.

SQL by email:

```sql
update public.profiles
set role = 'admin'
where email = 'demo-admin@example.com';
```

SQL by user id:

```sql
update public.profiles
set role = 'admin'
where id = '00000000-0000-0000-0000-000000000000';
```

### 3. Verify from the app

After the user signs in, call:

```powershell
curl -H "Authorization: Bearer <access-token>" http://127.0.0.1:8012/api/v1/admin/catalog/me
```

Expected shape:

```json
{
  "authenticated": true,
  "is_admin": true,
  "role": "admin",
  "email": "..."
}
```

## Minimal payload to add a catalog item

Admin creation now works through local image upload only.

- required transport: `multipart/form-data`
- required file field: `image_file`
- remote `image_url` is no longer accepted as the active create path

Example:

```powershell
curl -X POST http://127.0.0.1:8012/api/v1/admin/catalog/products `
  -H "Authorization: Bearer <access-token>" `
  -F "name=Demo blazer" `
  -F "category=blazers" `
  -F "outfit_category=outerwear" `
  -F "price=25900" `
  -F "currency=KZT" `
  -F "image_file=@C:\path\to\demo-blazer.jpg" `
  -F "url=https://example.com/blazer" `
  -F "description=Structured blazer for demo catalog validation" `
  -F "material=Poly-viscose blend" `
  -F "colors=black,white" `
  -F "sizes=S,M,L" `
  -F "style_tags=office,evening" `
  -F "in_stock=true"
```

Uploaded admin images are stored under:

- `ai-stylist-platform\ai-stylist-platform\static\uploads\catalog`

## Rollback

Demote the user:

```sql
update public.profiles
set role = 'user'
where email = 'demo-admin@example.com';
```

If you want to remove an accidentally added catalog item, either:

- use the admin delete endpoint, or
- remove the item from `outfit_generator\outfit_generator\catalog\sample_catalog.json`

## Notes and caveats

- Unauthorized requests return clean `401` or `403` responses.
- The browser may hide admin UI for non-admins, but real enforcement is server-side.
- No service-role secret is exposed to the browser.
- This is a hackathon-safe admin layer for the active JSON catalog source, not a full Supabase `public.products` CMS.
