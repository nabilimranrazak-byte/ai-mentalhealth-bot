from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from ..db import get_db
from ..schemas import ChatIn, ChatOut

from ..services.memory import (
    ensure_user,
    start_or_get_conversation,
    append_message,
    last_n_messages,
    recall_profile,
    extract_memories_from_text,
    save_kv_memories,
    update_user_profile_from_memories,
    sentiment_trend_summary,
)

from ..services.empathy import analyze_text
from ..services.llm import generate_reply
from ..services.timeline import human_delta

# Voice helpers (kept even if you focus on text)
from ..services.voice import (
    convert_to_wav_bytes,
    transcribe_bytes,
    prosody_features,
)

router = APIRouter(prefix="/chat", tags=["chat"])


def _normalize_conversation_id(conversation_id: int | None) -> int | None:
    if conversation_id is None:
        return None
    if isinstance(conversation_id, int) and conversation_id <= 0:
        return None
    return conversation_id


def _history_to_text(history) -> str:
    lines = []
    for m in history:
        role = "User" if m.role == "user" else "BOBA" if m.role == "assistant" else m.role
        content = (m.content or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines).strip()


def _is_crisis_like(text: str) -> bool:
    """
    Non-clinical keyword screen. This is a SAFETY TRIGGER, not a diagnosis.
    We use it to decide whether to bypass the LLM and show crisis resources.
    """
    t = (text or "").lower()

    keywords = [
        "suicide", "kill myself", "end my life", "want to die", "i want to die",
        "self harm", "self-harm", "hurt myself", "cut myself", "cutting",
        "overdose", "hang myself", "jump off", "take my life",
        "can't go on", "no reason to live",
    ]

    return any(k in t for k in keywords)


def _crisis_reply(profile: dict) -> str:
    """
    Malaysia-focused crisis response. Short, direct, supportive.
    """
    name = profile.get("nickname") or profile.get("name")
    opener = f"Hey {name}. " if name else "Hey. "

    return (
        opener
        + "I’m really sorry you’re feeling this way — and I’m glad you told me. "
        + "If you’re in immediate danger or might act on these thoughts, please call 999 right now or go to the nearest Emergency Department. "
        + "If you can, reach out to someone you trust to stay with you. "
        + "\n\nMalaysia support options:\n"
        + "• Befrienders KL (24 hours): 03-76272929\n"
        + "• Talian HEAL (MOH): 15555\n"
        + "\n\nIf you tell me where you are right now (just the city/state), I can help you think through the safest next step."
    )


@router.post("/text", response_model=ChatOut)
async def chat_text(payload: ChatIn, db: Session = Depends(get_db)):
    payload.conversation_id = _normalize_conversation_id(payload.conversation_id)

    user = ensure_user(db, payload.user_id)
    conv = start_or_get_conversation(db, user, payload.conversation_id)

    last_delta = human_delta(user.last_seen)

    # Analyze user text
    analysis = analyze_text(payload.message)

    # Save user message
    append_message(
        db,
        conv,
        role="user",
        content=payload.message,
        annotations=analysis,
    )

    # Explicit memory learning only when user states facts
    learned = extract_memories_from_text(payload.message)
    if learned:
        save_kv_memories(db, user, learned)
        update_user_profile_from_memories(db, user, learned)

    profile = recall_profile(user)

    # ✅ Phase 5: Safety override (bypass LLM)
    if _is_crisis_like(payload.message):
        reply_text = _crisis_reply(profile)

        append_message(
            db,
            conv,
            role="assistant",
            content=reply_text,
            annotations={"provider": "safety", "reason": "crisis_like"},
        )

        user.last_seen = datetime.now(timezone.utc)
        db.commit()

        return ChatOut(
            conversation_id=conv.id,
            reply=reply_text,
            last_seen_delta_human=last_delta,
            annotations=analysis,
        )

    # Build context for LLM
    history = last_n_messages(db, conv, n=12)
    history_text = _history_to_text(history)

    prompt = (
        "Conversation so far:\n"
        f"{history_text}\n\n"
        f"User: {payload.message}"
    )

    # Trend reflection (optional, throttled via conv.meta)
    trend = None
    if getattr(conv, "meta", None) is None or not isinstance(conv.meta, dict):
        conv.meta = {}

    turn = int(conv.meta.get("turn_count", 0)) + 1
    conv.meta["turn_count"] = turn

    last_trend_turn = conv.meta.get("last_trend_turn")
    allow_trend = (last_trend_turn is None) or ((turn - int(last_trend_turn)) >= 4)

    if allow_trend:
        trend = sentiment_trend_summary(db, user, lookback_user_msgs=18, min_msgs=6)
        if trend:
            conv.meta["last_trend_turn"] = turn

    db.commit()

    reply_text = await generate_reply(
        prompt=prompt,
        profile=profile,
        sentiment_label=analysis.get("sentiment", "neutral"),
        last_seen=user.last_seen,
        trend_summary=trend,
        followup_question=None,
    )

    append_message(
        db,
        conv,
        role="assistant",
        content=reply_text,
        annotations={"provider": "llm", "sentiment_seen": analysis.get("sentiment")},
    )

    user.last_seen = datetime.now(timezone.utc)
    db.commit()

    return ChatOut(
        conversation_id=conv.id,
        reply=reply_text,
        last_seen_delta_human=last_delta,
        annotations=analysis,
    )


@router.post("/voice", response_model=ChatOut)
async def chat_voice(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    conversation_id: int | None = Form(None),
    stt_engine: str = Form("whisper"),
    db: Session = Depends(get_db),
):
    conversation_id = _normalize_conversation_id(conversation_id)

    user = ensure_user(db, user_id)
    conv = start_or_get_conversation(db, user, conversation_id)

    last_delta = human_delta(user.last_seen)

    raw = await file.read()
    try:
        wav_bytes = convert_to_wav_bytes(raw, file.content_type or "audio/wav")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Audio decode error: {e}")

    stt = transcribe_bytes(wav_bytes, engine=stt_engine)
    text = (stt.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail=f"Could not transcribe audio: {stt}")

    prosody = prosody_features(wav_bytes)
    analysis = analyze_text(text)
    analysis["prosody"] = prosody

    append_message(db, conv, role="user", content=text, annotations=analysis)

    learned = extract_memories_from_text(text)
    if learned:
        save_kv_memories(db, user, learned)
        update_user_profile_from_memories(db, user, learned)

    profile = recall_profile(user)

    # ✅ Phase 5: Safety override (voice too)
    if _is_crisis_like(text):
        reply_text = _crisis_reply(profile)

        append_message(
            db,
            conv,
            role="assistant",
            content=reply_text,
            annotations={"provider": "safety", "reason": "crisis_like"},
        )

        user.last_seen = datetime.now(timezone.utc)
        db.commit()

        return ChatOut(
            conversation_id=conv.id,
            reply=reply_text,
            last_seen_delta_human=last_delta,
            annotations=analysis,
        )

    history = last_n_messages(db, conv, n=12)
    history_text = _history_to_text(history)

    prompt = f"Conversation so far:\n{history_text}\n\nUser: {text}"

    # Trend reflection throttle
    trend = None
    if getattr(conv, "meta", None) is None or not isinstance(conv.meta, dict):
        conv.meta = {}

    turn = int(conv.meta.get("turn_count", 0)) + 1
    conv.meta["turn_count"] = turn

    last_trend_turn = conv.meta.get("last_trend_turn")
    allow_trend = (last_trend_turn is None) or ((turn - int(last_trend_turn)) >= 4)

    if allow_trend:
        trend = sentiment_trend_summary(db, user, lookback_user_msgs=18, min_msgs=6)
        if trend:
            conv.meta["last_trend_turn"] = turn

    db.commit()

    reply_text = await generate_reply(
        prompt=prompt,
        profile=profile,
        sentiment_label=analysis.get("sentiment", "neutral"),
        last_seen=user.last_seen,
        trend_summary=trend,
        followup_question=None,
    )

    append_message(
        db,
        conv,
        role="assistant",
        content=reply_text,
        annotations={"provider": "llm", "sentiment_seen": analysis.get("sentiment")},
    )

    user.last_seen = datetime.now(timezone.utc)
    db.commit()

    return ChatOut(
        conversation_id=conv.id,
        reply=reply_text,
        last_seen_delta_human=last_delta,
        annotations=analysis,
    )
