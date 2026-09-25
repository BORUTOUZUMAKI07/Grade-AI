import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, NotFoundError, PermissionDeniedError
from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise AuthenticationError("Not authenticated.")
    try:
        claims = decode_token(creds.credentials, "access")
        user = db.get(User, int(claims["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise AuthenticationError("Your session has expired. Please sign in again.")
    if user is None or not user.is_active:
        raise AuthenticationError("Your session has expired. Please sign in again.")
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError()
        return user
    return checker


staff_only = require_roles("teacher", "admin")


def owned_or_404(db: Session, model, obj_id: int, user: User, what: str = "Item"):
    """Fetch a row that belongs to `user`; someone else's row looks exactly like a missing one."""
    obj = db.get(model, obj_id)
    if obj is None or obj.owner_id != user.id:
        raise NotFoundError(what)
    return obj
