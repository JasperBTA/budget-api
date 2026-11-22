from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from budget.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# Compared against when the user doesn't exist, so login takes the same time either way.
DUMMY_HASH = bcrypt.hashpw(b"timing-equalizer", bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode()
    if len(raw) > 72:  # bcrypt>=5 raises instead of truncating; register already rejects these
        return False
    return bcrypt.checkpw(raw, password_hash.encode())


def create_access_token(user_id: int) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires}, settings.jwt_secret, ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id, or None for any invalid/expired token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
