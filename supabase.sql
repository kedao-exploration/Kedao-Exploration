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
    exploration_type text,
    career text[] not null check (
        cardinality(career) between 0 and 4
        and career <@ array['lecture', 'lab', 'club', 'industry']::text[]
    ),
    life text[] not null check (
        cardinality(life) between 0 and 3
        and life <@ array['walk', 'heritage', 'citywalk']::text[]
    ),
    selected_modules text[] not null check (cardinality(selected_modules) between 1 and 7),
    generated_paths text[] not null check (cardinality(generated_paths) between 3 and 4),
    client_submitted_at timestamptz not null,
    user_agent text check (user_agent is null or char_length(user_agent) <= 1000),
    page_version text not null default '2.1.0' check (char_length(page_version) <= 30),
    created_at timestamptz not null default now()
);

-- 兼容已经执行过 1.0 版 SQL 的项目；NOT VALID 会保留历史记录，
-- 但仍会严格校验从现在开始写入的新记录。
alter table public.exploration_submissions
    add column if not exists exploration_type text;

alter table public.exploration_submissions
    alter column page_version set default '2.1.0';

alter table public.exploration_submissions
    drop constraint if exists exploration_submissions_career_check,
    drop constraint if exists exploration_submissions_life_check,
    drop constraint if exists exploration_submissions_selected_modules_check,
    drop constraint if exists exploration_submissions_generated_paths_check,
    drop constraint if exists exploration_type_required,
    drop constraint if exists exploration_type_matches_modules;

alter table public.exploration_submissions
    add constraint exploration_submissions_career_check check (
        cardinality(career) between 0 and 4
        and career <@ array['lecture', 'lab', 'club', 'industry']::text[]
    ) not valid,
    add constraint exploration_submissions_life_check check (
        cardinality(life) between 0 and 3
        and life <@ array['walk', 'heritage', 'citywalk']::text[]
    ) not valid,
    add constraint exploration_submissions_selected_modules_check
        check (cardinality(selected_modules) between 1 and 7) not valid,
    add constraint exploration_submissions_generated_paths_check
        check (cardinality(generated_paths) between 3 and 4) not valid,
    add constraint exploration_type_required
        check (exploration_type in ('career', 'life', 'both')) not valid,
    add constraint exploration_type_matches_modules check (
        (
            exploration_type = 'career'
            and cardinality(career) between 1 and 4
            and cardinality(life) = 0
        )
        or
        (
            exploration_type = 'life'
            and cardinality(life) between 1 and 3
            and cardinality(career) = 0
        )
        or
        (
            exploration_type = 'both'
            and cardinality(career) between 1 and 4
            and cardinality(life) between 1 and 3
        )
    ) not valid;

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
