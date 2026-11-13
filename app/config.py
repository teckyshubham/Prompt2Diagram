"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Centralized settings for Prompt2Diagram."""

    app_name: str = "Prompt2Diagram"
    app_version: str = "1.0.0"
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    plantuml_server_url: str = os.getenv(
        "PLANTUML_SERVER_URL", "https://www.plantuml.com/plantuml"
    ).rstrip("/")
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "25.0"))


settings = Settings()
