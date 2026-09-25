from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()
# Verified against when the email is unknown, so login timing does not reveal which emails exist.
DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(user_id: int, role: str, kind: str, lifetime: timedelta, jti: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user_id), "role": role, "type": kind, "iat": now, "exp": now + lifetime}
    if jti:
        claims["jti"] = jti
    return jwt.encode(claims, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str, kind: str) -> dict:
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    if claims.get("type") != kind:
        raise jwt.InvalidTokenError("wrong token type")
    return claims
