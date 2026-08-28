"""Reusable JWT auth for any FastAPI app.

Unlike messenger/auth.py (which is hardwired to one User model), this module is
configurable: bind it to *your* User model and DB session, and you get hashing,
tokens, a `get_current_user` dependency, plus a ready-made `/api/auth/*` router
(register / login / refresh / me).

    from ayka.auth import JwtAuth, build_auth_router
    auth = JwtAuth(User, database.get_db, secret_env="NOTES_SECRET")
    app.include_router(build_auth_router(auth))
"""
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt as jose_jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, Field

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)
_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class JwtAuth:
    def __init__(
        self,
        user_model,
        get_db: Callable,
        *,
        issuer: str = "ayka-app",
        secret_env: str = "APP_SECRET",
        secret_file: Optional[str] = None,
        access_hours: int = 24,
        refresh_days: int = 30,
    ):
        self.User = user_model
        self._get_db = get_db
        self.issuer = issuer
        self.secret_env = secret_env
        self.secret_file = secret_file
        self.access_hours = access_hours
        self.refresh_days = refresh_days
        self._secret: Optional[str] = None

    # ---- secrets -----------------------------------------------------------
    @property
    def secret(self) -> str:
        if self._secret:
            return self._secret
        env = os.environ.get(self.secret_env)
        if env:
            self._secret = env
            return env
        if self.secret_file:
            try:
                if os.path.isfile(self.secret_file):
                    val = open(self.secret_file, "r", encoding="utf-8").read().strip()
                    if val:
                        self._secret = val
                        return val
                val = os.urandom(32).hex()
                os.makedirs(os.path.dirname(os.path.abspath(self.secret_file)), exist_ok=True)
                with open(self.secret_file, "w", encoding="utf-8") as f:
                    f.write(val)
                self._secret = val
                return val
            except Exception:
                pass
        val = os.urandom(32).hex()
        self._secret = val
        return val

    # ---- passwords ----------------------------------------------------------
    @staticmethod
    def hash_password(password: str) -> str:
        return _pwd_context.hash(password)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        try:
            return _pwd_context.verify(plain, hashed)
        except ValueError:
            return False

    # ---- tokens ---------------------------------------------------------------
    def encode(self, payload: dict, expires: datetime) -> str:
        payload = dict(payload)
        payload.update({"exp": expires, "iss": self.issuer})
        return jose_jwt.encode(payload, self.secret, algorithm=ALGORITHM)

    def create_token(self, user_id: int) -> str:
        return self.encode(
            {"sub": str(user_id)},
            datetime.now(timezone.utc) + timedelta(hours=self.access_hours),
        )

    def create_refresh(self, user_id: int) -> str:
        return self.encode(
            {"sub": str(user_id), "type": "refresh"},
            datetime.now(timezone.utc) + timedelta(days=self.refresh_days),
        )

    def decode_token(self, token: str, *, refresh: bool = False) -> Optional[dict]:
        try:
            payload = jose_jwt.decode(
                token, self.secret, algorithms=[ALGORITHM],
                options={"require_exp": True}, issuer=self.issuer,
            )
        except JWTError:
            return None
        if refresh and payload.get("type") != "refresh":
            return None
        return payload

    # ---- /api/auth router ---------------------------------------------------------
    def build_router(self) -> APIRouter:
        return build_auth_router(self)

    def _safe_payload(self, user) -> dict:
        data = {
            "id": user.id,
            "username": user.username,
            "display_name": getattr(user, "display_name", user.username),
            "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
        }
        for field in ("email", "is_admin", "is_banned"):
            if hasattr(user, field):
                data[field] = getattr(user, field)
        return data


def get_current_user_dependency(auth: JwtAuth):
    """Return a ready-to-use FastAPI dependency bound to auth + the app's get_db."""

    def _get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer),
        db=Depends(auth._get_db),
    ):
        if credentials is None:
            raise HTTPException(401, "Not authenticated")
        payload = auth.decode_token(credentials.credentials)
        if payload is None:
            raise HTTPException(401, "Invalid or expired token")
        user = db.query(auth.User).filter(auth.User.id == int(payload["sub"])).first()
        if user is None:
            raise HTTPException(401, "User not found")
        return user

    return _get_current_user


def build_auth_router(auth: JwtAuth) -> APIRouter:
    """POST /api/auth/register, /login, /refresh, GET /me."""

    router = APIRouter(prefix="/api/auth", tags=["auth"])

    class RegisterReq(BaseModel):
        username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_\-\.]+$")
        password: str = Field(min_length=8, max_length=128)
        display_name: Optional[str] = Field(default=None, max_length=64)
        email: Optional[str] = Field(default=None, max_length=128)

    class LoginReq(BaseModel):
        username: str
        password: str

    class TokenOut(BaseModel):
        access_token: str
        refresh_token: str
        token_type: str = "bearer"

    def _tokens(user) -> dict:
        return {
            "access_token": auth.create_token(user.id),
            "refresh_token": auth.create_refresh(user.id),
            "token_type": "bearer",
        }

    @router.post("/register", response_model=TokenOut, status_code=201)
    def _register(req: RegisterReq, db=Depends(auth._get_db)):
        existing = db.query(auth.User).filter(auth.User.username == req.username).first()
        if existing:
            raise HTTPException(409, "Username already taken")
        user = auth.User(
            username=req.username,
            password_hash=auth.hash_password(req.password),
            display_name=req.display_name or req.username,
            email=req.email,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return _tokens(user)

    @router.post("/login", response_model=TokenOut)
    def _login(req: LoginReq, db=Depends(auth._get_db)):
        user = db.query(auth.User).filter(auth.User.username == req.username).first()
        if user is None or not auth.verify_password(req.password, user.password_hash):
            raise HTTPException(401, "Invalid credentials")
        if getattr(user, "is_banned", False):
            raise HTTPException(403, "Account banned")
        return _tokens(user)

    @router.post("/refresh", response_model=TokenOut)
    def _refresh(req: dict, db=Depends(auth._get_db)):
        payload = auth.decode_token(req.get("refresh_token", ""), refresh=True)
        if payload is None:
            raise HTTPException(401, "Invalid refresh token")
        user = db.query(auth.User).filter(auth.User.id == int(payload["sub"])).first()
        if user is None:
            raise HTTPException(401, "User not found")
        return _tokens(user)

    @router.get("/me")
    def _me(current_user=Depends(get_current_user_dependency(auth))):
        return auth._safe_payload(current_user)

    return router


__all__ = ["JwtAuth", "build_auth_router", "get_current_user_dependency"]