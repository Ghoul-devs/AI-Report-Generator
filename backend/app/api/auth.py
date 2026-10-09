import os
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.database.database import connect
from app.services.auth import (
    create_password_reset,
    issue_session,
    logout_user,
    register_user,
    require_user,
    reset_password,
    verify_password,
)
from app.services.email import send_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    password: str = Field(min_length=8, max_length=128)


@router.post("/register")
def register(body: Credentials):
    user = register_user(body.email, body.password)
    return issue_session(user["id"])


@router.post("/login")
def login(body: Credentials):
    with connect() as db:
        user = db.execute(
            "SELECT id,email,password_hash FROM users WHERE email = ?",
            (body.email,),
        ).fetchone()
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return issue_session(user["id"])


@router.get("/me")
def current_user(user: dict[str, str] = Depends(require_user)):
    return {"id": user["id"], "email": user["email"]}


@router.post("/logout")
def logout(user: dict[str, str] = Depends(require_user)):
    logout_user(user)
    return {"logged_out": True}


@router.post("/forgot-password")
def forgot_password(body: EmailRequest):
    with connect() as db:
        user = db.execute("SELECT id,email FROM users WHERE email = ?", (body.email,)).fetchone()
    if user is not None:
        token = create_password_reset(user["id"])
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
        reset_url = f"{frontend_url}/reset-password?token={quote(token)}"
        send_email(
            "Reset your Atlas Research password",
            f"Use this link within 30 minutes to reset your password:\n\n{reset_url}\n\n"
            "If you did not request this, you can ignore this email.",
            recipient=user["email"],
        )
    return {"message": "If an account exists for that email, a reset link has been sent."}


@router.post("/reset-password")
def reset_password_route(body: PasswordResetRequest):
    reset_password(body.token, body.password)
    return {"password_reset": True}
