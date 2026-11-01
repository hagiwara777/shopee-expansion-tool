"""Read JP catalog facts for one Sora run. No listing writes or fallback providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Mapping

from dotenv import dotenv_values
import requests

from modules.amazon_data_provider import AmazonDataProviderError, SP_API_PROVIDER


JP_MARKETPLACE = "A1VC38T7YXB528"
CATALOG_URL = "https://sellingpartnerapi-fe.amazon.com/catalog/2022-04-01/items"
AUTH_URL = "https://api.amazon.com/auth/o2/token"
REQUIRED_FIELDS = ("SP_API_CLIENT_ID", "SP_API_CLIENT_SECRET", "SP_API_REFRESH_TOKEN")
ASIN_PATTERN = re.compile(r"[A-Z0-9]{10}\Z")


class SpApiCatalogError(AmazonDataProviderError):
    """Only sanitized, locally chosen error messages may reach the screen."""


@dataclass(frozen=True)
class SpApiCredentials:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    refresh_token: str = field(repr=False)


def load_sp_api_credentials(env_path: str | Path | None = None) -> SpApiCredentials:
    """Read the explicitly selected Sora file; never import FROMAX or process secrets."""
    selected = env_path or os.environ.get("SORA_SP_API_ENV")
    path = Path(selected) if selected else Path(__file__).resolve().parents[1] / ".env"
    try:
        if not path.is_file():
            raise OSError
        values = dotenv_values(path, interpolate=False, encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise SpApiCatalogError("Sora専用の設定ファイルを読み取れません。保存先を確認してください。") from None
    if any(not isinstance(values.get(key), str) or not values[key].strip() for key in REQUIRED_FIELDS):
        raise SpApiCatalogError("Sora専用のSP-API設定に必要な3項目がそろっていません。")
    return SpApiCredentials(*(values[key].strip() for key in REQUIRED_FIELDS))


def planned_catalog_calls(asins) -> int:
    return math.ceil(len(_unique_asins(asins)) / 20)


def _unique_asins(asins) -> list[str]:
    if isinstance(asins, (str, bytes)):
        raise SpApiCatalogError("ASINは一覧で指定してください。")
    unique = list(dict.fromkeys(str(value).strip().upper() for value in asins))
    if any(not ASIN_PATTERN.fullmatch(value) for value in unique):
        raise SpApiCatalogError("ASINの形式を確認してください。")
    if len(unique) > 100:
        raise SpApiCatalogError("1回の実行は100 ASINまでです。分けて実行してください。")
    return unique


class SpApiCatalogClient:
    provider_name = SP_API_PROVIDER
    verification_label = "SP_API_VERIFIED"
    not_found_label = "SP_API_NOT_FOUND"
    product_field_prefix = "spapi"

    def __init__(self, credentials: SpApiCredentials, *, transport=None, sleep=time.sleep,
                 monotonic=time.monotonic):
        self._credentials = credentials
        self._transport = transport if transport is not None else requests.Session()
        self._sleep = sleep
        self._monotonic = monotonic
        self.auth_calls = 0
        self.catalog_calls = 0
        self._used = False
        self._last_catalog_start = None

    def verify_products_by_asin(self, asins) -> dict[str, dict[str, Any]]:
        requested = _unique_asins(asins)
        if self._used:
            raise SpApiCatalogError("この実行の取得は終了しています。新しい実行から開始してください。")
        self._used = True
        if not requested:
            return {}
        # A run has exactly one authorization attempt and at most five catalog sends.
        self.auth_calls += 1
        payload = self._request("POST", AUTH_URL, data={
            "grant_type": "refresh_token", "client_id": self._credentials.client_id,
            "client_secret": self._credentials.client_secret,
            "refresh_token": self._credentials.refresh_token,
        })
        token = payload.get("access_token")
        if not isinstance(token, str) or not token.strip():
            raise SpApiCatalogError("Amazonの認証結果を確認できません。取得を停止しました。")
        products = {}
        try:
            for start in range(0, len(requested), 20):
                if self._last_catalog_start is not None:
                    self._sleep(max(0.0, 2.0 - (self._monotonic() - self._last_catalog_start)))
                batch = requested[start:start + 20]
                self._last_catalog_start = self._monotonic()
                self.catalog_calls += 1
                response = self._request("GET", CATALOG_URL,
                    headers={"x-amz-access-token": token}, params={
                        "marketplaceIds": JP_MARKETPLACE, "identifiersType": "ASIN",
                        "identifiers": ",".join(batch), "pageSize": 20,
                        "includedData": "attributes,summaries,classifications",
                        "locale": "ja_JP",
                    })
                items = response.get("items")
                if not isinstance(items, list) or response.get("pagination", {}).get("nextToken"):
                    raise SpApiCatalogError("Amazonの商品取得結果が想定形式と異なるため停止しました。")
                fetched_at = datetime.now(timezone.utc).isoformat()
                for item in items:
                    asin = item.get("asin") if isinstance(item, dict) else None
                    if asin not in batch or asin in products:
                        raise SpApiCatalogError("Amazonの商品取得結果のASINが一致しないため停止しました。")
                    products[asin] = normalize_catalog_item(item, fetched_at=fetched_at)
            return products
        finally:
            token = None
            # No persistent cache, token file, product DB, or cumulative ledger.

    def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = self._transport.request(method, url, timeout=(10, 45),
                                                allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise SpApiCatalogError("Amazonとの通信を完了できませんでした。自動再試行はしていません。") from None
        if response.status_code != 200:
            status = response.status_code
            reason = {400: "認証または入力内容", 401: "認証", 403: "権限または認証",
                      429: "呼び出し回数の上限"}.get(status, "Amazon側の応答")
            raise SpApiCatalogError(f"Amazonへの取得を停止しました（HTTP {status}：{reason}を確認）。")
        try:
            payload = response.json()
        except (ValueError, requests.RequestException):
            raise SpApiCatalogError("Amazonの応答を読み取れないため停止しました。") from None
        if not isinstance(payload, dict) or payload.get("errors"):
            raise SpApiCatalogError("Amazonがエラーを返したため停止しました。")
        return payload


def attribute_values(attributes: Mapping, name: str) -> tuple[str, ...]:
    """Keep JP values only; do not turn other locales or metadata into product text."""
    def strings(value):
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [text for item in value for text in strings(item)]
        if isinstance(value, dict) and value.get("marketplace_id", JP_MARKETPLACE) == JP_MARKETPLACE:
            return strings(value.get("value"))
        return []
    return tuple(dict.fromkeys(strings(attributes.get(name))))


def normalize_catalog_item(item: Mapping, *, fetched_at: str) -> dict[str, Any]:
    """Map Amazon facts to existing safety transports with their actual provider."""
    from modules.ingredient_safety import IngredientSafetyFact, ingredient_safety_fact_to_payload
    from modules.product_text_safety import ProductTextSafetyFact, product_text_safety_fact_to_payload

    asin = item.get("asin", "")
    attributes = item.get("attributes", {})
    if not isinstance(attributes, dict) or not ASIN_PATTERN.fullmatch(asin):
        raise SpApiCatalogError("Amazonの商品資料の形式が不正です。")
    summaries = [s for s in item.get("summaries", [])
                 if s.get("marketplaceId") == JP_MARKETPLACE]
    summary = summaries[0] if summaries else {}
    values = lambda name: attribute_values(attributes, name)
    first = lambda seq: next(iter(seq), "")
    ingredient_values = tuple(values(name) for name in
                              ("ingredients", "active_ingredients", "special_ingredients"))
    text_values = tuple(values(name) for name in
                       ("product_description", "bullet_point", "short_product_description", "safety_warning"))
    highlights = tuple(dict.fromkeys(text for name in
                       ("special_feature", "included_components", "directions", "power_source")
                       for text in values(name)))
    # Required alone does not establish inclusion. Keep that fact as REVIEW evidence.
    if _true_attribute(attributes, "batteries_included"):
        highlights += ("電池付属",)
    elif _true_attribute(attributes, "batteries_required"):
        highlights += ("電池を使用（同梱有無は未確認）",)
    ingredients = IngredientSafetyFact(asin, SP_API_PROVIDER,
        "CAPTURED" if any(ingredient_values) else "NOT_CAPTURED", *ingredient_values, fetched_at)
    text = ProductTextSafetyFact(asin, SP_API_PROVIDER,
        "CAPTURED" if any((*text_values, highlights)) else "NOT_AVAILABLE",
        *text_values, highlights, fetched_at)
    category = ""
    for group in item.get("classifications", []):
        if group.get("marketplaceId") != JP_MARKETPLACE:
            continue
        for node in group.get("classifications", []):
            names = []
            while isinstance(node, dict) and len(names) < 30:
                if node.get("displayName"):
                    names.append(str(node["displayName"]))
                node = node.get("parent")
            if names:
                category = " > ".join(reversed(names))
                break
        if category:
            break
    return {
        "asin": asin, "title": summary.get("itemName") or first(values("item_name")),
        "brand": summary.get("brand") or first(values("brand")),
        "category": category or summary.get("browseClassification", {}).get("displayName", ""),
        "fetched_at": fetched_at,
        "ingredient_safety_fact": ingredient_safety_fact_to_payload(ingredients),
        "product_text_safety_fact": product_text_safety_fact_to_payload(text),
    }


def _true_attribute(attributes: Mapping, name: str) -> bool:
    entries = attributes.get(name, [])
    if not isinstance(entries, list):
        raise SpApiCatalogError("Amazonの電池情報の形式が不正です。")
    return any(entry is True or (isinstance(entry, dict) and entry.get("value") is True
               and entry.get("marketplace_id", JP_MARKETPLACE) == JP_MARKETPLACE)
               for entry in entries)
