import secrets
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


hasher = PasswordHasher()


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerifyMismatchError, ValueError):
        return False


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def safe_next_path(value: str | None) -> str:
    return value if value and value.startswith("/") and not value.startswith("//") else "/"


class LoginRateLimiter:
    def __init__(self, limit: int = 6, window_seconds: int = 600):
        self.limit = limit
        self.window_seconds = window_seconds
        self.attempts: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, identity: str) -> bool:
        now = time.monotonic()
        bucket = self.attempts[identity]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True

    def clear(self, identity: str) -> None:
        self.attempts.pop(identity, None)
