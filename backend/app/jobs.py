from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import Settings
from .llm import LLMService, PROMPT_VERSION, scrub_pii
from .supabase import Supabase


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def evidence_for_student(db: Supabase, student_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    onboarding = db.select(
        "onboarding_submissions", select="id,answers,submitted_at,form_version",
        params={"student_id": f"eq.{student_id}", "order": "submitted_at.asc"},
    )
    responses = db.select(
        "survey_responses", select="id,answers,submitted_at,survey_id",
        params={"student_id": f"eq.{student_id}", "order": "submitted_at.asc"},
    )
    evidence: list[dict[str, Any]] = []
    for item in onboarding:
        for key, value in item.get("answers", {}).items():
            evidence.append({"ref": f"onboarding:{item['id']}:{key}", "field": key, "value": scrub_pii(value), "recorded_at": item["submitted_at"]})
    for item in responses:
        for key, value in item.get("answers", {}).items():
            evidence.append({"ref": f"survey:{item['id']}:{key}", "field": key, "value": scrub_pii(value), "recorded_at": item["submitted_at"]})
    snapshot = {"onboarding_ids": [item["id"] for item in onboarding], "survey_response_ids": [item["id"] for item in responses]}
    return evidence, snapshot


def process_model_job(db: Supabase, llm: LLMService, job: dict[str, Any]) -> None:
    job_id, student_id = job["id"], job["student_id"]
    db.update("model_update_jobs", {"status": "processing", "locked_at": iso(utcnow()), "attempts": job.get("attempts", 0) + 1}, filters={"id": f"eq.{job_id}"})
    db.update("students", {"model_status": "processing"}, filters={"id": f"eq.{student_id}"})
    try:
        evidence, snapshot = evidence_for_student(db, student_id)
        if not evidence:
            raise RuntimeError("No profile evidence is available")
        canonical = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        input_hash = hashlib.sha256(canonical.encode()).hexdigest()
        existing = db.select("student_model_versions", params={"student_id": f"eq.{student_id}", "input_hash": f"eq.{input_hash}"}, limit=1)
        if existing:
            version_row = existing[0]
        else:
            previous = db.select("student_model_versions", select="version", params={"student_id": f"eq.{student_id}", "order": "version.desc"}, limit=1)
            next_version = (previous[0]["version"] if previous else 0) + 1
            model = llm.build_student_model(student_id, evidence)
            version_row = db.insert("student_model_versions", {
                "student_id": student_id, "version": next_version, "input_hash": input_hash,
                "profile": model.model_dump(), "summary": model.summary,
                "model_name": llm.settings.siliconflow_model, "prompt_version": PROMPT_VERSION, "source_snapshot": snapshot,
            })[0]
        db.update("students", {"current_model_version_id": version_row["id"], "model_status": "ready"}, filters={"id": f"eq.{student_id}"})
        db.update("model_update_jobs", {"status": "completed", "completed_at": iso(utcnow()), "last_error": None}, filters={"id": f"eq.{job_id}"})
    except Exception as exc:
        attempts = job.get("attempts", 0) + 1
        status = "failed" if attempts >= 5 else "pending"
        values = {"status": status, "last_error": str(exc)[:2000], "run_after": iso(utcnow() + timedelta(minutes=min(30, 2**attempts)))}
        db.update("model_update_jobs", values, filters={"id": f"eq.{job_id}"})
        db.update("students", {"model_status": "failed" if status == "failed" else "queued"}, filters={"id": f"eq.{student_id}"})


def process_pending_model_jobs(db: Supabase, llm: LLMService, limit: int = 10) -> int:
    jobs = db.select("model_update_jobs", params={"status": "eq.pending", "run_after": f"lte.{iso(utcnow())}", "order": "created_at.asc"}, limit=limit)
    for job in jobs:
        process_model_job(db, llm, job)
    return len(jobs)


def process_activity_run(db: Supabase, llm: LLMService, run: dict[str, Any]) -> None:
    run_id = run["id"]
    db.update("activity_match_runs", {"status": "processing", "started_at": iso(utcnow()), "attempts": run.get("attempts", 0) + 1}, filters={"id": f"eq.{run_id}"})
    try:
        activity = db.select("activities", params={"id": f"eq.{run['activity_id']}"}, limit=1)[0]
        students = db.select("students", select="id,current_model_version_id", params={"consent_status": "eq.granted", "deactivated_at": "is.null"})
        campaign = db.insert("campaigns", {"activity_id": activity["id"], "match_run_id": run_id, "name": f"{activity['title']} · 推送名单", "kind": "activity", "status": "review"})[0]
        recipients = []
        for student in students:
            if not student.get("current_model_version_id"):
                recipients.append({
                    "campaign_id": campaign["id"], "student_id": student["id"], "source": "llm", "included": False,
                    "recommendation": {
                        "include": False, "fit_score": 0, "interest_score": 0, "need_score": 0, "availability_score": 0,
                        "reasons": ["尚无可用画像，需 advisor 人工判断"], "evidence_refs": [], "caution": "student_model_missing",
                    },
                })
                continue
            rows = db.select("student_model_versions", select="profile", params={"id": f"eq.{student['current_model_version_id']}"}, limit=1)
            if not rows:
                recipients.append({
                    "campaign_id": campaign["id"], "student_id": student["id"], "source": "llm", "included": False,
                    "recommendation": {
                        "include": False, "fit_score": 0, "interest_score": 0, "need_score": 0, "availability_score": 0,
                        "reasons": ["画像版本不可用，需 advisor 人工判断"], "evidence_refs": [], "caution": "student_model_unavailable",
                    },
                })
                continue
            match = llm.match_activity(activity, student["id"], rows[0]["profile"])
            recipients.append({"campaign_id": campaign["id"], "student_id": student["id"], "recommendation": match.model_dump(), "source": "llm", "included": match.include})
        if recipients:
            db.insert("campaign_recipients", recipients, returning=False)
        db.update("activity_match_runs", {"status": "completed", "student_count": len(recipients), "completed_at": iso(utcnow())}, filters={"id": f"eq.{run_id}"})
        db.update("activities", {"status": "ready"}, filters={"id": f"eq.{activity['id']}"})
    except Exception as exc:
        db.update("activity_match_runs", {"status": "failed", "last_error": str(exc)[:2000]}, filters={"id": f"eq.{run_id}"})


def process_pending_activity_runs(db: Supabase, llm: LLMService, limit: int = 1) -> int:
    runs = db.select("activity_match_runs", params={"status": "eq.pending", "order": "created_at.asc"}, limit=limit)
    for run in runs:
        process_activity_run(db, llm, run)
    return len(runs)


def _walk_labels(value: Any, counter: Counter[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _walk_labels(item, counter)
    elif isinstance(value, dict):
        if isinstance(value.get("statement"), str):
            counter[value["statement"]] += 1
        else:
            for item in value.values():
                _walk_labels(item, counter)


def generate_aggregate_report(db: Supabase, llm: LLMService) -> dict[str, Any]:
    students = db.select("students", select="id,current_model_version_id", params={"consent_status": "eq.granted", "deactivated_at": "is.null"})
    profiles: list[dict[str, Any]] = []
    counter: Counter[str] = Counter()
    for student in students:
        if not student.get("current_model_version_id"):
            continue
        rows = db.select("student_model_versions", select="profile,generated_at", params={"id": f"eq.{student['current_model_version_id']}"}, limit=1)
        if rows:
            profile = rows[0]["profile"]
            _walk_labels(profile.get("goals", {}), counter)
            _walk_labels(profile.get("interests", []), counter)
            profiles.append({"student_ref": student["id"], "profile": profile})
    metrics = {"active_students": len(students), "modeled_students": len(profiles), "coverage_percent": round(100 * len(profiles) / max(1, len(students)), 1), "top_exact_signals": counter.most_common(30)}
    report = llm.build_aggregate_report(metrics, profiles)
    row = db.insert("aggregate_reports", {"report_date": utcnow().date().isoformat(), "source_snapshot": {"student_ids": [s["id"] for s in students]}, "deterministic_metrics": metrics, "report": report.model_dump(), "model_name": llm.settings.siliconflow_model, "prompt_version": "aggregate-v1"})[0]
    return row
