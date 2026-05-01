import base64
import hashlib
import hmac
import secrets
from datetime import datetime

from fastapi import Request, HTTPException
from itsdangerous import URLSafeSerializer, BadSignature
from sqlalchemy.orm import Session

from .models import AdminUser, Setting


HASH_ALGORITHM = "pbkdf2_sha256"
HASH_ITERATIONS = 260_000
SESSION_COOKIE_NAME = "appswire_admin"


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        return setting.value
    return default


def set_setting(db: Session, key: str, value: str) -> Setting:
    setting = db.query(Setting).filter(Setting.key == key).first()

    if setting:
        setting.value = value
        setting.updated_at = datetime.utcnow()
    else:
        setting = Setting(
            key=key,
            value=value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
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


def get_admin_user(db: Session) -> AdminUser | None:
    return db.query(AdminUser).order_by(AdminUser.id.asc()).first()


def admin_exists(db: Session) -> bool:
    return get_admin_user(db) is not None


def create_admin(db: Session, password: str) -> AdminUser:
    if admin_exists(db):
        raise HTTPException(status_code=400, detail="Admin user already exists")

    user = AdminUser(
        password_hash=hash_password(password),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_admin(db: Session, password: str) -> AdminUser | None:
    user = get_admin_user(db)

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def get_serializer(db: Session) -> URLSafeSerializer:
    secret_key = get_or_create_secret_key(db)
    return URLSafeSerializer(secret_key, salt="appswire-admin-session")


def create_session_token(db: Session, user: AdminUser) -> str:
    serializer = get_serializer(db)

    return serializer.dumps(
        {
            "admin_id": user.id,
            "type": "admin",
        }
    )


def verify_session_token(db: Session, token: str | None) -> bool:
    if not token:
        return False

    serializer = get_serializer(db)

    try:
        data = serializer.loads(token)
    except BadSignature:
        return False

    if data.get("type") != "admin":
        return False

    admin_id = data.get("admin_id")

    if not admin_id:
        return False

    user = db.query(AdminUser).filter(AdminUser.id == admin_id).first()

    return user is not None


def is_admin_request(request: Request, db: Session) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    return verify_session_token(db, token)


def check_admin(request: Request, db: Session):
    if not is_admin_request(request, db):
        raise HTTPException(status_code=403, detail="Not authorized")