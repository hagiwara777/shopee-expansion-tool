"""Explicit limited SG live validation; never grants formal operation approval.

The caller must obtain owner authorization before constructing this scope.
Scope enforces the authorized limits; it is not evidence of owner approval.
"""

from dataclasses import dataclass, field
from decimal import Decimal
import json
from pathlib import Path
import re
from threading import Lock

import requests

from modules.category_mapper_store import default_category_mapper_db_path
from modules.ph_image_safety_api import RESPONSES_URL


class LiveValidationStopped(ValueError):
    pass


@dataclass(frozen=True)
class SGLiveValidationScope:
    allowed_asins: tuple[str, ...]
    shop_id: int
    db_path: Path
    brand_page_limit: int = 10
    allowed_brand_category_ids: tuple[int, ...] = ()
    _brand_page_counts: dict[int, int] = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self):
        if (not isinstance(self.allowed_asins, tuple) or not 1 <= len(self.allowed_asins) <= 3
                or len(set(self.allowed_asins)) != len(self.allowed_asins)
                or any(not isinstance(asin, str) or not re.fullmatch(r"[A-Z0-9]{10}", asin) for asin in self.allowed_asins)
                or type(self.shop_id) is not int or self.shop_id <= 0):
            raise LiveValidationStopped("Invalid three-product SG validation scope")
        if (type(self.brand_page_limit) is not int or not 1 <= self.brand_page_limit <= 50
                or not isinstance(self.allowed_brand_category_ids, tuple)
                or len(self.allowed_brand_category_ids) > 3
                or len(set(self.allowed_brand_category_ids)) != len(self.allowed_brand_category_ids)
                or any(type(cid) is not int or cid <= 0 for cid in self.allowed_brand_category_ids)
                or self.brand_page_limit > 10 and not self.allowed_brand_category_ids):
            raise LiveValidationStopped("Explicit bounded Brand category scope required")
        path = Path(self.db_path).resolve()
        if path == default_category_mapper_db_path().resolve():
            raise LiveValidationStopped("Production DB is outside live validation scope")
        object.__setattr__(self, "db_path", path)

    def require_client(self, client, store):
        if (client.marketplace != "SG" or client.credentials.shop_id != self.shop_id
                or store.db_path.resolve() != self.db_path):
            raise LiveValidationStopped("SG live client/store binding changed")
        store._require_sg_brand_acceptance()

    def require_product(self, item):
        if item.marketplace != "SG" or item.candidate_asin not in self.allowed_asins:
            raise LiveValidationStopped("Product outside authorized SG validation scope")

    def require_brand_category(self, category_id):
        if self.allowed_brand_category_ids and category_id not in self.allowed_brand_category_ids:
            raise LiveValidationStopped("Brand Category outside authorized scope")

    def reserve_brand_page(self, category_id):
        self.require_brand_category(category_id)
        # Extended grants are cumulative within this scope, including failed
        # requests and repeated sync attempts. Legacy runs retain their limit.
        if self.allowed_brand_category_ids:
            count = self._brand_page_counts.get(category_id, 0)
            if count >= self.brand_page_limit:
                raise LiveValidationStopped("Brand page grant exhausted")
            self._brand_page_counts[category_id] = count + 1


class OpenAIValidationBudget:
    """Precharge conservative request ceilings; never refund an uncertain call.

    Uses fetched 2026-10-04 standard short-context prices. Input text is bounded
    by UTF-8 byte count plus overhead, each image by 36,000 billable tokens
    (30,000 patches * 1.2). Long-context, tools, priority and unknown models are
    refused. The upper-bound ledger is not a billing statement.
    """

    _PRICES = {"gpt-5.6-luna": (Decimal("0.20"), Decimal("1.20")),
               "gpt-5.6-terra": (Decimal("2"), Decimal("12"))}

    def __init__(self, *, limit_usd=Decimal("1"), ledger_path=None):
        limit = Decimal(str(limit_usd))
        if not limit.is_finite() or not Decimal("0") < limit <= Decimal("1"):
            raise LiveValidationStopped("OpenAI ceiling must be at most USD 1")
        self.limit_usd = limit
        self.reserved_usd = Decimal("0")
        self.request_count = 0
        self.stopped = False
        self._lock = Lock()
        self.ledger_path = Path(ledger_path) if ledger_path is not None else None
        if self.ledger_path is not None and self.ledger_path.exists():
            raise LiveValidationStopped("Existing live ledger must not be reset")

    @classmethod
    def ceiling(cls, payload):
        model = payload.get("model")
        if (model not in cls._PRICES or payload.get("store") is not False
                or payload.get("stream", False) is not False or payload.get("tools")
                or payload.get("service_tier", "default") != "default"
                or type(payload.get("max_output_tokens")) is not int
                or not 1 <= payload["max_output_tokens"] <= 1200):
            raise LiveValidationStopped("Unsupported paid request profile")
        image_count = 0
        def text_copy(value):
            nonlocal image_count
            if isinstance(value, dict):
                if value.get("type") == "input_image":
                    url = value.get("image_url")
                    if not isinstance(url, str) or not url.startswith("data:image/"):
                        raise LiveValidationStopped("Unbounded image input")
                    image_count += 1
                    return {"type": "input_image"}
                return {key: text_copy(child) for key, child in value.items()}
            if isinstance(value, list): return [text_copy(child) for child in value]
            return value
        copied = text_copy(payload)
        if image_count > 3:
            raise LiveValidationStopped("Too many paid images")
        text_bytes = len(json.dumps(copied, ensure_ascii=False).encode("utf-8"))
        input_bound = text_bytes + 8192 + image_count * 36000
        if input_bound > 272000:
            raise LiveValidationStopped("Long-context request exceeds validation profile")
        input_price, output_price = cls._PRICES[model]
        # Extra margin also covers cache writes at 1.25x and small overheads.
        return (Decimal(input_bound) * input_price * Decimal("1.25")
                + Decimal(payload["max_output_tokens"]) * output_price) / Decimal(1000000)

    def reserve(self, payload):
        with self._lock:
            if self.stopped:
                raise LiveValidationStopped("OpenAI validation budget stopped")
            try:
                ceiling = self.ceiling(payload)
                if self.reserved_usd + ceiling > self.limit_usd:
                    raise LiveValidationStopped("OpenAI validation budget exhausted")
                self.reserved_usd += ceiling
                self.request_count += 1
                if self.ledger_path is not None:
                    self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
                    self.ledger_path.write_text(json.dumps(self.summary()) + "\n", encoding="utf-8")
            except Exception:
                self.stopped = True
                raise

    def summary(self):
        return {"limit_usd": str(self.limit_usd), "reserved_upper_bound_usd": str(self.reserved_usd),
                "requests": self.request_count, "stopped": self.stopped}


class BudgetedOpenAISession:
    def __init__(self, budget, *, session=None):
        self.budget = budget
        self._session = session if session is not None else requests.Session()

    def post(self, url, **kwargs):
        if url != RESPONSES_URL:
            raise LiveValidationStopped("Unexpected paid endpoint")
        payload = dict(kwargs["json"])
        payload["service_tier"] = "default"
        self.budget.reserve(payload)  # Before network; includes retries/timeouts.
        return self._session.post(url, **{**kwargs, "json": payload, "allow_redirects": False})
