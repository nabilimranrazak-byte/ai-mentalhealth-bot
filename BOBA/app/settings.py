from pydantic import BaseModel
import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()


class Settings(BaseModel):
    # ===============================
    # Core environment
    # ===============================
    env: str = os.getenv("ENV", "dev")

    # ===============================
    # Database
    # ===============================
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./boba.db"
    )

    # ===============================
    # LLM Provider Selection
    # ===============================
    # xai | openai | ollama | rule
    default_model_provider: str = os.getenv(
        "DEFAULT_MODEL_PROVIDER",
        "xai"
    )

    default_model_name: str = os.getenv(
        "DEFAULT_MODEL_NAME",
        "grok-4"
    )

    # ===============================
    # xAI / Grok
    # ===============================
    xai_api_key: str | None = os.getenv("XAI_API_KEY")
    xai_base_url: str = os.getenv(
        "XAI_BASE_URL",
        "https://api.x.ai"
    )

    # ===============================
    # OpenAI (optional – not used yet)
    # ===============================
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

    # ===============================
    # Ollama (optional local fallback)
    # ===============================
    ollama_base_url: str = os.getenv(
        "OLLAMA_BASE_URL",
        "http://localhost:11434"
    )


# Singleton settings object
settings = Settings()
