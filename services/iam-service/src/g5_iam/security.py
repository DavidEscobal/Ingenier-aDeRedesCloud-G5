import hashlib
import secrets
import time
import uuid

import jwt
from fastapi import HTTPException
from pwdlib import PasswordHash

from .store import audit

PASSWORDS = PasswordHash.recommended()
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


def unauthorized():
    return HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})


def authenticate(db, secret, settings, token):
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"],
                            issuer=settings.issuer, audience=settings.audience,
                            options={"require": ["sub", "exp", "iat", "nbf", "jti", "iss", "aud"]})
        row = db.execute(
            "SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id "
            "WHERE s.jti=? AND s.user_id=? AND s.expires>? AND u.active=1",
            (claims["jti"], claims["sub"], int(time.time())),
        ).fetchone()
        if row is None:
            raise unauthorized()
        return row, claims
    except jwt.InvalidTokenError:
        raise unauthorized() from None


def login(store, settings, secret, body):
    now = int(time.time())
    subject = hashlib.sha256(body.username.encode()).hexdigest()
    # Count attempts atomically before doing costly password verification.
    with store.transaction() as db:
        db.execute("DELETE FROM login_attempts WHERE at<=?", (now - 60,))
        limited = db.execute("SELECT COUNT(*) FROM login_attempts WHERE subject=?", (subject,)).fetchone()[0] >= 5
        if limited:
            audit(db, None, "login", None, "rate_limited")
        else:
            db.execute("INSERT INTO login_attempts VALUES(?,?)", (subject, now))
        row = db.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
        user = dict(row) if row else None
    if limited:
        raise HTTPException(429, "too_many_attempts", headers={"Retry-After": "60"})
    password_hash = user["password_hash"] if user else DUMMY_HASH
    valid, replacement = PASSWORDS.verify_and_update(body.password.get_secret_value(), password_hash)
    with store.transaction() as db:
        # Recheck account and password after hashing: disable/reset may have raced login.
        current = db.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
        accepted = bool(valid and current and current["active"] and current["password_hash"] == password_hash)
        audit(db, current["id"] if current else None, "login", None, "allowed" if accepted else "denied")
        if accepted:
            if replacement:
                db.execute("UPDATE users SET password_hash=? WHERE id=?", (replacement, current["id"]))
            jti = str(uuid.uuid4())
            db.execute("DELETE FROM sessions WHERE expires<=?", (now,))
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (jti, current["id"], now + settings.ttl_seconds))
            payload = {"sub": current["id"], "jti": jti, "iat": now, "nbf": now,
                       "exp": now + settings.ttl_seconds, "iss": settings.issuer, "aud": settings.audience}
            token = jwt.encode(payload, secret, algorithm="HS256")
    if not accepted:
        raise unauthorized()
    return {"access_token": token, "token_type": "bearer", "expires_in": settings.ttl_seconds}
