"""Complete a server .env without printing secrets.

The existing file is expected to contain the Supabase values copied from the
local, untracked venv.env. Existing values (including a future SiliconFlow
key) are preserved.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from argon2 import PasswordHasher


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> None:
    existing = parse_env(ENV_PATH.read_text(encoding="utf-8")) if ENV_PATH.exists() else {}
    api_key_alias = existing.pop("API_KEY", "")
    if not existing.get("SILICONFLOW_API_KEY"):
        existing["SILICONFLOW_API_KEY"] = api_key_alias
    existing.setdefault("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    existing.setdefault("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
    existing.setdefault("SESSION_SECRET", secrets.token_urlsafe(48))
    existing.setdefault("ADVISOR_USERNAME", "kedao_college")
    existing.setdefault("ADVISOR_PASSWORD_HASH", PasswordHasher().hash("123456"))
    existing.setdefault(
        "STUDENT_SITE_URL",
        "https://kedao-exploration.github.io/Kedao-Exploration/",
    )
    existing.setdefault("DATA_DIR", str(ENV_PATH.parent / "data"))
    existing.setdefault("COOKIE_SECURE", "false")

    ordered = "\n".join(f"{key}={value}" for key, value in existing.items()) + "\n"
    ENV_PATH.write_text(ordered, encoding="utf-8")
    ENV_PATH.chmod(0o600)
    print(f"Configured {ENV_PATH} with {len(existing)} settings; secret values were not displayed.")


if __name__ == "__main__":
    main()
