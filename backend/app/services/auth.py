import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database.database import connect

PASSWORD_ITERATIONS = 600_000
SESSION_DAYS = 7
RESET_MINUTES = 30
bearer_scheme = HTTPBearer(auto_error=False)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            base64.urlsafe_b64decode(salt.encode("ascii")),
            int(iterations),
        )
        return hmac.compare_digest(
            base64.urlsafe_b64encode(digest).decode("ascii"),
            expected,
        )
    except (ValueError, TypeError):
        return False


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    created_at = datetime.now(timezone.utc)
    with connect() as db:
        db.execute(
            "INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
            (
                _token_hash(token),
                user_id,
                (created_at + timedelta(days=SESSION_DAYS)).isoformat(),
                created_at.isoformat(),
            ),
        )
    return token


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, str]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in to access the application.")

    with connect() as db:
        row = db.execute(
            """
            SELECT users.id, users.email, sessions.token_hash
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """,
            (_token_hash(credentials.credentials), _timestamp()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Your session has expired. Please sign in again.")
    return {"id": row["id"], "email": row["email"], "token_hash": row["token_hash"]}


def create_password_reset(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    created_at = datetime.now(timezone.utc)
    with connect() as db:
        db.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
        db.execute(
            "INSERT INTO password_resets(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
            (
                _token_hash(token),
                user_id,
                (created_at + timedelta(minutes=RESET_MINUTES)).isoformat(),
                created_at.isoformat(),
            ),
        )
    return token


def register_user(email: str, password: str) -> dict[str, str]:
    user_id = str(uuid.uuid4())
    normalized_email = email.strip().lower()
    try:
        with connect() as db:
            db.execute(
                "INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)",
                (user_id, normalized_email, hash_password(password), _timestamp()),
            )
    except sqlite3.IntegrityError as exc:
        if "users.email" in str(exc):
            raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
        raise
    return {"id": user_id, "email": normalized_email}


def issue_session(user_id: str) -> dict[str, object]:
    with connect() as db:
        user = db.execute("SELECT id,email FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    return {"access_token": create_session(user_id), "token_type": "bearer", "user": dict(user)}


def reset_password(token: str, password: str) -> None:
    now = _timestamp()
    with connect() as db:
        reset = db.execute(
            "SELECT user_id FROM password_resets WHERE token_hash = ? AND expires_at > ?",
            (_token_hash(token), now),
        ).fetchone()
        if reset is None:
            raise HTTPException(status_code=400, detail="This password reset link is invalid or has expired.")
        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(password), reset["user_id"]),
        )
        db.execute("DELETE FROM password_resets WHERE user_id = ?", (reset["user_id"],))
        db.execute("DELETE FROM sessions WHERE user_id = ?", (reset["user_id"],))


def logout_user(user: dict[str, str]) -> None:
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (user["token_hash"],))
