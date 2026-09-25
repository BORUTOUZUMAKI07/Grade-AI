from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, EmailAlreadyRegisteredError
from app.core.security import DUMMY_HASH, create_token, decode_token, hash_password, verify_password
from app.db.models import RefreshToken, User

# A refresh token used twice within this window is treated as a double request (for example two tabs), not theft.
REUSE_GRACE = timedelta(seconds=15)
_EXPIRED = "Your session has expired. Please sign in again."


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class AuthService:
    def __init__(self, db: Session):
        self._db = db

    def register(self, email: str, full_name: str, password: str) -> User:
        email = email.strip().lower()
        if self._db.scalar(select(User).where(User.email == email)):
            raise EmailAlreadyRegisteredError()
        # Register the ADMIN_EMAIL account yourself first: the address is not verified.
        is_admin = bool(settings.ADMIN_EMAIL) and email == settings.ADMIN_EMAIL.strip().lower()
        user = User(email=email, full_name=full_name.strip(), hashed_password=hash_password(password),
                    role="admin" if is_admin else "teacher")
        self._db.add(user)
        self._db.commit()
        return user

    def authenticate(self, email: str, password: str) -> User:
        user = self._db.scalar(select(User).where(User.email == email.strip().lower()))
        valid = verify_password(password, user.hashed_password if user else DUMMY_HASH)
        if not user or not valid or not user.is_active:
            raise AuthenticationError("Incorrect email or password.")
        return user

    def get(self, user_id: int) -> User | None:
        return self._db.get(User, user_id)

    @staticmethod
    def access_token(user: User) -> str:
        return create_token(user.id, user.role, "access", timedelta(minutes=settings.ACCESS_TOKEN_MINUTES))

    def issue_refresh(self, user: User) -> str:
        jti, life = uuid4().hex, timedelta(days=settings.REFRESH_TOKEN_DAYS)
        self._db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=datetime.now(timezone.utc) + life))
        self._db.commit()
        return create_token(user.id, user.role, "refresh", life, jti=jti)

    def rotate_refresh(self, token: str) -> tuple[User, str]:
        """Exchange a refresh token for a new one. The old one stops working immediately."""
        try:
            claims = decode_token(token, "refresh")
        except jwt.PyJWTError:
            raise AuthenticationError(_EXPIRED)
        row = self._db.scalar(select(RefreshToken).where(RefreshToken.jti == claims.get("jti")))
        if row is None:
            raise AuthenticationError(_EXPIRED)
        now = datetime.now(timezone.utc)
        if row.revoked_at is not None:
            if now - _aware(row.revoked_at) > REUSE_GRACE:
                self.revoke_all(row.user_id)  # an old token came back: assume it was stolen, sign out everywhere
            raise AuthenticationError(_EXPIRED)
        user = self.get(row.user_id)
        row.revoked_at = now
        self._db.commit()
        if user is None or not user.is_active:
            raise AuthenticationError(_EXPIRED)
        return user, self.issue_refresh(user)

    def revoke(self, token: str) -> None:
        try:
            jti = decode_token(token, "refresh").get("jti")
        except jwt.PyJWTError:
            return
        self._db.execute(update(RefreshToken).where(RefreshToken.jti == jti, RefreshToken.revoked_at.is_(None))
                         .values(revoked_at=datetime.now(timezone.utc)))
        self._db.commit()

    def revoke_all(self, user_id: int) -> None:
        self._db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
                         .values(revoked_at=datetime.now(timezone.utc)))
        self._db.commit()
