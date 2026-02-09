import re
from sqlalchemy.orm import Session
from ..models import User, Memory, Conversation, Message

MEMORY_KEYS = {"name", "nickname", "age", "hobbies", "diagnosis"}


def ensure_user(db: Session, user_id: str, **defaults) -> User:
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(user_id=user_id, **defaults)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def recall_profile(user: User) -> dict:
    return {
        "name": user.name,
        "nickname": user.nickname,
        "age": user.age,
        "hobbies": user.hobbies,
        "diagnosis": user.diagnosis,
    }


def save_kv_memories(db: Session, user: User, items: dict):
    for k, v in items.items():
        if k not in MEMORY_KEYS:
            continue
        if v is None:
            continue
        m = Memory(user_id_fk=user.id, key=k, value=str(v).strip())
        db.add(m)
    db.commit()


def update_user_profile_from_memories(db: Session, user: User, items: dict):
    changed = False

    if items.get("name") and not user.name:
        user.name = str(items["name"]).strip()
        changed = True

    if items.get("nickname") and not user.nickname:
        user.nickname = str(items["nickname"]).strip()
        changed = True

    if items.get("age") is not None and user.age is None:
        try:
            user.age = int(items["age"])
            changed = True
        except Exception:
            pass

    if items.get("hobbies") and not user.hobbies:
        user.hobbies = str(items["hobbies"]).strip()
        changed = True

    if items.get("diagnosis") and not user.diagnosis:
        user.diagnosis = str(items["diagnosis"]).strip()
        changed = True

    if changed:
        db.commit()
        db.refresh(user)


def extract_memories_from_text(text: str) -> dict:
    t = (text or "").strip()
    low = t.lower()
    out: dict = {}

    # Nickname
    m = re.search(r"\b(?:call me|you can call me)\s+([A-Za-z][A-Za-z0-9_\-]{1,20})\b", t, re.I)
    if m:
        out["nickname"] = m.group(1)

    # Name
    m = re.search(r"\bmy name is\s+([A-Za-z][A-Za-z0-9_\-]{1,20})\b", t, re.I)
    if m:
        out["name"] = m.group(1)

    # Age
    m = re.search(r"\b(?:i am|i'm)\s+(\d{1,2})\s*(?:years?\s*old)?\b", low)
    if m:
        age = int(m.group(1))
        if 5 <= age <= 120:
            out["age"] = age

    # Hobbies
    m = re.search(r"\b(?:my hobbies are|my hobbies include)\s+(.+)$", t, re.I)
    if m:
        hobbies = m.group(1).strip(" .!")
        if len(hobbies) <= 120:
            out["hobbies"] = hobbies

    m = re.search(r"\b(?:i like|i enjoy|i love)\s+(.+)$", t, re.I)
    if m:
        hobbies = m.group(1).strip(" .!")
        if 2 <= len(hobbies) <= 120:
            out.setdefault("hobbies", hobbies)

    # Diagnosis
    m = re.search(r"\b(?:i was diagnosed with|i've been diagnosed with)\s+(.+)$", t, re.I)
    if m:
        diag = m.group(1).strip(" .!")
        if 2 <= len(diag) <= 80:
            out["diagnosis"] = diag

    m = re.search(r"\bmy diagnosis is\s+(.+)$", t, re.I)
    if m:
        diag = m.group(1).strip(" .!")
        if 2 <= len(diag) <= 80:
            out["diagnosis"] = diag

    return out


# ✅ Nickname-first UX (kept, but not used for auto-asking now)
def choose_missing_field(profile: dict) -> str | None:
    order = ["nickname", "hobbies", "age", "diagnosis"]
    for f in order:
        if profile.get(f) is None:
            return f
    return None


def question_for_field(field: str) -> str:
    if field == "nickname":
        return "What do you like being called?"
    if field == "age":
        return "How old are you, if you don’t mind me asking?"
    if field == "hobbies":
        return "What do you usually do to unwind or feel a bit better?"
    if field == "diagnosis":
        return "If you’re comfortable sharing—have you ever been diagnosed with anything before? (It’s okay to say no.)"
    return ""


def extract_pending_field_value(field: str, text: str) -> dict:
    # Kept for compatibility (not used if auto-questions are removed)
    t = (text or "").strip()
    low = t.lower()
    if not t:
        return {}

    if field == "age":
        m = re.search(r"\b(\d{1,2})\b", low)
        if m:
            age = int(m.group(1))
            if 5 <= age <= 120:
                return {"age": age}
        return {}

    if field == "nickname":
        token = re.sub(r"[^A-Za-z0-9_\-]", "", t.split()[0]) if t.split() else ""
        if 2 <= len(token) <= 20:
            return {"nickname": token}
        return {}

    if field == "hobbies":
        if 2 <= len(t) <= 120:
            return {"hobbies": t}
        return {}

    if field == "diagnosis":
        if low in {"no", "nope", "none", "nah", "nothing", "prefer not to say"}:
            return {"diagnosis": "None reported"}
        if 2 <= len(t) <= 80:
            return {"diagnosis": t}
        return {}

    return {}


def start_or_get_conversation(db: Session, user: User, conversation_id: int | None):
    if conversation_id:
        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id_fk == user.id
        ).first()
        if conv:
            return conv

    conv = Conversation(user_id_fk=user.id, meta={})
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def append_message(db: Session, conversation: Conversation, role: str, content: str, annotations=None):
    msg = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        annotations=annotations or {},
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def last_n_messages(db: Session, conversation: Conversation, n: int = 12):
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(n)
        .all()[::-1]
    )


# =========================
# ✅ Emotional Trend Summary
# =========================
def _extract_compound(annotations: dict) -> float | None:
    try:
        v = annotations.get("scores", {}).get("compound")
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def sentiment_trend_summary(
    db: Session,
    user: User,
    lookback_user_msgs: int = 18,
    min_msgs: int = 6,
) -> str | None:
    """
    Returns a short, gentle trend reflection based on recent USER messages.

    Uses annotations->scores->compound (VADER-style). Example outputs:
    - "Over the last few chats, it seems like things have felt a bit heavier."
    - "You’ve sounded a bit lighter recently—like something is easing up."
    """
    # Get recent user messages across conversations for this user
    rows = (
        db.query(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.user_id_fk == user.id)
        .filter(Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(lookback_user_msgs)
        .all()
    )

    compounds: list[float] = []
    for m in rows:
        ann = m.annotations or {}
        c = _extract_compound(ann)
        if c is not None:
            compounds.append(c)

    if len(compounds) < min_msgs:
        return None

    # Reverse so oldest -> newest
    compounds = compounds[::-1]

    # Compare early vs late average (simple but effective)
    mid = len(compounds) // 2
    early = compounds[:mid]
    late = compounds[mid:]

    def avg(xs: list[float]) -> float:
        return sum(xs) / max(len(xs), 1)

    early_avg = avg(early)
    late_avg = avg(late)
    delta = late_avg - early_avg

    # Thresholds tuned to avoid over-claiming
    if delta <= -0.12:
        return "Over the last few chats, it seems like things have felt a bit heavier for you."
    if delta >= 0.12:
        return "Lately, you’ve sounded a little lighter—like something might be easing up, even if it’s subtle."

    # If no clear trend, avoid saying anything
    return None
