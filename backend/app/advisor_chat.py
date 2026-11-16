from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .llm import scrub_pii
from .supabase import Supabase


ATTACHMENT_FILENAME = "advisor-chat-context.json"
PROFILE_LIST_LIMIT = 1
ATTACHMENT_DETAIL_BUDGET_BYTES = 450_000


def _chunks(values: list[str], size: int = 50):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _atomic_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def _compact_evidence(items: Any, limit: int = PROFILE_LIST_LIMIT) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    compacted = []
    for item in items[:limit]:
        if not isinstance(item, dict) or not isinstance(item.get("statement"), str):
            continue
        compacted.append({
            "statement": item["statement"][:220],
            "evidence_refs": [str(ref)[:180] for ref in item.get("evidence_refs", [])[:1]],
        })
    return compacted


def _compact_profile(profile: Any) -> dict[str, Any] | None:
    if not isinstance(profile, dict):
        return None
    goals = profile.get("goals") if isinstance(profile.get("goals"), dict) else {}
    attention = []
    raw_attention = profile.get("advisor_attention") if isinstance(profile.get("advisor_attention"), list) else []
    for item in raw_attention[:PROFILE_LIST_LIMIT]:
        if isinstance(item, dict) and isinstance(item.get("note"), str):
            attention.append({
                "category": item.get("category"),
                "priority": item.get("priority"),
                "note": item["note"][:220],
                "evidence_refs": [str(ref)[:180] for ref in item.get("evidence_refs", [])[:1]],
            })
    return {
        "summary": str(profile.get("summary") or "")[:300],
        "current_state": _compact_evidence(profile.get("current_state")),
        "goals": {
            "long_term": _compact_evidence(goals.get("long_term")),
            "this_term": _compact_evidence(goals.get("this_term")),
            "next_30_days": _compact_evidence(goals.get("next_30_days")),
        },
        "interests": _compact_evidence(profile.get("interests")),
        "engagement_and_clubs": _compact_evidence(profile.get("engagement_and_clubs")),
        "skills_and_self_regulation": _compact_evidence(profile.get("skills_and_self_regulation")),
        "wellbeing_and_support_preferences": _compact_evidence(profile.get("wellbeing_and_support_preferences")),
        "constraints": _compact_evidence(profile.get("constraints")),
        "recommendation_profile": _compact_evidence(profile.get("recommendation_profile")),
        "advisor_attention": attention,
        "uncertainties": [
            str(item)[:220]
            for item in (profile.get("uncertainties") if isinstance(profile.get("uncertainties"), list) else [])[:PROFILE_LIST_LIMIT]
        ],
    }


def _summary_profile(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if not profile:
        return None
    return {
        "summary": profile["summary"],
        "goals": profile["goals"],
        "interests": profile["interests"],
        "constraints": profile["constraints"],
        "recommendation_profile": profile["recommendation_profile"],
        "advisor_attention": profile["advisor_attention"],
        "uncertainties": profile["uncertainties"],
    }


def build_advisor_chat_attachment(db: Supabase, data_dir: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Build the server-only, de-identified file attached to each advisor chat request."""
    students = db.select(
        "students",
        select="id,name,email,student_number,major,year_level,model_status,last_profile_input_at,current_model_version_id",
        params={"consent_status": "eq.granted", "deactivated_at": "is.null", "order": "updated_at.desc"},
    )
    version_ids = [row["current_model_version_id"] for row in students if row.get("current_model_version_id")]
    versions: dict[str, dict[str, Any]] = {}
    for batch in _chunks(version_ids):
        rows = db.select(
            "student_model_versions",
            select="id,profile,summary,generated_at,prompt_version",
            params={"id": f"in.({','.join(batch)})"},
        )
        versions.update({row["id"]: row for row in rows})

    identities: dict[str, dict[str, Any]] = {}
    context_students: list[dict[str, Any]] = []
    for student in students:
        student_ref = student["id"]
        identities[student_ref] = {
            "student_ref": student_ref,
            "name": student.get("name") or "未填写姓名",
            "email": student.get("email") or "",
            "student_number": student.get("student_number") or "",
            "major": student.get("major"),
            "year_level": student.get("year_level"),
        }
        version = versions.get(student.get("current_model_version_id", ""))
        profile = _compact_profile(scrub_pii(version.get("profile"))) if version else None
        context_students.append({
            "student_ref": student_ref,
            "major": student.get("major"),
            "year_level": student.get("year_level"),
            "model_status": student.get("model_status"),
            "last_profile_input_at": student.get("last_profile_input_at"),
            "profile_generated_at": version.get("generated_at") if version else None,
            "prompt_version": version.get("prompt_version") if version else None,
            "profile": profile,
        })

    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    attachment = {
        "attachment_type": "advisor_student_context",
        "schema_version": "1.0",
        "generated_at": generated_at,
        "privacy": "deidentified; names, emails and student numbers are resolved only after model output",
        "student_count": len(context_students),
        "modeled_count": sum(1 for row in context_students if row["profile"]),
        "detail_level": "compact",
        "students": context_students,
    }
    if len(json.dumps(attachment, ensure_ascii=False, separators=(",", ":")).encode()) > ATTACHMENT_DETAIL_BUDGET_BYTES:
        for row in context_students:
            row["profile"] = _summary_profile(row["profile"])
        attachment["detail_level"] = "summary"
    canonical = json.dumps(attachment, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    attachment["sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    _atomic_private_json(data_dir / ATTACHMENT_FILENAME, attachment)
    return attachment, identities


def deidentify_chat_text(value: str, identities: dict[str, dict[str, Any]]) -> str:
    """Replace known direct identifiers with the internal reference before LLM use."""
    replacements: list[tuple[str, str]] = []
    for student_ref, identity in identities.items():
        replacement = f"学生[{student_ref}]"
        for key in ("email", "student_number", "name"):
            token = str(identity.get(key) or "").strip()
            if token and (key != "name" or len(token) >= 2):
                replacements.append((token, replacement))
    result = value
    for token, replacement in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        result = re.sub(re.escape(token), replacement, result, flags=re.IGNORECASE)
    return str(scrub_pii(result))
