from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Text
from typing import List
from ..db import get_db
from ..models import Mood, User
from ..schemas import MoodLogIn, MoodOut
from ..services.memory import ensure_user

router = APIRouter(prefix="/mood", tags=["mood"])

VALID_MOODS = {"happy", "sad", "anxious", "stressed", "tired", "neutral", "angry"}

@router.post("/log", response_model=MoodOut)
def log_mood(payload: MoodLogIn, db: Session = Depends(get_db)):
    user = ensure_user(db, payload.user_id)

    mood_clean = payload.mood.lower().strip()

    # Optional: block unknown mood categories
    if mood_clean not in VALID_MOODS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid mood '{payload.mood}'. Valid options: {list(VALID_MOODS)}"
        )

    row = Mood(
        user_id_fk=user.id,
        mood=mood_clean,
        note=payload.note or None,
        sentiment_score=payload.sentiment_score,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return MoodOut(
        id=row.id,
        user_id=user.user_id,
        mood=row.mood,
        note=row.note,
        sentiment_score=row.sentiment_score,
        day=row.day,
        created_at=row.created_at,
    )


@router.get("/recent", response_model=List[MoodOut])
def recent_moods(
    user_id: str = Query(...),
    limit: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rows = (
        db.query(Mood)
        .filter(Mood.user_id_fk == user.id)
        .order_by(Mood.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        MoodOut(
            id=r.id,
            user_id=user.user_id,
            mood=r.mood,
            note=r.note,
            sentiment_score=r.sentiment_score,
            day=r.day,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/summary")
def mood_summary(
    user_id: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # last N days
    rows = (
        db.query(Mood.mood, func.count(Mood.id))
        .filter(Mood.user_id_fk == user.id)
        .filter(Mood.created_at >= func.now() - cast(f"{days} days", Text))
        .group_by(Mood.mood)
        .all()
    )

    total = sum(count for _, count in rows) or 1

    dist = [
        {
            "mood": mood,
            "count": int(count),
            "pct": round(100.0 * count / total, 2)
        }
        for mood, count in rows
    ]

    return {
        "user_id": user.user_id,
        "days": days,
        "total": total if total != 1 else 0,
        "distribution": dist,
    }
