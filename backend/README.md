# Backend setup

The API uses the local SQLite database at `research.db` for accounts and app data.
Account passwords are stored as PBKDF2-HMAC-SHA256 hashes; bearer sessions and
password-reset tokens are stored only as SHA-256 hashes.

## Email delivery

Feedback and password-reset links are sent through SMTP. Copy `.env.example` to
`.env`, then replace the SMTP host, port, username, password, and verified sender
with credentials from your mail provider. `FEEDBACK_TO_EMAIL` is configured for
the requested inbox; keep provider credentials out of source control. Port 587
uses STARTTLS, while port 465 uses implicit TLS.

Feedback is saved only after its notification email has been sent successfully.
Password-reset links expire after 30 minutes and can be used once. Signed-in
sessions expire after seven days.
