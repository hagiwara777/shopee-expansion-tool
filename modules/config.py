from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_KEEPA_DOMAIN = "JP"
CACHE_TTL_DAYS = 7
CACHE_DB_PATH = PROJECT_ROOT / "cache" / "keepa_cache.sqlite3"


@dataclass(frozen=True)
class Settings:
    keepa_api_key: str
    keepa_domain: str = DEFAULT_KEEPA_DOMAIN
    openai_api_key: str = ""


def load_settings() -> Settings:
    load_dotenv(ENV_PATH)
    api_key = os.getenv("KEEPA_API_KEY", "").strip()
    domain = os.getenv("KEEPA_DOMAIN", DEFAULT_KEEPA_DOMAIN).strip() or DEFAULT_KEEPA_DOMAIN
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    return Settings(
        keepa_api_key=api_key,
        keepa_domain=domain,
        openai_api_key=openai_api_key,
    )
