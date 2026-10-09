import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()


def send_email(subject: str, body: str, recipient: str | None = None) -> None:
    host = os.getenv("SMTP_HOST")
    username = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM_EMAIL", username or "")
    recipient = recipient or os.getenv("FEEDBACK_TO_EMAIL")

    if not all((host, username, password, sender, recipient)):
        raise HTTPException(
            status_code=503,
            detail="Email delivery is not configured. Set the SMTP and recipient environment variables.",
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Email delivery failed. Check the SMTP server settings and try again.",
        ) from exc
