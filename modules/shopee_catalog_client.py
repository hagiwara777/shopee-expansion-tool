"""Read-only Shopee Open Platform catalog client for PH Category Mapper."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen


PH_MARKETPLACE = "PH"
SHOPEE_PARTNER_BASE_URL = "https://partner.shopeemobile.com"
_CATEGORY_PATH = "/api/v2/product/get_category"
_ATTRIBUTE_PATH = "/api/v2/product/get_attribute_tree"
_BRAND_PATH = "/api/v2/product/get_brand_list"
_MAX_TIMEOUT_SECONDS = 30
_MAX_ATTRIBUTE_CATEGORY_IDS = 20
BRAND_STATUS_NORMAL = 1
BRAND_STATUS_PENDING = 2
_VALID_BRAND_STATUSES = frozenset({BRAND_STATUS_NORMAL, BRAND_STATUS_PENDING})


class ShopeeCatalogError(RuntimeError):
    """Raised for safe, read-only catalog API failures."""


class ShopeeCatalogConfigurationError(ShopeeCatalogError):
    """Raised when required credentials are unavailable."""


class ShopeeRateLimitError(ShopeeCatalogError):
    """Raised immediately on HTTP 429 without automatic retry."""


@dataclass(frozen=True)
class ShopeeCatalogCredentials:
    partner_id: int
    partner_key: str
    shop_id: int
    access_token: str


@dataclass(frozen=True)
class BrandPage:
    brands: tuple[dict[str, Any], ...]
    next_offset: int
    is_complete: bool

    @property
    def has_next_page(self) -> bool:
        """Expose the API paging signal while retaining the existing caller contract."""

        return not self.is_complete


class ShopeeCatalogClient:
    """Read only category, attribute, and brand endpoints for the PH shop."""

    def __init__(
        self,
        credentials: ShopeeCatalogCredentials,
        *,
        base_url: str = SHOPEE_PARTNER_BASE_URL,
        request_json: Callable[[str, Mapping[str, str], int], Mapping[str, Any]] | None = None,
    ) -> None:
        self.credentials = credentials
        self.base_url = base_url.rstrip("/")
        self._request_json = request_json or _urlopen_json

    @classmethod
    def from_local_audit_env(cls, env_path: str | Path | None = None) -> "ShopeeCatalogClient":
        return cls(load_shopee_catalog_credentials(env_path))

    def get_categories(self, marketplace: str, *, language: str = "en") -> tuple[dict[str, Any], ...]:
        self._require_ph(marketplace)
        payload = self._get(_CATEGORY_PATH, {"language": language})
        response = _response_dict(payload, endpoint_path=_CATEGORY_PATH)
        raw_categories = _required_list(
            response,
            "category_list",
            "categories",
            "category_tree",
            endpoint_path=_CATEGORY_PATH,
        )
        categories = []
        for raw in raw_categories:
            if not isinstance(raw, Mapping):
                continue
            category_id = _int_or_none(raw.get("category_id"))
            if category_id is None or category_id <= 0:
                continue
            has_children = raw.get("has_children")
            is_leaf_value = raw.get("is_leaf")
            if is_leaf_value is None:
                is_leaf_value = raw.get("is_leaf_category")
            is_leaf = bool(is_leaf_value) if is_leaf_value is not None else not bool(has_children)
            category_name = _first_text(
                raw,
                "display_category_name",
                "original_category_name",
                "category_name",
                "name",
            )
            categories.append(
                {
                    "category_id": category_id,
                    "parent_category_id": _int_or_none(raw.get("parent_category_id")),
                    "category_name": category_name,
                    "is_leaf": is_leaf,
                    "is_others": category_name.casefold() == "others",
                }
            )
        return tuple(categories)

    def get_attribute_tree(
        self, marketplace: str, category_id: int, *, language: str = "en"
    ) -> Any:
        """Return the tree for one category, preserving the original public API."""

        numeric_category_id = _positive_int(category_id)
        result = self.get_attribute_trees(
            marketplace,
            (numeric_category_id,),
            language=language,
        )
        return result[0]["attribute_tree"]

    def get_attribute_trees(
        self,
        marketplace: str,
        category_ids: Sequence[int],
        *,
        language: str = "en",
    ) -> tuple[dict[str, Any], ...]:
        """Return ordered attribute-tree results for up to 20 distinct category IDs."""

        self._require_ph(marketplace)
        normalized_category_ids = _normalize_category_id_list(category_ids)
        payload = self._get(
            _ATTRIBUTE_PATH,
            {
                "category_id_list": _serialize_category_id_list(normalized_category_ids),
                "language": language,
            },
        )
        response = _response_dict(payload, endpoint_path=_ATTRIBUTE_PATH)
        raw_results = _required_list(response, "list", endpoint_path=_ATTRIBUTE_PATH)
        results_by_category_id: dict[int, dict[str, Any]] = {}
        for raw_result in raw_results:
            if not isinstance(raw_result, Mapping):
                raise _response_error(_ATTRIBUTE_PATH, "attribute result was invalid")
            try:
                response_category_id = _positive_int(raw_result.get("category_id"))
            except ValueError as exc:
                raise _response_error(
                    _ATTRIBUTE_PATH, "attribute result category_id was invalid"
                ) from exc
            raw_tree = raw_result.get("attribute_tree")
            if not isinstance(raw_tree, list):
                raise _response_error(_ATTRIBUTE_PATH, "attribute_tree was missing")
            if response_category_id in results_by_category_id:
                raise _response_error(_ATTRIBUTE_PATH, "duplicate category result")
            results_by_category_id[response_category_id] = {
                "category_id": response_category_id,
                "attribute_tree": raw_tree,
            }
        try:
            return tuple(results_by_category_id[category_id] for category_id in normalized_category_ids)
        except KeyError as exc:
            raise _response_error(_ATTRIBUTE_PATH, "requested category result was missing") from exc

    def get_brand_list(
        self,
        marketplace: str,
        category_id: int,
        *,
        offset: int = 0,
        page_size: int = 100,
        status: int = BRAND_STATUS_NORMAL,
    ) -> BrandPage:
        self._require_ph(marketplace)
        numeric_category_id = _positive_int(category_id)
        numeric_offset = _nonnegative_int(offset, field_name="offset")
        numeric_page_size = _positive_int(page_size, field_name="page_size")
        if numeric_page_size > 100:
            raise ValueError("page_size must be between 1 and 100")
        numeric_status = _brand_status(status)
        payload = self._get(
            _BRAND_PATH,
            {
                "category_id": str(numeric_category_id),
                "status": str(numeric_status),
                "offset": str(numeric_offset),
                "page_size": str(numeric_page_size),
            },
        )
        response = _response_dict(payload, endpoint_path=_BRAND_PATH)
        raw_brands = _required_list(response, "brand_list", endpoint_path=_BRAND_PATH)
        brands = []
        for raw in raw_brands:
            if not isinstance(raw, Mapping):
                continue
            brand_id = _int_or_none(raw.get("brand_id"))
            if brand_id is None or brand_id < 0:
                continue
            brand_name = _first_text(raw, "display_brand_name", "brand_name", "name")
            is_no_brand = brand_id == 0 or brand_name.casefold() in {
                "no brand",
                "no_brand",
                "nobrand",
            }
            brands.append(
                {
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                    "is_no_brand": is_no_brand,
                }
            )

        try:
            next_offset = _nonnegative_int(
                response.get("next_offset"), field_name="next_offset"
            )
        except ValueError as exc:
            raise _response_error(_BRAND_PATH, "next_offset was missing or invalid") from exc
        has_next = response.get("has_next_page")
        if not isinstance(has_next, bool):
            raise _response_error(_BRAND_PATH, "has_next_page was missing")
        is_complete = not has_next
        if next_offset <= numeric_offset and not is_complete:
            raise ShopeeCatalogError("Catalog brand pagination response was invalid.")
        return BrandPage(tuple(brands), next_offset, is_complete)

    def _get(self, path: str, parameters: Mapping[str, str]) -> Mapping[str, Any]:
        timestamp = int(time.time())
        signature_base = (
            f"{self.credentials.partner_id}{path}{timestamp}"
            f"{self.credentials.access_token}{self.credentials.shop_id}"
        )
        signature = hmac.new(
            self.credentials.partner_key.encode("utf-8"),
            signature_base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        query = {
            "partner_id": str(self.credentials.partner_id),
            "timestamp": str(timestamp),
            "access_token": self.credentials.access_token,
            "shop_id": str(self.credentials.shop_id),
            "sign": signature,
            **parameters,
        }
        try:
            payload = self._request_json(
                f"{self.base_url}{path}",
                query,
                _MAX_TIMEOUT_SECONDS,
            )
        except ShopeeCatalogError:
            raise
        except Exception as exc:
            raise ShopeeCatalogError(f"Catalog API request failed at {path}.") from exc
        if not isinstance(payload, Mapping):
            raise _response_error(path, "response was invalid")
        error = payload.get("error")
        if error:
            raise _application_error(path, error, payload.get("message"))
        return payload

    @staticmethod
    def _require_ph(marketplace: str) -> None:
        if str(marketplace).strip().upper() != PH_MARKETPLACE:
            raise ValueError("Category Mapper supports PH only.")


def load_shopee_catalog_credentials(
    env_path: str | Path | None = None,
) -> ShopeeCatalogCredentials:
    """Load only the required local values without exposing or persisting them."""

    path = Path(env_path) if env_path is not None else _default_audit_env_path()
    try:
        values = _read_env_values(path)
        partner_id = _positive_int(values.get("SHOPEE_PARTNER_ID"))
        shop_id = _positive_int(values.get("SHOPEE_PH_SHOP_ID"))
        partner_key = values.get("SHOPEE_PARTNER_KEY", "").strip()
        catalog_token = values.get("SHOPEE_PH_ACCESS_TOKEN", "").strip()
    except (OSError, ValueError) as exc:
        raise ShopeeCatalogConfigurationError(
            "Shopee catalog credentials are unavailable."
        ) from exc
    if not partner_id or not shop_id or not partner_key or not catalog_token:
        raise ShopeeCatalogConfigurationError("Shopee catalog credentials are unavailable.")
    return ShopeeCatalogCredentials(partner_id, partner_key, shop_id, catalog_token)


def _default_audit_env_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "ShopeeOpenPlatform" / "audit.env"
    return Path.home() / "AppData" / "Local" / "ShopeeOpenPlatform" / "audit.env"


def _read_env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        if normalized_key in {
            "SHOPEE_PARTNER_ID",
            "SHOPEE_PARTNER_KEY",
            "SHOPEE_PH_SHOP_ID",
            "SHOPEE_PH_ACCESS_TOKEN",
        }:
            values[normalized_key] = value.strip().strip("\"'")
    return values


def _urlopen_json(url: str, parameters: Mapping[str, str], timeout: int) -> Mapping[str, Any]:
    request_url = f"{url}?{urlencode(parameters)}"
    endpoint_path = urlsplit(url).path
    try:
        with urlopen(request_url, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        payload = _decode_mapping_or_none(exc.read())
        error = payload.get("error") if payload else None
        message = payload.get("message") if payload else None
        if exc.code == 429:
            raise ShopeeRateLimitError(
                _api_error_message(endpoint_path, exc.code, error, message)
            ) from exc
        raise ShopeeCatalogError(
            _api_error_message(endpoint_path, exc.code, error, message)
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ShopeeCatalogError(f"Catalog API request failed at {endpoint_path}.") from exc
    decoded = _decode_mapping_or_none(raw)
    if decoded is None:
        raise _response_error(endpoint_path, "response was invalid")
    return decoded


def _response_dict(payload: Mapping[str, Any], *, endpoint_path: str) -> Mapping[str, Any]:
    response = payload.get("response")
    if not isinstance(response, Mapping):
        raise _response_error(endpoint_path, "response object was missing")
    return response


def _required_list(
    payload: Mapping[str, Any], *keys: str, endpoint_path: str
) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    raise _response_error(endpoint_path, f"required list was missing: {keys[0]}")


def _first_text(payload: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _positive_int(value: object, *, field_name: str = "category_id") -> int:
    parsed = _int_or_none(value)
    if parsed is None or parsed <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return parsed


def _nonnegative_int(value: object, *, field_name: str) -> int:
    parsed = _int_or_none(value)
    if parsed is None or parsed < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return parsed


def _normalize_category_id_list(category_ids: Sequence[int]) -> tuple[int, ...]:
    if isinstance(category_ids, (str, bytes)) or not isinstance(category_ids, Sequence):
        raise ValueError("category_ids must be a non-empty sequence")
    if not category_ids:
        raise ValueError("category_ids must not be empty")
    if len(category_ids) > _MAX_ATTRIBUTE_CATEGORY_IDS:
        raise ValueError("category_ids must contain at most 20 values")
    normalized = tuple(_positive_int(value) for value in category_ids)
    if len(set(normalized)) != len(normalized):
        raise ValueError("category_ids must not contain duplicates")
    return normalized


def _serialize_category_id_list(category_ids: Sequence[int]) -> str:
    """Serialize the documented int[] request value in caller-provided order."""

    return ",".join(str(category_id) for category_id in category_ids)


def _brand_status(value: object) -> int:
    status = _positive_int(value, field_name="status")
    if status not in _VALID_BRAND_STATUSES:
        raise ValueError("status must be a supported Shopee brand status")
    return status


def _decode_mapping_or_none(raw: bytes) -> Mapping[str, Any] | None:
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, Mapping) else None


def _safe_message(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    message = value.strip().replace("\r", " ").replace("\n", " ")
    if not message or len(message) > 240 or "://" in message or "?" in message:
        return None
    return message


def _api_error_message(
    endpoint_path: str,
    http_status: int | None,
    error: object,
    message: object,
) -> str:
    details = [f"Catalog API request failed at {endpoint_path}."]
    if http_status is not None:
        details.append(f"HTTP {http_status}.")
    if error:
        details.append(f"Shopee error: {error}.")
    safe_message = _safe_message(message)
    if safe_message:
        details.append(safe_message)
    return " ".join(details)


def _application_error(endpoint_path: str, error: object, message: object) -> ShopeeCatalogError:
    return ShopeeCatalogError(_api_error_message(endpoint_path, None, error, message))


def _response_error(endpoint_path: str, detail: str) -> ShopeeCatalogError:
    return ShopeeCatalogError(f"Catalog API response was invalid at {endpoint_path}: {detail}.")
