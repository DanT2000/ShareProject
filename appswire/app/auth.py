import secrets
from passlib.context import CryptContext
from itsdangerous import URLSafeSerializer, BadSignature
from sqlalchemy.orm import Session
from app.models import AdminUser, Setting

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_or_create_secret_key(db: Session) -> str:
    setting = db.query(Setting).filter(Setting.key == "secret_key").first()
    if not setting:
        key = secrets.token_urlsafe(32)
        setting = Setting(key="secret_key", value=key)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting.value


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_admin(db: Session, password: str) -> AdminUser:
    user = AdminUser(password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_admin(db: Session) -> AdminUser | None:
    return db.query(AdminUser).first()


def set_session(response, user_id: int, secret_key: str) -> None:
    s = URLSafeSerializer(secret_key)
    token = s.dumps({"uid": user_id})
    response.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=86400 * 30
    )


def clear_session(response) -> None:
    response.delete_cookie("session")


def get_session_user(request, secret_key: str) -> int | None:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        s = URLSafeSerializer(secret_key)
        data = s.loads(token)
        return data.get("uid")
    except BadSignature:
        return None
