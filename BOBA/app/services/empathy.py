# Lightweight text sentiment + empathetic nudge. Uses NLTK VADER.
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

_vader = None

def get_vader():
    global _vader
    if _vader is None:
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except LookupError:
            nltk.download('vader_lexicon')
        _vader = SentimentIntensityAnalyzer()
    return _vader

def analyze_text(text: str) -> dict:
    sia = get_vader()
    scores = sia.polarity_scores(text)
    label = 'neutral'
    if scores['compound'] >= 0.3:
        label = 'positive'
    elif scores['compound'] <= -0.3:
        label = 'negative'
    return {"sentiment": label, "scores": scores}

def empathy_prompt_fragment(sentiment_label: str) -> str:
    if sentiment_label == 'negative':
        return (
            "Acknowledge feelings with warmth. Offer grounding suggestions (deep breath, small walk)."
            " Avoid clinical advice. Keep it short and caring."
        )
    if sentiment_label == 'positive':
        return (
            "Celebrate the good news warmly. Encourage the user to savor the moment and keep going."
        )
    return "Be supportive and curious, ask gentle follow-ups."

CRISIS_TERMS = [
    "suicide", "kill myself", "end my life", "self harm",
    "cutting", "overdose", "die", "want to disappear"
]

def detect_crisis(text: str) -> bool:
    t = text.lower()
    return any(term in t for term in CRISIS_TERMS)
