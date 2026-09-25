from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.rate_limit import RateLimiter
from app.db.models import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.services.auth_service import AuthService

router = APIRouter()
COOKIE = "refresh_token"
COOKIE_PATH = f"{settings.API_V1_STR}/auth"

# Failed logins: 5 per email+IP and 20 per IP every 5 minutes. Sign-ups: 10 per IP per hour.
# Behind a reverse proxy request.client is the proxy; configure trusted forwarded headers before relying on the IP.
_login_pair = RateLimiter(5, 300)
_login_ip = RateLimiter(20, 300)
_register_ip = RateLimiter(10, 3600)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _start_session(svc: AuthService, user: User, response: Response) -> dict:
    refresh = svc.issue_refresh(user)
    # The refresh token lives in an httpOnly cookie so page scripts (and any XSS) cannot read it.
    response.set_cookie(COOKIE, refresh, max_age=settings.REFRESH_TOKEN_DAYS * 86400, httponly=True,
                        samesite="lax", secure=settings.ENVIRONMENT == "production", path=COOKIE_PATH)
    return {"access_token": svc.access_token(user), "user": user}


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = _ip(request)
    _register_ip.check(ip)
    _register_ip.hit(ip)
    svc = AuthService(db)
    return _start_session(svc, svc.register(payload.email, payload.full_name, payload.password), response)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip, pair = _ip(request), f"{_ip(request)}:{payload.email.strip().lower()}"
    _login_ip.check(ip)
    _login_pair.check(pair)
    svc = AuthService(db)
    try:
        user = svc.authenticate(payload.email, payload.password)
    except AuthenticationError:
        _login_ip.hit(ip)
        _login_pair.hit(pair)
        raise
    _login_pair.reset(pair)
    return _start_session(svc, user, response)


@router.post("/refresh", response_model=AuthResponse)
def refresh(response: Response, refresh_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if not refresh_token:
        raise AuthenticationError("Not signed in.")
    svc = AuthService(db)
    user, new_refresh = svc.rotate_refresh(refresh_token)
    response.set_cookie(COOKIE, new_refresh, max_age=settings.REFRESH_TOKEN_DAYS * 86400, httponly=True,
                        samesite="lax", secure=settings.ENVIRONMENT == "production", path=COOKIE_PATH)
    return {"access_token": svc.access_token(user), "user": user}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, refresh_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if refresh_token:
        AuthService(db).revoke(refresh_token)
    response.delete_cookie(COOKIE, path=COOKIE_PATH)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
