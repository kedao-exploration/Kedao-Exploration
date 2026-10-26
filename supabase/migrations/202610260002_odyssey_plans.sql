-- Require the three structured Odyssey plans for every new onboarding submission.
create or replace function public.valid_odyssey_answers(p_answers jsonb)
returns boolean
language sql
immutable
set search_path = public, pg_temp
as $$
  select coalesce(bool_and(
    coalesce(jsonb_typeof(p_answers -> plan_key), '') = 'object'
    and not exists (
      select 1
      from unnest(array['title','five_year_goal','core_activities','capabilities','challenges']) as fields(field_key)
      where coalesce(jsonb_typeof(p_answers -> plan_key -> field_key), '') <> 'string'
         or char_length(btrim(coalesce(p_answers -> plan_key ->> field_key, ''))) not between 1 and
            case when field_key = 'title' then 120 else 800 end
    )
  ), false)
  from unnest(array['odyssey_a','odyssey_b','odyssey_c']) as plans(plan_key)
$$;

create or replace function public.enforce_current_onboarding_version()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  new.form_version := '3.1.0';
  if not public.valid_odyssey_answers(new.answers) then
    raise exception '请完整填写三个奥德赛计划，每项内容需在允许长度内';
  end if;
  return new;
end
$$;

drop trigger if exists onboarding_require_odyssey on public.onboarding_submissions;
create trigger onboarding_require_odyssey
before insert on public.onboarding_submissions
for each row execute function public.enforce_current_onboarding_version();

alter table public.onboarding_submissions alter column form_version set default '3.1.0';
revoke all on function public.valid_odyssey_answers(jsonb) from public, anon, authenticated;
revoke all on function public.enforce_current_onboarding_version() from public, anon, authenticated;

comment on function public.valid_odyssey_answers(jsonb) is 'Validates the three structured Odyssey-plan scenarios without treating them as committed goals.';
