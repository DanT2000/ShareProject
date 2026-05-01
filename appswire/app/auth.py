import base64
import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import Response
from itsdangerous import URLSafeSerializer, BadSignature
from sqlalchemy.orm import Session

from .models import AdminUser, Setting


HASH_ALGORITHM = "pbkdf2_sha256"
HASH_ITERATIONS = 260_000
SESSION_COOKIE_NAME = "appswire_admin"


# ---------------- Settings ----------------

def get_setting(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        return setting.value
    return default


def set_setting(db: Session, key: str, value: str) -> Setting:
    setting = db.query(Setting).filter(Setting.key == key).first()

    now = datetime.utcnow()

    if setting:
        setting.value = value
        setting.updated_at = now
    else:
        setting = Setting(
            key=key,
            value=value,
            created_at=now,
            updated_at=now,
        )
        db.add(setting)

    db.commit()
    db.refresh(setting)
    return setting


def get_or_create_secret_key(db: Session) -> str:
    secret_key = get_setting(db, "secret_key")

    if secret_key:
        return secret_key

    secret_key = secrets.token_urlsafe(48)
    set_setting(db, "secret_key", secret_key)
    return secret_key


# ---------------- Password hashing ----------------

def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password is empty")

    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        HASH_ITERATIONS,
    )

    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")

    return f"{HASH_ALGORITHM}${HASH_ITERATIONS}${salt_b64}${digest_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_b64, digest_b64 = stored_hash.split("$", 3)

        if algorithm != HASH_ALGORITHM:
            return False

        iterations = int(iterations_raw)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected_digest = base64.b64decode(digest_b64.encode("ascii"))

        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )

        return hmac.compare_digest(actual_digest, expected_digest)

    except Exception:
        return False


# ---------------- Admin user ----------------

def get_admin_user(db: Session) -> Optional[AdminUser]:
    return db.query(AdminUser).order_by(AdminUser.id.asc()).first()


# Compatibility alias for current main.py
def get_admin(db: Session) -> Optional[AdminUser]:
    return get_admin_user(db)


def admin_exists(db: Session) -> bool:
    return get_admin_user(db) is not None


def create_admin(db: Session, password: str) -> AdminUser:
    if admin_exists(db):
        raise HTTPException(status_code=400, detail="Admin user already exists")

    now = datetime.utcnow()

    user = AdminUser(
        password_hash=hash_password(password),
        created_at=now,
        updated_at=now,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_admin(db: Session, password: str) -> Optional[AdminUser]:
    user = get_admin_user(db)

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


# Compatibility alias, на случай если main.py вызывает auth.check_password(...)
def check_password(password: str, stored_hash: str) -> bool:
    return verify_password(password, stored_hash)


# ---------------- Sessions ----------------

def _serializer(secret_key: str) -> URLSafeSerializer:
    return URLSafeSerializer(secret_key, salt="appswire-admin-session")


def create_session_token(user_id: int, secret_key: str) -> str:
    serializer = _serializer(secret_key)

    return serializer.dumps(
        {
            "user_id": user_id,
            "type": "admin",
        }
    )


def read_session_token(token: Optional[str], secret_key: str) -> Optional[int]:
    if not token:
        return None

    serializer = _serializer(secret_key)

    try:
        data = serializer.loads(token)
    except BadSignature:
        return None

    if data.get("type") != "admin":
        return None

    user_id = data.get("user_id")

    try:
        return int(user_id)
    except Exception:
        return None


# This is what your current main.py expects:
# auth.set_session(response, user.id, _secret())
def set_session(response: Response, user_id: int, secret_key: str) -> None:
    token = create_session_token(user_id, secret_key)

    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )


# This is what your current main.py expects:
# auth.get_session_user(request, _secret())
def get_session_user(request: Request, secret_key: str) -> Optional[int]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    return read_session_token(token, secret_key)


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def is_admin_request(request: Request, db: Session, secret_key: Optional[str] = None) -> bool:
    if secret_key is None:
        secret_key = get_or_create_secret_key(db)

    user_id = get_session_user(request, secret_key)

    if not user_id:
        return False

    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()

    return user is not None


def check_admin(request: Request, db: Session, secret_key: Optional[str] = None) -> None:
    if not is_admin_request(request, db, secret_key):
        raise HTTPException(status_code=403, detail="Not authorized")