-- 在 Supabase Dashboard -> SQL Editor 中完整执行一次
create extension if not exists pgcrypto;

create table if not exists public.explore_declarations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 1 and 20),
  ability text not null,
  feeling text not null,
  type text not null,
  declaration text not null check (char_length(declaration) between 1 and 50),
  created_at timestamptz not null default now()
);

create index if not exists explore_declarations_created_at_idx
  on public.explore_declarations (created_at desc);
create index if not exists explore_declarations_type_idx
  on public.explore_declarations (type);

alter table public.explore_declarations enable row level security;

drop policy if exists "public can read declarations" on public.explore_declarations;
create policy "public can read declarations"
  on public.explore_declarations for select to anon, authenticated using (true);

drop policy if exists "public can submit declarations" on public.explore_declarations;
create policy "public can submit declarations"
  on public.explore_declarations for insert to anon, authenticated with check (true);

drop policy if exists "public can delete declarations" on public.explore_declarations;
create policy "public can delete declarations"
  on public.explore_declarations for delete to anon, authenticated using (true);
