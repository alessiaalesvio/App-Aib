"""Session auth (httpOnly JWT cookie) + role checks. The user is re-read from Mongo on every request,
so a revoked role / suspended account stops working immediately."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, Response
from passlib.context import CryptContext

from lib.db import db

COOKIE = "aib_session"
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_SECRET = os.environ["JWT_SECRET"]
_TTL = timedelta(days=14)


def hash_password(p: str) -> str:
    return _pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    try:
        return _pwd.verify(p, h)
    except Exception:
        return False


def set_session(resp: Response, user_id: str) -> None:
    token = jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc) + _TTL}, _SECRET, algorithm="HS256")
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", max_age=int(_TTL.total_seconds()), path="/")


def clear_session(resp: Response) -> None:
    resp.delete_cookie(COOKIE, path="/")


async def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Non autenticato")
    try:
        uid = jwt.decode(token, _SECRET, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "Sessione non valida")
    user = await db.users.find_one({"id": uid}, {"_id": 0})
    if not user or user.get("status") != "active":
        raise HTTPException(401, "Account non attivo")
    return user


async def require_admin(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Riservato agli amministratori")
    return user


def full_name(u: dict) -> str:
    return f"{u['first_name']} {u['last_name']}"
