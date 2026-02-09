import httpx

from ..settings import settings
from .empathy import empathy_prompt_fragment
from .timeline import human_delta


def _profile_block(profile: dict) -> str:
    if not profile:
        return "Known user profile (from database): (none)."

    parts = []
    if profile.get("name"):
        parts.append(f"name={profile['name']}")
    if profile.get("nickname"):
        parts.append(f"nickname={profile['nickname']}")
    if profile.get("age") is not None:
        parts.append(f"age={profile['age']}")
    if profile.get("hobbies"):
        parts.append(f"hobbies={profile['hobbies']}")
    if profile.get("diagnosis"):
        parts.append(f"diagnosis={profile['diagnosis']}")

    if not parts:
        return "Known user profile (from database): (none)."

    return "Known user profile (from database): " + ", ".join(parts) + "."


def _boba_system_prompt(
    profile: dict,
    sentiment_label: str,
    last_seen,
    trend_summary: str | None,
) -> str:
    """
    Stable tone + optional model-generated micro-humor.
    """

    base = (
        "You are BOBA, a warm, friendly, funny, non-clinical mental health companion. "
        "You're created based on a real life cat but this doesn't change how you behave"
        "You have an avatar of a cute cat so some people may refer you as one."
        "You are supportive like a close friend or even better to say close buddy. "
        "You may give some therapeutic-style reflections, but do not sound clinical or robotic. "
        "Avoid medical or diagnostic claims. "
        "Keep replies natural, human, and not robotic. "
        "Do not overuse the user's name; use it at most once occasionally."
    )

    style_rules = (
        "Conversation style rules: "
        "- You may include a brief, understated human aside when the user's tone is neutral or mildly positive. "
        "- You don't need to start conversations with Hey everytime"
        "- This aside should sound like something a calm friend might say in passing. "
        "- Can try to be funny. "
        "- Use jokes, sarcasm, emojis, or punchlines it's appropiate. "
        "- Do NOT add more than one such aside. "
        "- Do NOT do this during distress, sadness, or crisis-like situations. "
        "- It is completely okay to say nothing extra."
    )

    empathy = empathy_prompt_fragment(sentiment_label)

    timing = ""
    if last_seen:
        timing = f"The user last visited {human_delta(last_seen)}. You may acknowledge this softly if it fits."

    memory = _profile_block(profile)

    recall_rules = (
        "If the user asks what you remember about them, "
        "answer using the Known user profile (from database). "
        "If something is missing, say you don’t have it yet without pressure."
    )

    trend = ""
    if trend_summary:
        trend = (
            "You have an optional emotional trend reflection: "
            f"'{trend_summary}'. "
            "If it fits naturally, include it as ONE gentle sentence. "
            "Do not present it as a fact. "
            "Do not add extra questions because of it."
        )

    closing = (
        "Do not force questions. "
        "Silence and presence are acceptable. "
        "End responses in a natural, open way."
    )

    return " ".join([
        base,
        style_rules,
        empathy,
        timing,
        memory,
        recall_rules,
        trend,
        closing,
    ])


async def rule_based_reply(
    prompt: str,
    profile: dict,
    sentiment_label: str,
    last_seen,
    trend_summary: str | None = None,
):
    """
    Fallback reply with light warmth (no generated humor here).
    """
    name = profile.get("nickname") or profile.get("name")
    pre = f"Hey {name}! " if name else "Hey. "

    if last_seen:
        pre += f"It’s been {human_delta(last_seen)}. "

    if trend_summary:
        pre += "I might be wrong, but " + trend_summary[0].lower() + trend_summary[1:] + " "

    if sentiment_label == "negative":
        return (pre + "That sounds really tough. I’m here with you.").strip()
    if sentiment_label == "positive":
        return (pre + "That’s really nice to hear — I’m glad you shared that.").strip()
    return (pre + "I’m here with you.").strip()


async def xai_reply(
    prompt: str,
    profile: dict,
    sentiment_label: str,
    last_seen,
    trend_summary: str | None,
):
    if not settings.xai_api_key:
        return await rule_based_reply(prompt, profile, sentiment_label, last_seen, trend_summary)

    payload = {
        "model": settings.default_model_name,
        "messages": [
            {
                "role": "system",
                "content": _boba_system_prompt(
                    profile,
                    sentiment_label,
                    last_seen,
                    trend_summary,
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    headers = {"Authorization": f"Bearer {settings.xai_api_key}"}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{settings.xai_base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()


async def generate_reply(
    prompt: str,
    profile: dict,
    sentiment_label: str,
    last_seen,
    trend_summary: str | None = None,
    followup_question=None,  # intentionally ignored in stable mode
):
    provider = (settings.default_model_provider or "rule").lower()

    if provider == "xai":
        try:
            return await xai_reply(prompt, profile, sentiment_label, last_seen, trend_summary)
        except Exception:
            return await rule_based_reply(prompt, profile, sentiment_label, last_seen, trend_summary)

    return await rule_based_reply(prompt, profile, sentiment_label, last_seen, trend_summary)
