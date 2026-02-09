from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db, Base, engine
from ..models import User
from ..schemas import UserCreate, UserOut
from ..services.memory import save_kv_memories
from datetime import datetime, timezone

router = APIRouter(prefix="/users", tags=["users"])

# Ensure tables exist at import time (simple dev convenience)
Base.metadata.create_all(bind=engine)

@router.post("/register", response_model=UserOut)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == payload.user_id).first()

    if user:
        # Update existing user fields if provided
        for field in ["name", "nickname", "age", "hobbies", "diagnosis"]:
            val = getattr(payload, field)
            if val is not None:
                setattr(user, field, val)
        user.last_seen = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)

        # ✅ Auto-save/refresh memories on update
        save_kv_memories(db, user, {
            "name": user.name,
            "nickname": user.nickname,
            "age": user.age,
            "hobbies": user.hobbies,
            "diagnosis": user.diagnosis
        })
        return user

    # Create new user
    user = User(
        user_id=payload.user_id,
        name=payload.name,
        nickname=payload.nickname,
        age=payload.age,
        hobbies=payload.hobbies,
        diagnosis=payload.diagnosis,
        last_seen=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # ✅ Auto-save memories on create
    save_kv_memories(db, user, {
        "name": user.name,
        "nickname": user.nickname,
        "age": user.age,
        "hobbies": user.hobbies,
        "diagnosis": user.diagnosis
    })
    return user

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# (Optional) Quick endpoint to view memories for a user
@router.get("/{user_id}/memories")
def get_user_memories(user_id: str, db: Session = Depends(get_db)):
    from ..models import Memory
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    rows = db.query(Memory).filter(Memory.user_id_fk == user.id).order_by(Memory.created_at.desc()).all()
    return [{"key": r.key, "value": r.value, "created_at": r.created_at.isoformat()} for r in rows]

@router.post("/{user_id}/memories/sync")
def sync_user_memories(user_id: str, db: Session = Depends(get_db)):
    from ..models import User, Memory
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from ..services.memory import save_kv_memories
    count = save_kv_memories(db, user, {
        "name": user.name,
        "nickname": user.nickname,
        "age": user.age,
        "hobbies": user.hobbies,
        "diagnosis": user.diagnosis
    })

    # return current memories so you can see them immediately
    rows = db.query(Memory).filter(Memory.user_id_fk == user.id).order_by(Memory.created_at.desc()).all()
    return {
        "inserted_now": count,
        "total": len(rows),
        "memories": [{"key": r.key, "value": r.value, "created_at": r.created_at.isoformat()} for r in rows]
    }
