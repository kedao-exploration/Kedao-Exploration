-- 在 Supabase Dashboard > SQL Editor 中完整运行本文件。
-- 表只允许网页匿名新增数据，不允许匿名读取、修改或删除。

create extension if not exists pgcrypto;

create table if not exists public.exploration_submissions (
    id uuid primary key default gen_random_uuid(),
    name text not null check (char_length(btrim(name)) between 1 and 80),
    major text not null check (char_length(btrim(major)) between 1 and 120),
    email text not null check (
        char_length(email) between 3 and 320
        and email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'
    ),
    role text not null check (role in ('participant', 'organizer')),
    career text[] not null check (
        cardinality(career) between 1 and 4
        and career <@ array['lecture', 'lab', 'club', 'industry']::text[]
    ),
    life text[] not null check (
        cardinality(life) between 1 and 3
        and life <@ array['walk', 'heritage', 'citywalk']::text[]
    ),
    selected_modules text[] not null check (cardinality(selected_modules) between 2 and 7),
    generated_paths text[] not null check (cardinality(generated_paths) between 3 and 4),
    client_submitted_at timestamptz not null,
    user_agent text check (user_agent is null or char_length(user_agent) <= 1000),
    page_version text not null default '1.0.0' check (char_length(page_version) <= 30),
    created_at timestamptz not null default now()
);

alter table public.exploration_submissions enable row level security;

revoke all on table public.exploration_submissions from anon, authenticated;
grant insert on table public.exploration_submissions to anon;

drop policy if exists "public_can_submit_exploration" on public.exploration_submissions;
create policy "public_can_submit_exploration"
on public.exploration_submissions
for insert
to anon
with check (true);

comment on table public.exploration_submissions is
'科道书院探索盲盒网页提交；客户端只能新增，不能读取、修改或删除。';

-- 管理员在 SQL Editor 中查询数据：
-- select * from public.exploration_submissions order by created_at desc;
