from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv, dotenv_values
from modules.beta_runtime_paths import current_beta_paths

from modules.amazon_data_provider import (
    AmazonDataProviderConfigurationError,
    normalize_amazon_data_provider,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_KEEPA_DOMAIN = "JP"
CACHE_TTL_DAYS = 7
CACHE_DB_PATH = PROJECT_ROOT / "cache" / "keepa_cache.sqlite3"


@dataclass(frozen=True)
class Settings:
    keepa_api_key: str
    keepa_domain: str = DEFAULT_KEEPA_DOMAIN
    amazon_data_provider: str = "keepa"


def load_settings() -> Settings:
    paths = current_beta_paths()
    if paths is None:
        load_dotenv(ENV_PATH)
        values = os.environ
    else:
        # Explicit existing PH settings, without leaking them to the SG runtime
        # or to concurrent sessions. Preserve environment-over-file precedence.
        values = {**dotenv_values(paths.ph_api_env), **os.environ}
    api_key = (values.get("KEEPA_API_KEY") or "").strip()
    domain = (values.get("KEEPA_DOMAIN") or DEFAULT_KEEPA_DOMAIN).strip() or DEFAULT_KEEPA_DOMAIN
    amazon_data_provider = normalize_amazon_data_provider(
        values.get("AMAZON_DATA_PROVIDER") or "keepa"
    )
    return Settings(
        keepa_api_key=api_key,
        keepa_domain=domain,
        amazon_data_provider=amazon_data_provider,
    )
