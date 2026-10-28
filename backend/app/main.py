from __future__ import annotations

import hashlib
import json
import secrets
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .models import SurveySchema
from .security import LoginRateLimiter, new_csrf_token, safe_next_path, verify_password
from .supabase import Supabase, SupabaseError


BASE_DIR = Path(__file__).resolve().parent
settings = get_settings()
db = Supabase(settings)
app = FastAPI(title="科道书院学生画像后台", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret.get_secret_value(),
    same_site="strict",
    https_only=settings.cookie_secure,
    max_age=8 * 60 * 60,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
rate_limiter = LoginRateLimiter()
SHANGHAI = ZoneInfo("Asia/Shanghai")


def signed_in(request: Request) -> bool:
    return request.session.get("advisor") == settings.advisor_username


def page_context(request: Request, **values):
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = new_csrf_token()
    return {"request": request, "advisor": request.session.get("advisor"), "csrf_token": request.session["csrf_token"], **values}


def require_page_login(request: Request):
    if not signed_in(request):
        return RedirectResponse(f"/login?next={quote(request.url.path)}", status_code=303)
    return None


def require_csrf(request: Request, token: str) -> None:
    expected = request.session.get("csrf_token")
    if not expected or not secrets.compare_digest(expected, token):
        raise HTTPException(403, "CSRF validation failed")


def require_campaign_editable(campaign_id: str) -> dict:
    rows = db.select("campaigns", select="id,status", params={"id": f"eq.{campaign_id}"}, limit=1)
    if not rows:
        raise HTTPException(404, "名单不存在")
    if rows[0]["status"] in {"confirmed", "exported"}:
        raise HTTPException(409, "最终名单已确认，不能再修改")
    return rows[0]


@app.get("/health")
def health():
    return {"ok": True, "service": "kedao-discover-backend"}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    if signed_in(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", page_context(request, next=safe_next_path(next), error=None))


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: Annotated[str, Form()], password: Annotated[str, Form()], next: Annotated[str, Form()] = "/"):
    identity = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(identity):
        return templates.TemplateResponse("login.html", page_context(request, next=safe_next_path(next), error="尝试次数过多，请十分钟后再试。"), status_code=429)
    valid = username == settings.advisor_username and verify_password(settings.advisor_password_hash.get_secret_value(), password)
    if not valid:
        return templates.TemplateResponse("login.html", page_context(request, next=safe_next_path(next), error="用户名或密码不正确。"), status_code=401)
    rate_limiter.clear(identity)
    request.session.clear()
    request.session.update({"advisor": settings.advisor_username, "csrf_token": new_csrf_token()})
    return RedirectResponse(safe_next_path(next), status_code=303)


@app.post("/logout")
def logout(request: Request, csrf_token: Annotated[str, Form()]):
    require_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    if redirect := require_page_login(request): return redirect
    students = db.select("students", select="id,model_status,consent_status,last_profile_input_at", params={"deactivated_at": "is.null"})
    report_rows = db.select("aggregate_reports", params={"order": "generated_at.desc"}, limit=1)
    activities = db.select("activities", params={"order": "start_at.asc", "start_at": f"gte.{datetime.now(SHANGHAI).isoformat()}"}, limit=5)
    metrics = {
        "students": len(students),
        "ready": sum(1 for row in students if row["model_status"] == "ready"),
        "queued": sum(1 for row in students if row["model_status"] in {"queued", "processing"}),
        "failed": sum(1 for row in students if row["model_status"] == "failed"),
    }
    return templates.TemplateResponse("dashboard.html", page_context(request, metrics=metrics, report=report_rows[0] if report_rows else None, activities=activities))


def render_student_list(request: Request, q: str = "", student_result: dict | None = None, error: str | None = None):
    params = {"order": "updated_at.desc"}
    if q:
        escaped = q.replace("%", "")[:80]
        params["or"] = f"(name.ilike.*{escaped}*,email.ilike.*{escaped}*,student_number.ilike.*{escaped}*)"
    students = db.select("students", select="id,name,email,student_number,major,year_level,model_status,consent_status,last_profile_input_at", params=params)
    return templates.TemplateResponse("students.html", page_context(request, students=students, q=q, student_result=student_result, error=error))


@app.get("/students", response_class=HTMLResponse)
def student_list(request: Request, q: str = ""):
    if redirect := require_page_login(request): return redirect
    return render_student_list(request, q=q)


@app.post("/students", response_class=HTMLResponse)
def create_student_record(
    request: Request,
    csrf_token: Annotated[str, Form()],
    student_number: Annotated[str, Form()],
    email: Annotated[str, Form()],
    name: Annotated[str, Form()] = "",
):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    student_number = student_number.strip()
    email = email.strip().lower()
    name = name.strip()
    if not student_number or len(student_number) > 40:
        return render_student_list(request, error="请输入有效学号（不超过 40 个字符）。")
    if "@" not in email or len(email) > 320:
        return render_student_list(request, error="请输入有效邮箱。")
    try:
        by_number = db.select("students", params={"student_number": f"eq.{student_number}"}, limit=1)
        by_email = db.select("students", params={"email": f"eq.{email}"}, limit=1)
        matches = by_number or by_email
        if by_number and by_email and by_number[0]["id"] != by_email[0]["id"]:
            return render_student_list(request, error="该学号与邮箱分别属于不同档案，请先核对信息。")
        if matches:
            student = matches[0]
            if student["student_number"] != student_number or student["email"].lower() != email:
                return render_student_list(request, error="该学号或邮箱已绑定其他学生，请检查后再提交。")
            db.update("students", {"name": name or student.get("name")}, filters={"id": f"eq.{student['id']}"})
        else:
            student = db.insert("students", {"student_number": student_number, "email": email, "name": name or None})[0]
        student_result = {
            "name": name or student.get("name") or "待首次填写",
            "student_number": student_number,
            "email": email,
            "url": f"{settings.student_site_url.rstrip('/')}/#/onboarding",
        }
        db.insert("audit_logs", {"actor": settings.advisor_username, "action": "student_record_saved", "entity_type": "student", "entity_id": student["id"]}, returning=False)
        return render_student_list(request, student_result=student_result)
    except SupabaseError as exc:
        return render_student_list(request, error=f"保存失败：{exc}")


@app.get("/students/{student_id}", response_class=HTMLResponse)
def student_detail(request: Request, student_id: str):
    if redirect := require_page_login(request): return redirect
    rows = db.select("students", params={"id": f"eq.{student_id}"}, limit=1)
    if not rows: raise HTTPException(404)
    models = db.select("student_model_versions", params={"student_id": f"eq.{student_id}", "order": "version.desc"})
    onboarding = db.select("onboarding_submissions", params={"student_id": f"eq.{student_id}", "order": "submitted_at.desc"})
    responses = db.select("survey_responses", params={"student_id": f"eq.{student_id}", "order": "submitted_at.desc"})
    return templates.TemplateResponse("student_detail.html", page_context(request, student=rows[0], models=models, onboarding=onboarding, responses=responses))


@app.post("/students/{student_id}/retry")
def retry_model(request: Request, student_id: str, csrf_token: Annotated[str, Form()]):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    active = db.select("model_update_jobs", params={"student_id": f"eq.{student_id}", "status": "in.(pending,processing)"}, limit=1)
    if not active: db.insert("model_update_jobs", {"student_id": student_id, "reason": "advisor_retry"}, returning=False)
    db.update("students", {"model_status": "queued"}, filters={"id": f"eq.{student_id}"})
    return RedirectResponse(f"/students/{student_id}", status_code=303)


@app.post("/students/{student_id}/withdraw")
def withdraw_student(request: Request, student_id: str, csrf_token: Annotated[str, Form()]):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    db.update("students", {"consent_status": "withdrawn", "deactivated_at": datetime.now(SHANGHAI).isoformat()}, filters={"id": f"eq.{student_id}"})
    db.insert("audit_logs", {"actor": settings.advisor_username, "action": "consent_withdrawn", "entity_type": "student", "entity_id": student_id}, returning=False)
    return RedirectResponse(f"/students/{student_id}", status_code=303)


@app.get("/activities", response_class=HTMLResponse)
def activities_page(request: Request):
    if redirect := require_page_login(request): return redirect
    activities = db.select("activities", params={"order": "start_at.desc"})
    campaigns = db.select("campaigns", select="id,name,status,activity_id,created_at", params={"kind": "eq.activity", "order": "created_at.desc"})
    return templates.TemplateResponse("activities.html", page_context(request, activities=activities, campaigns=campaigns))


@app.post("/activities")
async def create_activity(
    request: Request, csrf_token: Annotated[str, Form()], title: Annotated[str, Form()], description: Annotated[str, Form()],
    start_at: Annotated[str, Form()], end_at: Annotated[str, Form()], location: Annotated[str, Form()] = "",
    tags: Annotated[str, Form()] = "", capacity: Annotated[str, Form()] = "", poster: UploadFile | None = File(None),
):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    start = datetime.fromisoformat(start_at).replace(tzinfo=SHANGHAI)
    end = datetime.fromisoformat(end_at).replace(tzinfo=SHANGHAI)
    row = db.insert("activities", {"title": title.strip(), "description": description.strip(), "start_at": start.isoformat(), "end_at": end.isoformat(), "location": location.strip() or None, "tags": [x.strip() for x in tags.split(",") if x.strip()], "capacity": int(capacity) if capacity else None})[0]
    if poster and poster.filename:
        suffix = Path(poster.filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}: raise HTTPException(400, "海报仅支持 JPG、PNG 或 WebP")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await poster.read()); path = Path(tmp.name)
        try:
            object_path = f"{row['id']}/poster{suffix}"
            url = db.upload("activity-posters", object_path, path, poster.content_type or "image/jpeg")
            db.update("activities", {"poster_path": object_path, "poster_url": url}, filters={"id": f"eq.{row['id']}"})
        finally:
            path.unlink(missing_ok=True)
    return RedirectResponse("/activities", status_code=303)


@app.post("/activities/{activity_id}/match")
def match_activity(request: Request, activity_id: str, csrf_token: Annotated[str, Form()]):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    db.insert("activity_match_runs", {"activity_id": activity_id}, returning=False)
    db.update("activities", {"status": "matching"}, filters={"id": f"eq.{activity_id}"})
    return RedirectResponse("/activities", status_code=303)


@app.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_page(request: Request, campaign_id: str):
    if redirect := require_page_login(request): return redirect
    campaigns = db.select("campaigns", params={"id": f"eq.{campaign_id}"}, limit=1)
    if not campaigns: raise HTTPException(404)
    recipients = db.select("campaign_recipients", select="*,student:students(id,name,email,student_number,major)", params={"campaign_id": f"eq.{campaign_id}", "order": "included.desc,created_at.asc"})
    candidates = db.select("students", select="id,name,email,student_number,major", params={"consent_status": "eq.granted", "deactivated_at": "is.null", "order": "name.asc"})
    return templates.TemplateResponse("campaign.html", page_context(request, campaign=campaigns[0], recipients=recipients, candidates=candidates))


@app.post("/campaigns/{campaign_id}/recipients/{recipient_id}")
def update_recipient(request: Request, campaign_id: str, recipient_id: str, csrf_token: Annotated[str, Form()], included: Annotated[str, Form()] = "false", advisor_note: Annotated[str, Form()] = ""):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    require_campaign_editable(campaign_id)
    db.update("campaign_recipients", {"included": included == "true", "advisor_note": advisor_note[:1000]}, filters={"id": f"eq.{recipient_id}", "campaign_id": f"eq.{campaign_id}"})
    db.insert("audit_logs", {"actor": settings.advisor_username, "action": "campaign_recipient_updated", "entity_type": "campaign", "entity_id": campaign_id, "details": {"recipient_id": recipient_id, "included": included == "true", "reason": advisor_note[:1000]}}, returning=False)
    return RedirectResponse(f"/campaigns/{campaign_id}", status_code=303)


@app.post("/campaigns/{campaign_id}/recipients")
def add_recipient(request: Request, campaign_id: str, student_id: Annotated[str, Form()], csrf_token: Annotated[str, Form()]):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    require_campaign_editable(campaign_id)
    db.upsert("campaign_recipients", {"campaign_id": campaign_id, "student_id": student_id, "source": "advisor", "included": True, "advisor_note": "advisor 手动加入", "recommendation": {"reasons": ["advisor 手动加入"]}}, on_conflict="campaign_id,student_id")
    db.insert("audit_logs", {"actor": settings.advisor_username, "action": "campaign_recipient_added", "entity_type": "campaign", "entity_id": campaign_id, "details": {"student_id": student_id, "reason": "advisor 手动加入"}}, returning=False)
    return RedirectResponse(f"/campaigns/{campaign_id}", status_code=303)


@app.post("/campaigns/{campaign_id}/confirm")
def confirm_campaign(request: Request, campaign_id: str, csrf_token: Annotated[str, Form()]):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    require_campaign_editable(campaign_id)
    db.update("campaigns", {"status": "confirmed", "confirmed_at": datetime.now(SHANGHAI).isoformat()}, filters={"id": f"eq.{campaign_id}"})
    db.insert("audit_logs", {"actor": settings.advisor_username, "action": "campaign_confirmed", "entity_type": "campaign", "entity_id": campaign_id}, returning=False)
    return RedirectResponse(f"/campaigns/{campaign_id}", status_code=303)


@app.get("/campaigns/{campaign_id}/final", response_class=HTMLResponse)
def final_campaign(request: Request, campaign_id: str):
    if redirect := require_page_login(request): return redirect
    campaign = db.select("campaigns", select="status", params={"id": f"eq.{campaign_id}"}, limit=1)
    if not campaign or campaign[0]["status"] not in {"confirmed", "exported"}:
        raise HTTPException(409, "请先确认最终名单")
    rows = db.select("campaign_recipients", select="student:students(name,email,student_number,major),advisor_note", params={"campaign_id": f"eq.{campaign_id}", "included": "eq.true"})
    return templates.TemplateResponse("campaign_final.html", page_context(request, campaign_id=campaign_id, rows=rows))


@app.get("/surveys", response_class=HTMLResponse)
def surveys_page(request: Request):
    if redirect := require_page_login(request): return redirect
    surveys = db.select("survey_definitions", params={"order": "created_at.desc"})
    campaigns = db.select("campaigns", select="id,name,status", params={"status": "in.(confirmed,exported)", "order": "created_at.desc"})
    students = db.select("students", select="id,name,email,student_number", params={"consent_status": "eq.granted", "deactivated_at": "is.null", "order": "name.asc"})
    return templates.TemplateResponse("surveys.html", page_context(request, surveys=surveys, campaigns=campaigns, students=students, validation_error=None))


@app.post("/surveys")
def create_survey(request: Request, csrf_token: Annotated[str, Form()], title: Annotated[str, Form()], description: Annotated[str, Form()] = "", schema_definition: Annotated[str, Form(alias="schema_json")] = ""):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    try:
        schema = SurveySchema.model_validate_json(schema_definition)
    except ValidationError as exc:
        raise HTTPException(400, f"问卷定义不合法：{exc}") from exc
    db.insert("survey_definitions", {"title": title.strip(), "description": description.strip() or None, "schema": schema.model_dump(by_alias=True)})
    return RedirectResponse("/surveys", status_code=303)


@app.post("/surveys/{survey_id}/publish")
def publish_survey(request: Request, survey_id: str, csrf_token: Annotated[str, Form()]):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    db.update("survey_definitions", {"status": "published", "published_at": datetime.now(SHANGHAI).isoformat()}, filters={"id": f"eq.{survey_id}", "status": "eq.draft"})
    return RedirectResponse("/surveys", status_code=303)


@app.post("/surveys/{survey_id}/assign", response_class=HTMLResponse)
def assign_survey(request: Request, survey_id: str, csrf_token: Annotated[str, Form()], campaign_id: Annotated[str, Form()] = "", student_ids: Annotated[list[str] | None, Form()] = None):
    if redirect := require_page_login(request): return redirect
    require_csrf(request, csrf_token)
    ids = set(student_ids or [])
    if campaign_id:
        rows = db.select("campaign_recipients", select="student_id", params={"campaign_id": f"eq.{campaign_id}", "included": "eq.true"})
        ids.update(row["student_id"] for row in rows)
    if not ids: raise HTTPException(400, "请选择至少一名学生或已确认名单")
    links = []
    for student_id in sorted(ids):
        token = "QS-" + secrets.token_urlsafe(15).replace("_", "A").replace("-", "B").upper()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        try:
            db.insert("survey_assignments", {"survey_id": survey_id, "student_id": student_id, "token_hash": token_hash}, returning=False)
            student = db.select("students", select="name,email,student_number", params={"id": f"eq.{student_id}"}, limit=1)[0]
            links.append({**student, "url": f"{settings.student_site_url.rstrip('/')}/#/survey?token={quote(token)}"})
        except SupabaseError as exc:
            if "duplicate" not in str(exc).lower(): raise
    return templates.TemplateResponse("survey_links.html", page_context(request, survey_id=survey_id, links=links))
