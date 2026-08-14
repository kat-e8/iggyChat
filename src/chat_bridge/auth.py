"""Mock user store, password hashing, and JWT issuance/verification.

No persistent DB -- users live in an in-memory dict for the process's
lifetime, seeded with the mock user implied by the frontend's reference
screenshots (test@angular-university.io / Angular123). Whether this carries
through to a later environment with real user storage is an open question,
not resolved here.
"""

from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import settings

_hasher = PasswordHasher()

_users: dict[str, str] = {}  # email -> argon2 hash


def _seed_mock_user() -> None:
    _users["test@angular-university.io"] = _hasher.hash("Angular123")


_seed_mock_user()


def create_user(email: str, password: str) -> None:
    if email in _users:
        raise ValueError("User already exists")
    _users[email] = _hasher.hash(password)


def authenticate_user(email: str, password: str) -> bool:
    hashed = _users.get(email)
    if hashed is None:
        return False
    try:
        _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False
    return True


def create_access_token(email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    return payload.get("sub")
