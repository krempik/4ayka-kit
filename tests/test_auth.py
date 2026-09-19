"""Tests for ayka.auth: secret handling, password hashing, tokens, /api/auth router."""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Boolean, Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from ayka.auth import JwtAuth, build_auth_router

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    display_name = Column(String(128), nullable=False, default="")
    email = Column(String(128), nullable=True)
    password_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)


@pytest.fixture
def user_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session
    engine.dispose()


@pytest.fixture
def app_client(user_db, tmp_path):
    def get_db():
        db = user_db()
        try:
            yield db
        finally:
            db.close()

    auth = JwtAuth(User, get_db, issuer="test", secret_env="TEST_AUTH_SECRET", secret_file=str(tmp_path / ".secret_key"))
    app = FastAPI()
    app.include_router(build_auth_router(auth))
    return TestClient(app)


# ---------- secrets ----------

def test_secret_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_AUTH_SECRET", "env-secret-value")
    auth = JwtAuth(User, lambda: None, secret_env="TEST_AUTH_SECRET", secret_file=str(tmp_path / ".secret_key"))
    assert auth.secret == "env-secret-value"
    # env wins: file is never touched
    assert not (tmp_path / ".secret_key").exists()


def test_secret_persisted_across_instances(tmp_path):
    path = str(tmp_path / ".secret_key")
    a = JwtAuth(User, lambda: None, secret_env="NOPE", secret_file=path)
    first = a.secret
    assert (tmp_path / ".secret_key").exists()
    b = JwtAuth(User, lambda: None, secret_env="NOPE", secret_file=path)
    assert b.secret == first


def test_secret_unwritable_raises(tmp_path):
    blocker = tmp_path / "afile"
    blocker.write_text("x")
    path = str(blocker / "secret")
    auth = JwtAuth(User, lambda: None, secret_env="NOPE", secret_file=path)
    with pytest.raises(RuntimeError):
        auth.secret


def test_secret_ephemeral_without_file_env():
    auth = JwtAuth(User, lambda: None, secret_env="NOPE_MISSING")
    s1 = auth.secret
    s2 = auth.secret
    assert len(s1) == 64 and s1 == s2  # cached within the instance


# ---------- passwords ----------

def test_password_roundtrip():
    h = JwtAuth.hash_password("secret123")
    assert h != "secret123"
    assert JwtAuth.verify_password("secret123", h)
    assert not JwtAuth.verify_password("wrong", h)
    assert not JwtAuth.verify_password("secret123", "garbage-hash")


# ---------- tokens ----------

def test_token_encode_decode(tmp_path):
    auth = JwtAuth(User, lambda: None, secret_env="T", secret_file=str(tmp_path / ".s"))
    tok = auth.create_token(7)
    payload = auth.decode_token(tok)
    assert payload["sub"] == "7"


def test_refresh_token_rejected_as_access(tmp_path):
    auth = JwtAuth(User, lambda: None, secret_env="T", secret_file=str(tmp_path / ".s"))
    refresh = auth.create_refresh(7)
    assert auth.decode_token(refresh, refresh=True)["sub"] == "7"
    assert auth.decode_token(refresh) is None
    access = auth.create_token(7)
    assert access is not None  # can't be misread as refresh
    assert auth.decode_token(access, refresh=True) is None


# ---------- /api/auth router ----------

def test_register_login_me_refresh(app_client):
    r = app_client.post("/api/auth/register", json={"username": "neo", "password": "passw0rd!"})
    assert r.status_code == 201, r.text
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    me = app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == "neo"

    login = app_client.post("/api/auth/login", json={"username": "neo", "password": "passw0rd!"})
    assert login.status_code == 200
    bad = app_client.post("/api/auth/login", json={"username": "neo", "password": "wrong!"})
    assert bad.status_code == 401

    new = app_client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert new.status_code == 200
    assert new.json()["access_token"]


def test_register_duplicate_conflict(app_client):
    assert app_client.post("/api/auth/register", json={"username": "dup", "password": "passw0rd!"}).status_code == 201
    r = app_client.post("/api/auth/register", json={"username": "dup", "password": "passw0rd!"})
    assert r.status_code == 409


def test_me_rejects_invalid_token(app_client):
    assert app_client.get("/api/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert app_client.get("/api/auth/me").status_code == 401


def test_register_validates_username(app_client):
    r = app_client.post("/api/auth/register", json={"username": "a b!", "password": "passw0rd!"})
    assert r.status_code == 422
    r = app_client.post("/api/auth/register", json={"username": "ok", "password": "short"})
    assert r.status_code == 422