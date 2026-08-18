"""Password hashing and JWT issuance/verification.

User accounts are persisted in user_store.py's SQLite table -- not an
in-memory dict, which lost every signed-up account on every process
restart (see Deployment/Phase7_Cost_Diagnostics_And_Usage_Guardrails.pdf).

Signup is closed: there is no HTTP endpoint that creates accounts.
Accounts are provisioned by the operator via manage_users.py (`docker exec`
into the container and run it), on top of the tailnet-only network access
this app already has. See Deployment/Phase8_*.pdf for why, and for JWT
revocation's one known limitation (removing a user does not invalidate an
already-issued cookie for it -- tokens are checked by signature/expiry
only, not by re-querying the user store on every request).
"""

from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from . import user_store
from .config import settings

_hasher = PasswordHasher()

# Idempotent: a no-op once the row exists, including after the operator has
# added real accounts -- safe to call on every startup.
user_store.seed_mock_user_if_absent(_hasher.hash("Angular123"))


def authenticate_user(email: str, password: str) -> bool:
    hashed = user_store.get_password_hash(email)
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
