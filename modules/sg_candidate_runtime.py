"""Explicit, network-free SG candidate runtime. Never reads production data.

Replay inputs are development material, not proof of server provenance or live
acceptance. Raw responses still pass the existing strict SG/API contracts.
"""

from base64 import b64decode
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urlsplit

from modules.category_ai_core import CategoryAIEngine, CategoryAIError, content_hash, parse_step_result
from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
from modules.category_mapper_store import CategoryMapperStore, default_category_mapper_db_path
from modules.ph_image_safety import valid_image_url
from modules.shopee_catalog_client import ShopeeCatalogClient, ShopeeCatalogCredentials
from modules.weapon_image_inspection import OfflineWeaponImageInspector


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate replay key")
        result[key] = value
    return result


class SGReplayBundle:
    """Responses keyed by exact request; no credentials, network or fallback."""

    def __init__(self, content):
        if not isinstance(content, bytes) or not content or len(content) > 10 * 1024 * 1024:
            raise ValueError("Replay bundle size/type invalid")
        data = json.loads(content.decode("utf-8-sig"), object_pairs_hook=_unique_keys)
        if (not isinstance(data, dict) or set(data) != {
                "schema", "marketplace", "shop_id", "catalog_responses",
                "category_predictions", "images", "image_predictions"}
                or data["schema"] not in {"SG_OFFLINE_REPLAY_V1", "SG_OFFLINE_REPLAY_V2"} or data["marketplace"] != "SG"
                or type(data["shop_id"]) is not int or data["shop_id"] <= 0
                or any(not isinstance(data[key], dict) for key in (
                    "catalog_responses", "category_predictions", "images", "image_predictions"))):
            raise ValueError("SG replay schema/binding invalid")
        for url, encoded in data["images"].items():
            if not valid_image_url(url) or not isinstance(encoded, str):
                raise ValueError("Invalid replay image")
            raw = b64decode(encoded, validate=True)
            if not raw or len(raw) > 5 * 1024 * 1024:
                raise ValueError("Invalid replay image size")
        self._data = data
        self.shop_id = data["shop_id"]

    def catalog_request(self, url, query, timeout):
        parsed = urlsplit(url)
        if query.get("shop_id") != str(self.shop_id):
            raise ValueError("Replay shop mismatch")
        if parsed.path == "/api/v2/product/get_brand_list":
            key = f"brand:{query['category_id']}:{query['offset']}"
        elif parsed.path == "/api/v2/product/get_attribute_tree":
            key = f"attribute:{query['category_id_list']}"
        else:
            raise ValueError("Unsupported replay endpoint")
        # Missing responses fail; never synthesize empty catalogs or No Brand.
        return deepcopy(self._data["catalog_responses"][key])

    @property
    def has_image_replay(self):
        return bool(self._data["image_predictions"])

    def category_engine(self):
        if self._data["schema"] == "SG_OFFLINE_REPLAY_V2" and self._data["category_predictions"]:
            from modules.category_ai_leaf_search import LeafSearchEngine
            return LeafSearchEngine(_ReplayCategoryProvider(self))
        return CategoryAIEngine(_ReplayCategoryProvider(self)) if self._data["category_predictions"] else None

    def image_inspector(self):
        if not self.has_image_replay:
            return None
        return OfflineWeaponImageInspector(api_key="offline-replay", api_session=_ReplayImageAPI(self),
                                           image_session=_ReplayImages(self), sleep=lambda delay: None)


class _ReplayCategoryProvider:
    name = "offline_replay"

    def __init__(self, bundle):
        self.bundle = bundle

    def select(self, request, profile):
        key = content_hash([request.user_input(), profile.to_dict()])
        result = self.bundle._data["category_predictions"].get(key)
        if result is None:
            raise CategoryAIError("OFFLINE_REPLAY_MISSING")
        data = deepcopy(result)
        understood = None
        if self.bundle._data["schema"] == "SG_OFFLINE_REPLAY_V2":
            from modules.category_ai_leaf_search import VERSION
            from modules.category_ai_prompts import PROMPT_VERSION
            understood = data.pop("product_understood", None)
            if type(understood) is not bool or data.get("prompt_version") != VERSION:
                raise CategoryAIError("OFFLINE_REPLAY_V2_CONTRACT_INVALID")
            data["prompt_version"] = PROMPT_VERSION
        parsed = parse_step_result(data,
                                 allowed_category_ids={node.category_id for node in request.candidates},
                                 api_call_count=0)
        if understood is not None:
            from dataclasses import fields
            from modules.category_ai_core import StepResult
            from modules.category_ai_leaf_search import LeafResult
            return LeafResult(**{f.name: getattr(parsed, f.name) for f in fields(StepResult)}, product_understood=understood)
        return parsed


class _ReplayResponse:
    def __init__(self, *, raw=b"", body=None, status=200):
        self.status_code = status
        self._raw, self._body = raw, body

    def json(self):
        return deepcopy(self._body)

    def iter_content(self, chunk_size):
        yield self._raw

    def close(self):
        self._raw = b""


class _ReplayImages:
    def __init__(self, bundle):
        self.bundle = bundle

    def get(self, url, **kwargs):
        value = self.bundle._data["images"].get(url)
        return (_ReplayResponse(raw=b64decode(value, validate=True)) if value is not None
                else _ReplayResponse(status=404))


class _ReplayImageAPI:
    def __init__(self, bundle):
        self.bundle = bundle

    def post(self, url, **kwargs):
        from modules.ph_image_safety_api import RESPONSES_URL
        if url != RESPONSES_URL:
            raise ValueError("Unexpected replay endpoint")
        key = content_hash(kwargs["json"])
        if key not in self.bundle._data["image_predictions"]:
            raise ValueError("Image request does not match replay")
        return _ReplayResponse(body=self.bundle._data["image_predictions"][key])


def create_sg_candidate_workflow(bundle, *, db_path):
    """Only a NEW isolated database; no cloning, migration or production opens."""
    path = Path(db_path).resolve()
    if path == default_category_mapper_db_path().resolve() or path.exists():
        raise ValueError("New isolated candidate database required")
    store = CategoryMapperStore(path)
    store.initialize_sg_brand_acceptance()
    client = ShopeeCatalogClient(ShopeeCatalogCredentials(1, "", bundle.shop_id, ""),
                                 marketplace="SG", request_json=bundle.catalog_request)
    return SGBrandWorkflow(store=store, client=client, image_inspector=bundle.image_inspector())
