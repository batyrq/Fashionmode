-- Supabase schema for AI Stylist / Virtual Try-On
-- Includes:
-- - Supabase Auth profile mirroring
-- - Marketplace catalog tables
-- - User-owned personalization / activity tables
-- - RLS policies for authenticated and anonymous access
-- - Storage bucket policies for uploads and generated outputs

begin;

create extension if not exists "pgcrypto";
create extension if not exists "vector";

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  username text unique,
  full_name text,
  avatar_url text,
  role text not null default 'user' check (role in ('user', 'admin', 'moderator')),
  locale text not null default 'en',
  onboarding_completed boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists set_profiles_updated_at on public.profiles;
create trigger set_profiles_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (
    id,
    email,
    full_name,
    avatar_url,
    role,
    locale,
    onboarding_completed
  )
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
    new.raw_user_meta_data->>'avatar_url',
    coalesce(new.raw_app_meta_data->>'role', 'user'),
    coalesce(new.raw_user_meta_data->>'locale', 'en'),
    false
  )
  on conflict (id) do nothing;

  return new;
end;
$$;

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (select p.role = 'admin'
     from public.profiles p
     where p.id = auth.uid()),
    false
  );
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

create table if not exists public.user_preferences (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  preferred_styles text[] not null default '{}',
  preferred_colors text[] not null default '{}',
  preferred_occasions text[] not null default '{}',
  budget_min integer,
  budget_max integer,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists user_preferences_user_id_key on public.user_preferences (user_id);

drop trigger if exists set_user_preferences_updated_at on public.user_preferences;
create trigger set_user_preferences_updated_at
before update on public.user_preferences
for each row execute function public.set_updated_at();

create table if not exists public.user_sizes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  top_size text,
  bottom_size text,
  dress_size text,
  shoe_size text,
  height_cm numeric(5,2),
  weight_kg numeric(5,2),
  body_measurements jsonb not null default '{}'::jsonb,
  fit_preference text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists user_sizes_user_id_key on public.user_sizes (user_id);

drop trigger if exists set_user_sizes_updated_at on public.user_sizes;
create trigger set_user_sizes_updated_at
before update on public.user_sizes
for each row execute function public.set_updated_at();

create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  slug text unique,
  name text not null,
  brand text,
  description text,
  category text not null,
  outfit_category text not null,
  style_tags text[] not null default '{}',
  colors text[] not null default '{}',
  sizes text[] not null default '{}',
  material text,
  price numeric(12,2) not null default 0,
  currency text not null default 'KZT',
  image_url text,
  product_url text,
  in_stock boolean not null default true,
  is_active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists set_products_updated_at on public.products;
create trigger set_products_updated_at
before update on public.products
for each row execute function public.set_updated_at();

create table if not exists public.product_variants (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products(id) on delete cascade,
  sku text unique,
  variant_name text,
  color text,
  size text,
  price numeric(12,2),
  currency text,
  stock_quantity integer not null default 0,
  image_url text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists set_product_variants_updated_at on public.product_variants;
create trigger set_product_variants_updated_at
before update on public.product_variants
for each row execute function public.set_updated_at();

create table if not exists public.product_images (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products(id) on delete cascade,
  variant_id uuid references public.product_variants(id) on delete cascade,
  image_url text not null,
  alt_text text,
  sort_order integer not null default 0,
  is_primary boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists set_product_images_updated_at on public.product_images;
create trigger set_product_images_updated_at
before update on public.product_images
for each row execute function public.set_updated_at();

create table if not exists public.product_attributes (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products(id) on delete cascade,
  attribute_name text not null,
  attribute_value text not null,
  attribute_group text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists product_attributes_product_id_idx on public.product_attributes (product_id);
create index if not exists product_attributes_name_value_idx on public.product_attributes (attribute_name, attribute_value);

drop trigger if exists set_product_attributes_updated_at on public.product_attributes;
create trigger set_product_attributes_updated_at
before update on public.product_attributes
for each row execute function public.set_updated_at();

create table if not exists public.product_embeddings (
  product_id uuid primary key references public.products(id) on delete cascade,
  embedding vector(512),
  embedding_model text not null default 'openai/clip-vit-base-patch32',
  embedding_source text not null default 'faiss-sync',
  embedding_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists set_product_embeddings_updated_at on public.product_embeddings;
create trigger set_product_embeddings_updated_at
before update on public.product_embeddings
for each row execute function public.set_updated_at();

create table if not exists public.saved_outfits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  style text,
  occasion text,
  total_price numeric(12,2),
  currency text not null default 'KZT',
  outfit_payload jsonb not null default '{}'::jsonb,
  source_type text,
  source_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists saved_outfits_user_id_idx on public.saved_outfits (user_id);

drop trigger if exists set_saved_outfits_updated_at on public.saved_outfits;
create trigger set_saved_outfits_updated_at
before update on public.saved_outfits
for each row execute function public.set_updated_at();

create table if not exists public.liked_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  liked_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  unique (user_id, product_id)
);

create index if not exists liked_items_user_id_idx on public.liked_items (user_id);
create index if not exists liked_items_product_id_idx on public.liked_items (product_id);

create table if not exists public.search_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  query_text text not null,
  budget integer,
  sizes text[] not null default '{}',
  style text,
  filters jsonb not null default '{}'::jsonb,
  result_count integer not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists search_history_user_id_idx on public.search_history (user_id);
create index if not exists search_history_created_at_idx on public.search_history (created_at desc);

create table if not exists public.uploaded_photos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  photo_type text not null check (photo_type in ('selfie', 'garment', 'full_body', 'tryon_source', 'other')),
  storage_bucket text not null,
  storage_path text not null,
  original_filename text,
  mime_type text,
  width integer,
  height integer,
  body_type text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists uploaded_photos_user_id_idx on public.uploaded_photos (user_id);
create index if not exists uploaded_photos_storage_path_idx on public.uploaded_photos (storage_bucket, storage_path);

drop trigger if exists set_uploaded_photos_updated_at on public.uploaded_photos;
create trigger set_uploaded_photos_updated_at
before update on public.uploaded_photos
for each row execute function public.set_updated_at();

create table if not exists public.tryon_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  source_photo_id uuid references public.uploaded_photos(id) on delete set null,
  product_id uuid references public.products(id) on delete set null,
  saved_outfit_id uuid references public.saved_outfits(id) on delete set null,
  status text not null default 'pending' check (status in ('pending', 'running', 'succeeded', 'failed', 'cancelled')),
  provider text not null default 'replicate',
  prompt text,
  request_payload jsonb not null default '{}'::jsonb,
  result_image_bucket text,
  result_image_path text,
  result_metadata jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists tryon_jobs_user_id_idx on public.tryon_jobs (user_id);
create index if not exists tryon_jobs_status_idx on public.tryon_jobs (status);

drop trigger if exists set_tryon_jobs_updated_at on public.tryon_jobs;
create trigger set_tryon_jobs_updated_at
before update on public.tryon_jobs
for each row execute function public.set_updated_at();

create table if not exists public.recommendation_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  input_photo_id uuid references public.uploaded_photos(id) on delete set null,
  query_text text,
  algorithm_version text not null default 'v1',
  top_k integer not null default 3,
  input_payload jsonb not null default '{}'::jsonb,
  output_payload jsonb not null default '{}'::jsonb,
  status text not null default 'completed' check (status in ('pending', 'running', 'completed', 'failed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists recommendation_runs_user_id_idx on public.recommendation_runs (user_id);
create index if not exists recommendation_runs_created_at_idx on public.recommendation_runs (created_at desc);

drop trigger if exists set_recommendation_runs_updated_at on public.recommendation_runs;
create trigger set_recommendation_runs_updated_at
before update on public.recommendation_runs
for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;
alter table public.user_preferences enable row level security;
alter table public.user_sizes enable row level security;
alter table public.products enable row level security;
alter table public.product_variants enable row level security;
alter table public.product_images enable row level security;
alter table public.product_attributes enable row level security;
alter table public.product_embeddings enable row level security;
alter table public.saved_outfits enable row level security;
alter table public.liked_items enable row level security;
alter table public.search_history enable row level security;
alter table public.uploaded_photos enable row level security;
alter table public.tryon_jobs enable row level security;
alter table public.recommendation_runs enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
on public.profiles
for select
to authenticated
using (id = auth.uid());

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
on public.profiles
for update
to authenticated
using (id = auth.uid())
with check (id = auth.uid());

drop policy if exists "profiles_admin_select_all" on public.profiles;
create policy "profiles_admin_select_all"
on public.profiles
for select
to authenticated
using (public.is_admin());

drop policy if exists "user_preferences_own" on public.user_preferences;
create policy "user_preferences_own"
on public.user_preferences
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "user_sizes_own" on public.user_sizes;
create policy "user_sizes_own"
on public.user_sizes
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "products_select_public" on public.products;
create policy "products_select_public"
on public.products
for select
to anon, authenticated
using (true);

drop policy if exists "products_write_admin" on public.products;
create policy "products_write_admin"
on public.products
for insert
to authenticated
with check (public.is_admin());

drop policy if exists "products_update_admin" on public.products;
create policy "products_update_admin"
on public.products
for update
to authenticated
using (public.is_admin())
with check (public.is_admin());

drop policy if exists "products_delete_admin" on public.products;
create policy "products_delete_admin"
on public.products
for delete
to authenticated
using (public.is_admin());

drop policy if exists "product_variants_select_public" on public.product_variants;
create policy "product_variants_select_public"
on public.product_variants
for select
to anon, authenticated
using (true);

drop policy if exists "product_variants_write_admin" on public.product_variants;
create policy "product_variants_write_admin"
on public.product_variants
for all
to authenticated
using (public.is_admin())
with check (public.is_admin());

drop policy if exists "product_images_select_public" on public.product_images;
create policy "product_images_select_public"
on public.product_images
for select
to anon, authenticated
using (true);

drop policy if exists "product_images_write_admin" on public.product_images;
create policy "product_images_write_admin"
on public.product_images
for all
to authenticated
using (public.is_admin())
with check (public.is_admin());

drop policy if exists "product_attributes_select_public" on public.product_attributes;
create policy "product_attributes_select_public"
on public.product_attributes
for select
to anon, authenticated
using (true);

drop policy if exists "product_attributes_write_admin" on public.product_attributes;
create policy "product_attributes_write_admin"
on public.product_attributes
for all
to authenticated
using (public.is_admin())
with check (public.is_admin());

drop policy if exists "product_embeddings_select_admin" on public.product_embeddings;
create policy "product_embeddings_select_admin"
on public.product_embeddings
for select
to authenticated
using (public.is_admin());

drop policy if exists "product_embeddings_write_admin" on public.product_embeddings;
create policy "product_embeddings_write_admin"
on public.product_embeddings
for all
to authenticated
using (public.is_admin())
with check (public.is_admin());

drop policy if exists "saved_outfits_own" on public.saved_outfits;
create policy "saved_outfits_own"
on public.saved_outfits
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "liked_items_own" on public.liked_items;
create policy "liked_items_own"
on public.liked_items
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "search_history_own" on public.search_history;
create policy "search_history_own"
on public.search_history
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "uploaded_photos_own" on public.uploaded_photos;
create policy "uploaded_photos_own"
on public.uploaded_photos
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "tryon_jobs_own" on public.tryon_jobs;
create policy "tryon_jobs_own"
on public.tryon_jobs
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "recommendation_runs_own" on public.recommendation_runs;
create policy "recommendation_runs_own"
on public.recommendation_runs
for all
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

insert into storage.buckets (id, name, public)
values
  ('catalog-images', 'catalog-images', true),
  ('user-uploads', 'user-uploads', false),
  ('tryon-results', 'tryon-results', false)
on conflict (id) do update
set name = excluded.name,
    public = excluded.public;

drop policy if exists "catalog_images_public_read" on storage.objects;
create policy "catalog_images_public_read"
on storage.objects
for select
to anon, authenticated
using (bucket_id = 'catalog-images');

drop policy if exists "catalog_images_admin_write" on storage.objects;
create policy "catalog_images_admin_write"
on storage.objects
for all
to authenticated
using (bucket_id = 'catalog-images' and public.is_admin())
with check (bucket_id = 'catalog-images' and public.is_admin());

drop policy if exists "user_uploads_owner_read" on storage.objects;
create policy "user_uploads_owner_read"
on storage.objects
for select
to authenticated
using (bucket_id = 'user-uploads' and owner = auth.uid());

drop policy if exists "user_uploads_owner_write" on storage.objects;
create policy "user_uploads_owner_write"
on storage.objects
for insert
to authenticated
with check (bucket_id = 'user-uploads' and owner = auth.uid());

drop policy if exists "user_uploads_owner_update" on storage.objects;
create policy "user_uploads_owner_update"
on storage.objects
for update
to authenticated
using (bucket_id = 'user-uploads' and owner = auth.uid())
with check (bucket_id = 'user-uploads' and owner = auth.uid());

drop policy if exists "user_uploads_owner_delete" on storage.objects;
create policy "user_uploads_owner_delete"
on storage.objects
for delete
to authenticated
using (bucket_id = 'user-uploads' and owner = auth.uid());

drop policy if exists "tryon_results_owner_read" on storage.objects;
create policy "tryon_results_owner_read"
on storage.objects
for select
to authenticated
using (bucket_id = 'tryon-results' and owner_id = auth.uid()::text);

drop policy if exists "tryon_results_owner_write" on storage.objects;
create policy "tryon_results_owner_write"
on storage.objects
for insert
to authenticated
with check (bucket_id = 'tryon-results' and owner_id = auth.uid()::text);

drop policy if exists "tryon_results_owner_update" on storage.objects;
create policy "tryon_results_owner_update"
on storage.objects
for update
to authenticated
using (bucket_id = 'tryon-results' and owner_id = auth.uid()::text)
with check (bucket_id = 'tryon-results' and owner_id = auth.uid()::text);

drop policy if exists "tryon_results_owner_delete" on storage.objects;
create policy "tryon_results_owner_delete"
on storage.objects
for delete
to authenticated
using (bucket_id = 'tryon-results' and owner_id = auth.uid()::text);

commit;
