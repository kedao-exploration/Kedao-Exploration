-- 科道书院学生画像与活动推荐系统
create extension if not exists pgcrypto;
create extension if not exists citext;

create table if not exists public.students (
  id uuid primary key default gen_random_uuid(),
  student_number text not null unique check (char_length(btrim(student_number)) between 1 and 40),
  email citext not null unique check (email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'),
  name text check (name is null or char_length(btrim(name)) between 1 and 80),
  major text check (major is null or char_length(btrim(major)) between 1 and 120),
  year_level text check (year_level is null or char_length(year_level) <= 40),
  consent_status text not null default 'pending' check (consent_status in ('pending','granted','withdrawn')),
  consented_at timestamptz,
  deactivated_at timestamptz,
  model_status text not null default 'not_started' check (model_status in ('not_started','queued','processing','ready','failed','stale')),
  last_profile_input_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table if not exists public.student_invites (
  id uuid primary key default gen_random_uuid(), student_id uuid not null references public.students(id) on delete cascade,
  token_hash text not null unique check (char_length(token_hash) = 64), expires_at timestamptz,
  consumed_at timestamptz, revoked_at timestamptz, created_by text not null default 'advisor', created_at timestamptz not null default now()
);
create index if not exists student_invites_student_idx on public.student_invites(student_id);
create table if not exists public.onboarding_submissions (
  id uuid primary key default gen_random_uuid(), student_id uuid not null references public.students(id) on delete cascade,
  answers jsonb not null check (jsonb_typeof(answers) = 'object'), form_version text not null default '3.0.0' check (char_length(form_version) <= 30),
  submitted_at timestamptz not null default now(), created_at timestamptz not null default now()
);
create index if not exists onboarding_student_time_idx on public.onboarding_submissions(student_id, submitted_at desc);

create table if not exists public.survey_definitions (
  id uuid primary key default gen_random_uuid(), title text not null check (char_length(btrim(title)) between 1 and 160),
  description text check (description is null or char_length(description) <= 2000), version integer not null default 1 check (version > 0),
  schema jsonb not null check (jsonb_typeof(schema) = 'object' and jsonb_typeof(schema->'questions') = 'array'),
  status text not null default 'draft' check (status in ('draft','published','archived')), published_at timestamptz,
  created_by text not null default 'advisor', created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.survey_assignments (
  id uuid primary key default gen_random_uuid(), survey_id uuid not null references public.survey_definitions(id) on delete cascade,
  student_id uuid not null references public.students(id) on delete cascade, token_hash text not null unique check (char_length(token_hash) = 64),
  status text not null default 'pending' check (status in ('pending','opened','submitted','expired','revoked')),
  expires_at timestamptz, opened_at timestamptz, submitted_at timestamptz, created_at timestamptz not null default now(), unique (survey_id, student_id)
);
create index if not exists survey_assignment_student_idx on public.survey_assignments(student_id, created_at desc);
create table if not exists public.survey_responses (
  id uuid primary key default gen_random_uuid(), assignment_id uuid not null unique references public.survey_assignments(id) on delete cascade,
  survey_id uuid not null references public.survey_definitions(id) on delete cascade,
  student_id uuid not null references public.students(id) on delete cascade,
  answers jsonb not null check (jsonb_typeof(answers) = 'object'), submitted_at timestamptz not null default now(), created_at timestamptz not null default now()
);
create index if not exists survey_response_student_time_idx on public.survey_responses(student_id, submitted_at desc);

create table if not exists public.student_model_versions (
  id uuid primary key default gen_random_uuid(), student_id uuid not null references public.students(id) on delete cascade,
  version integer not null check (version > 0), input_hash text not null, profile jsonb not null check (jsonb_typeof(profile) = 'object'),
  summary text not null default '', model_name text not null default 'deepseek-ai/DeepSeek-V4-Flash', prompt_version text not null,
  source_snapshot jsonb not null default '{}'::jsonb, generated_at timestamptz not null default now(), created_at timestamptz not null default now(),
  unique (student_id, version), unique (student_id, input_hash)
);
create index if not exists student_model_latest_idx on public.student_model_versions(student_id, version desc);
alter table public.students add column if not exists current_model_version_id uuid references public.student_model_versions(id) on delete set null;
create table if not exists public.model_update_jobs (
  id uuid primary key default gen_random_uuid(), student_id uuid not null references public.students(id) on delete cascade,
  reason text not null, status text not null default 'pending' check (status in ('pending','processing','completed','failed')),
  attempts integer not null default 0 check (attempts >= 0), last_error text, run_after timestamptz not null default now(),
  locked_at timestamptz, completed_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index if not exists model_jobs_pending_idx on public.model_update_jobs(status, run_after, created_at);
create unique index if not exists model_jobs_one_active_per_student_idx on public.model_update_jobs(student_id) where status in ('pending','processing');

create table if not exists public.aggregate_reports (
  id uuid primary key default gen_random_uuid(), report_date date not null, source_snapshot jsonb not null default '{}'::jsonb,
  deterministic_metrics jsonb not null default '{}'::jsonb, report jsonb not null check (jsonb_typeof(report) = 'object'),
  model_name text not null default 'deepseek-ai/DeepSeek-V4-Flash', prompt_version text not null,
  generated_at timestamptz not null default now(), created_at timestamptz not null default now()
);
create index if not exists aggregate_reports_date_idx on public.aggregate_reports(report_date desc, generated_at desc);
create table if not exists public.activities (
  id uuid primary key default gen_random_uuid(), title text not null check (char_length(btrim(title)) between 1 and 160),
  description text not null check (char_length(btrim(description)) between 1 and 10000), start_at timestamptz not null, end_at timestamptz not null,
  location text check (location is null or char_length(location) <= 300), poster_path text, poster_url text, tags text[] not null default '{}',
  capacity integer check (capacity is null or capacity > 0), status text not null default 'draft' check (status in ('draft','matching','ready','archived','cancelled')),
  created_by text not null default 'advisor', created_at timestamptz not null default now(), updated_at timestamptz not null default now(), check (end_at > start_at)
);
create table if not exists public.activity_match_runs (
  id uuid primary key default gen_random_uuid(), activity_id uuid not null references public.activities(id) on delete cascade,
  status text not null default 'pending' check (status in ('pending','processing','completed','failed')),
  model_name text not null default 'deepseek-ai/DeepSeek-V4-Flash', prompt_version text not null default 'activity-match-v1',
  student_count integer not null default 0, attempts integer not null default 0, last_error text, started_at timestamptz, completed_at timestamptz, created_at timestamptz not null default now()
);
create table if not exists public.campaigns (
  id uuid primary key default gen_random_uuid(), activity_id uuid references public.activities(id) on delete set null,
  survey_id uuid references public.survey_definitions(id) on delete set null, match_run_id uuid references public.activity_match_runs(id) on delete set null,
  name text not null check (char_length(btrim(name)) between 1 and 200), kind text not null check (kind in ('activity','survey')),
  status text not null default 'draft' check (status in ('draft','review','confirmed','exported')), confirmed_at timestamptz,
  created_by text not null default 'advisor', created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.campaign_recipients (
  id uuid primary key default gen_random_uuid(), campaign_id uuid not null references public.campaigns(id) on delete cascade,
  student_id uuid not null references public.students(id) on delete cascade, recommendation jsonb not null default '{}'::jsonb,
  source text not null default 'llm' check (source in ('llm','advisor','reused')), included boolean not null default true,
  advisor_note text check (advisor_note is null or char_length(advisor_note) <= 1000), updated_at timestamptz not null default now(),
  created_at timestamptz not null default now(), unique (campaign_id, student_id)
);
create index if not exists campaign_recipients_campaign_idx on public.campaign_recipients(campaign_id, included);
create table if not exists public.audit_logs (
  id bigint generated always as identity primary key, actor text not null, action text not null, entity_type text not null,
  entity_id text, details jsonb not null default '{}'::jsonb, created_at timestamptz not null default now()
);
create index if not exists audit_logs_time_idx on public.audit_logs(created_at desc);

create or replace function public.touch_updated_at() returns trigger language plpgsql as $$ begin new.updated_at = now(); return new; end $$;
drop trigger if exists students_touch_updated_at on public.students;
create trigger students_touch_updated_at before update on public.students for each row execute function public.touch_updated_at();
drop trigger if exists survey_definitions_touch_updated_at on public.survey_definitions;
create trigger survey_definitions_touch_updated_at before update on public.survey_definitions for each row execute function public.touch_updated_at();
drop trigger if exists activities_touch_updated_at on public.activities;
create trigger activities_touch_updated_at before update on public.activities for each row execute function public.touch_updated_at();
drop trigger if exists campaigns_touch_updated_at on public.campaigns;
create trigger campaigns_touch_updated_at before update on public.campaigns for each row execute function public.touch_updated_at();
drop trigger if exists campaign_recipients_touch_updated_at on public.campaign_recipients;
create trigger campaign_recipients_touch_updated_at before update on public.campaign_recipients for each row execute function public.touch_updated_at();
drop trigger if exists model_update_jobs_touch_updated_at on public.model_update_jobs;
create trigger model_update_jobs_touch_updated_at before update on public.model_update_jobs for each row execute function public.touch_updated_at();

create or replace function public.freeze_published_survey() returns trigger language plpgsql as $$
begin
  if old.status in ('published','archived') and (
    new.title is distinct from old.title or
    new.description is distinct from old.description or
    new.version is distinct from old.version or
    new.schema is distinct from old.schema
  ) then
    raise exception '已发布问卷的题目与版本不可修改，请复制为新版本';
  end if;
  return new;
end $$;
drop trigger if exists survey_definitions_freeze_published on public.survey_definitions;
create trigger survey_definitions_freeze_published before update on public.survey_definitions for each row execute function public.freeze_published_survey();

create or replace function public.enqueue_student_model_update() returns trigger language plpgsql security definer set search_path = public, pg_temp as $$
declare v_student_id uuid;
begin
  v_student_id := new.student_id;
  update public.students set model_status = 'queued', last_profile_input_at = now() where id = v_student_id;
  if not exists (select 1 from public.model_update_jobs where student_id = v_student_id and status in ('pending','processing')) then
    insert into public.model_update_jobs(student_id, reason) values (v_student_id, tg_table_name || ':' || tg_op);
  end if;
  return new;
end $$;
drop trigger if exists onboarding_enqueue_model on public.onboarding_submissions;
create trigger onboarding_enqueue_model after insert on public.onboarding_submissions for each row execute function public.enqueue_student_model_update();
drop trigger if exists survey_response_enqueue_model on public.survey_responses;
create trigger survey_response_enqueue_model after insert on public.survey_responses for each row execute function public.enqueue_student_model_update();

create or replace function public.claim_invite_and_submit_onboarding(p_token text, p_payload jsonb) returns jsonb
language plpgsql security definer set search_path = public, extensions, pg_temp as $$
declare v_invite public.student_invites%rowtype; v_student public.students%rowtype; v_submission_id uuid; v_email citext; v_student_number text;
begin
  if p_token is null or char_length(btrim(p_token)) < 8 then raise exception '邀请码格式不正确'; end if;
  if jsonb_typeof(p_payload) <> 'object' then raise exception '提交内容格式不正确'; end if;
  if length(p_payload::text) > 100000 then raise exception '提交内容过长'; end if;
  if coalesce((p_payload->>'consent')::boolean, false) is not true then raise exception '请先阅读并同意数据使用说明'; end if;
  select * into v_invite from public.student_invites where token_hash = encode(digest(btrim(p_token), 'sha256'), 'hex') for update;
  if not found or v_invite.revoked_at is not null then raise exception '邀请码无效'; end if;
  if v_invite.consumed_at is not null then raise exception '该邀请码已使用'; end if;
  if v_invite.expires_at is not null and v_invite.expires_at < now() then raise exception '邀请码已过期'; end if;
  select * into v_student from public.students where id = v_invite.student_id for update;
  v_email := lower(btrim(coalesce(p_payload->>'email','')))::citext;
  v_student_number := btrim(coalesce(p_payload->>'student_number',''));
  if v_email::text !~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$' then raise exception '邮箱格式不正确'; end if;
  if v_email <> v_student.email then raise exception '邮箱与邀请码绑定信息不一致'; end if;
  if v_student_number <> v_student.student_number then raise exception '学号与邀请码绑定信息不一致'; end if;
  if char_length(btrim(coalesce(p_payload->>'name',''))) not between 1 and 80 then raise exception '姓名格式不正确'; end if;
  if char_length(btrim(coalesce(p_payload->>'major',''))) not between 1 and 120 then raise exception '专业格式不正确'; end if;
  if coalesce(p_payload->>'year_level','') not in ('大一','大二','大三','大四','研究生','其他') then raise exception '年级选项不正确'; end if;
  if coalesce(p_payload->>'weekly_load','') not in ('比较轻松','基本平衡','有些忙碌','经常超负荷','难以判断') then raise exception '任务负荷选项不正确'; end if;
  if coalesce(p_payload->>'next_30_days','') not in ('获得信息与路径','制定计划','找到同伴','联系导师/学长姐','报名一次活动','完成一个具体任务','先恢复精力','暂时不确定') then raise exception '近期目标选项不正确'; end if;
  if p_payload ? 'current_courses' and char_length(coalesce(p_payload->>'current_courses','')) > 500 then raise exception '文本回答过长'; end if;
  if jsonb_typeof(p_payload->'self_regulation') <> 'object' or exists (
    select 1 from unnest(array['planning','time_management','persistence','help_seeking','self_efficacy']) as key
    where jsonb_typeof(p_payload->'self_regulation'->key) <> 'number'
       or ((p_payload->'self_regulation'->>key)::numeric not between 1 and 5)
       or ((p_payload->'self_regulation'->>key)::numeric <> trunc((p_payload->'self_regulation'->>key)::numeric))
  ) then raise exception '自我调节量表回答不完整'; end if;
  if exists (
    select 1 from unnest(array['current_learning','clubs','interest_topics','activity_formats','available_times','participation_constraints','long_term_goals','semester_goals','barriers','desired_support']) as key
    where jsonb_typeof(p_payload->key) <> 'array' or jsonb_array_length(p_payload->key) = 0 or jsonb_array_length(p_payload->key) > 20
       or exists (select 1 from jsonb_array_elements(p_payload->key) item where jsonb_typeof(item) <> 'string' or char_length(item#>>'{}') > 120)
  ) then raise exception '多选题回答格式不正确'; end if;
  if exists (
    select 1
    from (values
      ('current_learning', array['专业课程','语言与标化考试','科研训练','竞赛','实习与职业技能','人文艺术','运动健康','还在探索']::text[]),
      ('clubs', array['学术科研','创新创业','文体艺术','志愿公益','学生工作','运动社群','校外实践','组织者/负责人','暂未参加']::text[]),
      ('interest_topics', array['保研与科研','考研规划','出国交流','行业与就业','创新创业','AI 与科技','人文艺术','城市探索','心理与成长','运动健康','公益与社会参与']::text[]),
      ('activity_formats', array['短讲座','深度工作坊','圆桌/小组交流','实验室或企业参访','长期项目','社团体验','一对一咨询','线上资源']::text[]),
      ('available_times', array['工作日午间','工作日下午','工作日晚上','周六','周日','时间不固定']::text[]),
      ('participation_constraints', array['课程冲突','任务太多','地点/交通','费用','不认识其他人','不确定是否适合','需要无障碍支持','没有明显限制']::text[]),
      ('long_term_goals', array['保研','考研','出国/境深造','直接就业','公务员/选调','创新创业','学术研究','还在探索']::text[]),
      ('semester_goals', array['提升课程成绩','通过重要考试','进入实验室','完成科研成果','参加竞赛','找到实习','加入/建设社团','改善作息与状态','扩大社交连接']::text[]),
      ('barriers', array['信息不足','不知道从哪里开始','时间管理','行动动力','能力准备','资源或机会','缺少同伴','压力或情绪','没有明显阻碍']::text[]),
      ('desired_support', array['经验分享','路线规划','技能训练','导师/学长姐连接','同伴小组','实践机会','心理成长活动','安静的自主探索空间']::text[])
    ) as allowed(question_id, options)
    cross join lateral jsonb_array_elements_text(p_payload->allowed.question_id) answer
    where not (answer = any(allowed.options))
  ) then raise exception '多选题包含无效选项'; end if;
  if exists (
    select 1 from unnest(array['who5_cheerful','who5_calm','who5_active','who5_rested','who5_interested']) as key
    where p_payload ? key and coalesce(p_payload->>key,'') not in ('0','1','2','3','4','5','prefer_not')
  ) then raise exception '幸福感量表包含无效选项'; end if;
  if p_payload ? 'stress_level' and coalesce(p_payload->>'stress_level','') not in ('很低','较低','适中','较高','很高','暂不回答') then raise exception '压力选项不正确'; end if;
  if p_payload ? 'belonging' and coalesce(p_payload->>'belonging','') not in ('很少','偶尔','一般','大多数时候','非常强','暂不回答') then raise exception '归属感选项不正确'; end if;
  update public.students set name=btrim(p_payload->>'name'), major=btrim(p_payload->>'major'),
    year_level=left(btrim(coalesce(p_payload->>'year_level','')),40), consent_status='granted', consented_at=now(), deactivated_at=null where id=v_student.id;
  insert into public.onboarding_submissions(student_id,answers,form_version,submitted_at)
  values(v_student.id,p_payload-array['name','email','student_number'],left(coalesce(p_payload->>'form_version','3.0.0'),30),coalesce((p_payload->>'client_submitted_at')::timestamptz,now()))
  returning id into v_submission_id;
  update public.student_invites set consumed_at=now() where id=v_invite.id;
  insert into public.audit_logs(actor,action,entity_type,entity_id,details) values('student','onboarding_submitted','student',v_student.id::text,jsonb_build_object('submission_id',v_submission_id));
  return jsonb_build_object('ok',true,'student_id',v_student.id,'submission_id',v_submission_id);
end $$;

create or replace function public.get_survey_by_token(p_token text) returns jsonb
language plpgsql security definer set search_path = public, extensions, pg_temp as $$
declare v_assignment public.survey_assignments%rowtype; v_survey public.survey_definitions%rowtype;
begin
  select * into v_assignment from public.survey_assignments where token_hash=encode(digest(btrim(p_token),'sha256'),'hex') for update;
  if not found or v_assignment.status in ('revoked','expired','submitted') then raise exception '问卷链接无效或已完成'; end if;
  if v_assignment.expires_at is not null and v_assignment.expires_at<now() then update public.survey_assignments set status='expired' where id=v_assignment.id; raise exception '问卷链接已过期'; end if;
  select * into v_survey from public.survey_definitions where id=v_assignment.survey_id and status='published';
  if not found then raise exception '问卷尚未发布'; end if;
  if v_assignment.status='pending' then update public.survey_assignments set status='opened',opened_at=now() where id=v_assignment.id; end if;
  return jsonb_build_object('id',v_survey.id,'title',v_survey.title,'description',v_survey.description,'version',v_survey.version,'questions',v_survey.schema->'questions');
end $$;

create or replace function public.submit_survey_response(p_token text,p_answers jsonb) returns jsonb
language plpgsql security definer set search_path = public, extensions, pg_temp as $$
declare v_assignment public.survey_assignments%rowtype; v_survey public.survey_definitions%rowtype; v_question jsonb; v_id text; v_type text; v_value jsonb; v_response_id uuid;
begin
  if jsonb_typeof(p_answers)<>'object' then raise exception '回答格式不正确'; end if;
  if length(p_answers::text)>100000 then raise exception '回答内容过长'; end if;
  select * into v_assignment from public.survey_assignments where token_hash=encode(digest(btrim(p_token),'sha256'),'hex') for update;
  if not found or v_assignment.status in ('revoked','expired','submitted') then raise exception '问卷链接无效或已完成'; end if;
  if v_assignment.expires_at is not null and v_assignment.expires_at<now() then raise exception '问卷链接已过期'; end if;
  select * into v_survey from public.survey_definitions where id=v_assignment.survey_id and status='published';
  if not found then raise exception '问卷尚未发布'; end if;
  if exists (
    select 1 from jsonb_object_keys(p_answers) answer_key
    where not exists (select 1 from jsonb_array_elements(v_survey.schema->'questions') q where q->>'id'=answer_key)
  ) then raise exception '回答包含未知题目'; end if;
  for v_question in select value from jsonb_array_elements(v_survey.schema->'questions') loop
    v_id:=v_question->>'id'; v_type:=v_question->>'type'; v_value:=p_answers->v_id;
    if coalesce((v_question->>'required')::boolean,false) and (v_value is null or v_value='null'::jsonb or v_value='""'::jsonb or v_value='[]'::jsonb) then raise exception '存在未完成的必填题'; end if;
    if v_value is not null then
      if v_type='multiple' and jsonb_typeof(v_value)<>'array' then raise exception '多选题回答格式不正确'; end if;
      if v_type in ('single','short_text','long_text') and jsonb_typeof(v_value)<>'string' then raise exception '文本或单选题回答格式不正确'; end if;
      if v_type='scale' and jsonb_typeof(v_value)<>'number' then raise exception '量表题回答格式不正确'; end if;
      if v_type in ('short_text','long_text') and char_length(v_value#>>'{}')>least(coalesce((v_question->>'maxLength')::integer,2000),10000) then raise exception '文本回答过长'; end if;
      if v_type='single' and not exists (select 1 from jsonb_array_elements(coalesce(v_question->'options','[]'::jsonb)) option where option->>'value'=v_value#>>'{}') then raise exception '单选题包含无效选项'; end if;
      if v_type='multiple' and exists (
        select 1 from jsonb_array_elements(v_value) answer
        where jsonb_typeof(answer)<>'string' or not exists (
          select 1 from jsonb_array_elements(coalesce(v_question->'options','[]'::jsonb)) option where option->>'value'=answer#>>'{}'
        )
      ) then raise exception '多选题包含无效选项'; end if;
      if v_type='scale' and (
        (v_value#>>'{}')::numeric < coalesce((v_question->>'min')::numeric,1) or
        (v_value#>>'{}')::numeric > coalesce((v_question->>'max')::numeric,5) or
        (v_value#>>'{}')::numeric <> trunc((v_value#>>'{}')::numeric)
      ) then raise exception '量表题超出允许范围'; end if;
    end if;
  end loop;
  insert into public.survey_responses(assignment_id,survey_id,student_id,answers) values(v_assignment.id,v_assignment.survey_id,v_assignment.student_id,p_answers) returning id into v_response_id;
  update public.survey_assignments set status='submitted',submitted_at=now() where id=v_assignment.id;
  insert into public.audit_logs(actor,action,entity_type,entity_id,details) values('student','survey_submitted','student',v_assignment.student_id::text,jsonb_build_object('survey_id',v_survey.id,'response_id',v_response_id));
  return jsonb_build_object('ok',true,'response_id',v_response_id);
end $$;

do $$ declare t text; begin
  foreach t in array array['students','student_invites','onboarding_submissions','survey_definitions','survey_assignments','survey_responses','student_model_versions','model_update_jobs','aggregate_reports','activities','activity_match_runs','campaigns','campaign_recipients','audit_logs'] loop
    execute format('alter table public.%I enable row level security',t); execute format('revoke all on table public.%I from anon, authenticated',t);
  end loop;
end $$;
revoke all on function public.claim_invite_and_submit_onboarding(text,jsonb) from public;
revoke all on function public.get_survey_by_token(text) from public;
revoke all on function public.submit_survey_response(text,jsonb) from public;
grant execute on function public.claim_invite_and_submit_onboarding(text,jsonb) to anon;
grant execute on function public.get_survey_by_token(text) to anon;
grant execute on function public.submit_survey_response(text,jsonb) to anon;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('activity-posters','activity-posters',true,10485760,array['image/jpeg','image/png','image/webp'])
on conflict(id) do update set public=excluded.public,file_size_limit=excluded.file_size_limit,allowed_mime_types=excluded.allowed_mime_types;
comment on table public.student_model_versions is 'Immutable, evidence-linked student-model versions.';
comment on table public.survey_definitions is 'Versioned JSONB survey definitions; published versions are immutable by application policy.';
