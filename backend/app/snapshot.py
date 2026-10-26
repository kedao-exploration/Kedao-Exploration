from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .config import get_settings
from .supabase import Supabase


TABLES = [
    "students", "student_invites", "onboarding_submissions", "survey_definitions", "survey_assignments",
    "survey_responses", "student_model_versions", "aggregate_reports", "activities", "activity_match_runs",
    "campaigns", "campaign_recipients", "audit_logs",
]


def main() -> None:
    settings = get_settings()
    db = Supabase(settings)
    snapshot_dir = settings.data_dir / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    target = snapshot_dir / f"kedao-{stamp}.jsonl.gz"
    with gzip.open(target, "wt", encoding="utf-8") as stream:
        for table in TABLES:
            for row in db.select(table):
                stream.write(json.dumps({"table": table, "row": row}, ensure_ascii=False, separators=(",", ":")) + "\n")
    cutoff = datetime.now(UTC) - timedelta(days=settings.snapshot_retention_days)
    for path in snapshot_dir.glob("kedao-*.jsonl.gz"):
        if datetime.fromtimestamp(path.stat().st_mtime, UTC) < cutoff:
            path.unlink()
    print(target)


if __name__ == "__main__":
    main()
