from argon2 import PasswordHasher

from app.security import LoginRateLimiter, safe_next_path, verify_password


def test_password_hash_verification():
    encoded = PasswordHasher().hash("123456")
    assert verify_password(encoded, "123456")
    assert not verify_password(encoded, "wrong")


def test_open_redirect_is_blocked():
    assert safe_next_path("//evil.example") == "/"
    assert safe_next_path("https://evil.example") == "/"
    assert safe_next_path("/students") == "/students"


def test_login_rate_limiter():
    limiter = LoginRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("ip")
    assert limiter.allow("ip")
    assert not limiter.allow("ip")
    limiter.clear("ip")
    assert limiter.allow("ip")
