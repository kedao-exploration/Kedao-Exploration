-- Open first-time onboarding to all students while retaining tokenized follow-up surveys.
create or replace function public.submit_open_onboarding(p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  v_student public.students%rowtype;
  v_student_id uuid;
  v_number_id uuid;
  v_email_id uuid;
  v_submission_id uuid;
  v_email citext;
  v_student_number text;
begin
  if jsonb_typeof(p_payload) <> 'object' then raise exception '提交内容格式不正确'; end if;
  if length(p_payload::text) > 100000 then raise exception '提交内容过长'; end if;
  if coalesce((p_payload->>'consent')::boolean, false) is not true then raise exception '请先阅读并同意数据使用说明'; end if;

  v_email := lower(btrim(coalesce(p_payload->>'email','')))::citext;
  v_student_number := btrim(coalesce(p_payload->>'student_number',''));
  if v_email::text !~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$' then raise exception '邮箱格式不正确'; end if;
  if char_length(v_student_number) not between 1 and 40 then raise exception '学号格式不正确'; end if;
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
  if not public.valid_odyssey_answers(p_payload) then raise exception '请完整填写三个奥德赛计划，每项内容需在允许长度内'; end if;

  select id into v_number_id from public.students where student_number = v_student_number;
  select id into v_email_id from public.students where email = v_email;
  if v_number_id is not null and v_email_id is not null and v_number_id <> v_email_id then
    raise exception '该学号与邮箱分别属于不同档案，请核对后重试';
  end if;

  v_student_id := coalesce(v_number_id, v_email_id);
  if v_student_id is not null then
    select * into v_student from public.students where id = v_student_id for update;
    if v_student.student_number <> v_student_number or v_student.email <> v_email then
      raise exception '该学号或邮箱已绑定其他档案，请核对后重试';
    end if;
  else
    begin
      insert into public.students(student_number,email,name,major,year_level)
      values(v_student_number,v_email,btrim(p_payload->>'name'),btrim(p_payload->>'major'),p_payload->>'year_level')
      returning * into v_student;
    exception when unique_violation then
      select * into v_student from public.students where student_number = v_student_number and email = v_email for update;
      if not found then raise exception '该学号或邮箱已绑定其他档案，请核对后重试'; end if;
    end;
  end if;

  update public.students set
    name=btrim(p_payload->>'name'), major=btrim(p_payload->>'major'), year_level=left(btrim(p_payload->>'year_level'),40),
    consent_status='granted', consented_at=now(), deactivated_at=null
  where id=v_student.id;

  insert into public.onboarding_submissions(student_id,answers,form_version,submitted_at)
  values(v_student.id,p_payload-array['name','email','student_number'],left(coalesce(p_payload->>'form_version','3.2.0'),30),now())
  returning id into v_submission_id;

  insert into public.audit_logs(actor,action,entity_type,entity_id,details)
  values('student','open_onboarding_submitted','student',v_student.id::text,jsonb_build_object('submission_id',v_submission_id));
  return jsonb_build_object('ok',true,'student_id',v_student.id,'submission_id',v_submission_id);
end
$$;

create or replace function public.enforce_current_onboarding_version()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  new.form_version := '3.2.0';
  if not public.valid_odyssey_answers(new.answers) then
    raise exception '请完整填写三个奥德赛计划，每项内容需在允许长度内';
  end if;
  return new;
end
$$;

alter table public.onboarding_submissions alter column form_version set default '3.2.0';

revoke all on function public.submit_open_onboarding(jsonb) from public, authenticated;
grant execute on function public.submit_open_onboarding(jsonb) to anon;
revoke all on function public.claim_invite_and_submit_onboarding(text,jsonb) from public, anon, authenticated;

comment on function public.submit_open_onboarding(jsonb) is 'Validates open first-time onboarding, creates or reuses the exact student identity, and enqueues a new model version.';
