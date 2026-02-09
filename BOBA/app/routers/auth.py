from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from ..db import get_db
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])

# ✅ Use pbkdf2_sha256 to avoid bcrypt issues on Windows
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def next_user_id(db: Session) -> str:
    # Generates U0001, U0002, ...
    last = db.query(User).order_by(User.id.desc()).first()
    n = (last.id + 1) if last else 1
    return f"U{n:04d}"


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


@router.post("/register")
def register(payload: dict, db: Session = Depends(get_db)):
    email = normalize_email(payload.get("email"))
    password = payload.get("password") or ""

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")

    # ✅ simple password rules
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if len(password.encode("utf-8")) > 512:
        raise HTTPException(status_code=400, detail="Password too long")

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email,
        user_id=next_user_id(db),
        password_hash=pwd_context.hash(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"user_id": user.user_id, "email": user.email}


@router.post("/login")
def login(payload: dict, db: Session = Depends(get_db)):
    email = normalize_email(payload.get("email"))
    password = payload.get("password") or ""

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not getattr(user, "password_hash", None):
        raise HTTPException(status_code=401, detail="Account password not set. Please register again.")

    if not pwd_context.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {"user_id": user.user_id, "email": user.email}
