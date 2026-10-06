"""Country-neutral weapon-shape inspection using the existing PH transport.

This development adapter accepts only injected test transports. It has no
environment factory and does not select products or decide country compliance.
"""

from dataclasses import dataclass
import hashlib
import json
import re
import time
from uuid import uuid4

import requests

from modules.ph_image_safety_api import OpenAIImageAnalyzer


@dataclass(frozen=True)
class WeaponImageInspection:
    evaluation_id: str
    system_status: str
    ai_status: str | None
    note: str
    evidence_binding: str
    image_digests: tuple


class OfflineWeaponImageInspector:
    def __init__(self, *, api_key, api_session, image_session, sleep=time.sleep):
        if (api_session is None or image_session is None
                or isinstance(api_session, requests.Session) or isinstance(image_session, requests.Session)):
            raise ValueError("Explicit offline image/API test transports required")
        self._analyzer = OpenAIImageAnalyzer(api_key=api_key, enabled=True, session=api_session,
                                            image_session=image_session, sleep=sleep)

    def inspect(self, evidence):
        self._analyzer.preflight()
        if evidence.image_provider != "keepa" or evidence.guardrail_status != "SAFE":
            raise ValueError("Unsupported provider or existing Safety stop")
        if not evidence.image_urls:
            return self._seal(evidence, "ERROR" if evidence.image_capture_error else "UNAVAILABLE",
                              None, "確認できる商品画像がありません。", ())
        result = self._analyzer.analyze(evidence.image_urls, capture_error=evidence.image_capture_error)
        self._validate(result, evidence)
        status = "INDETERMINATE" if result["system_status"] == "PARTIAL" else result["ai_status"]
        digests = tuple((image["url"], image["status"], image["sha256"], image["mime"]) for image in result["images"])
        return self._seal(evidence, result["system_status"], status, result["note"], digests)

    @staticmethod
    def _seal(evidence, system_status, status, note, digests):
        binding = hashlib.sha256(json.dumps(
            [evidence.binding, system_status, status, note, digests, uuid4().hex], ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        return WeaponImageInspection(binding, system_status, status, note, evidence.binding, digests)

    @staticmethod
    def _validate(result, evidence):
        if not isinstance(result, dict) or set(result) != {"system_status", "ai_status", "note", "images", "attempts"}:
            raise ValueError("Invalid image inspection response")
        state, status = result["system_status"], result["ai_status"]
        if (state not in {"COMPLETED", "PARTIAL", "ERROR", "UNAVAILABLE"}
                or status not in {None, "NO_SIGNAL", "REVIEW", "INDETERMINATE"}
                or type(result["attempts"]) is not int or not 0 <= result["attempts"] <= 2
                or not isinstance(result["note"], str) or len(result["note"]) > 2000
                or not isinstance(result["images"], list)
                or any(not isinstance(image, dict) for image in result["images"])
                or [image.get("url") for image in result["images"]] != list(evidence.image_urls)):
            raise ValueError("Invalid image inspection status/binding")
        all_loaded = True
        for image in result["images"]:
            if set(image) != {"url", "status", "sha256", "mime"} or image["status"] not in {"LOADED", "ERROR", "UNAVAILABLE"}:
                raise ValueError("Invalid inspected image")
            if image["status"] == "LOADED":
                if (not isinstance(image["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", image["sha256"])
                        or image["mime"] not in {"image/jpeg", "image/png", "image/webp", "image/gif"}):
                    raise ValueError("Invalid loaded image digest/type")
            else:
                all_loaded = False
                if image["sha256"] or image["mime"]:
                    raise ValueError("Unavailable image has retained data")
        if (state == "COMPLETED" and (not all_loaded or evidence.image_capture_error or status is None)
                or state in {"ERROR", "UNAVAILABLE"} and status is not None
                or status is not None and result["attempts"] == 0
                or state == "PARTIAL" and all_loaded and not evidence.image_capture_error):
            raise ValueError("Image completion contradicts evidence")


class BudgetedLiveWeaponImageInspector(OfflineWeaponImageInspector):
    """Explicit live adapter; no environment factory or ordinary UI activation."""

    def __init__(self, *, api_key, budget, api_session=None, image_session=None):
        from modules.sg_live_validation import OpenAIValidationBudget, BudgetedOpenAISession
        if not isinstance(budget, OpenAIValidationBudget):
            raise ValueError("Explicit capped live budget required")
        self._analyzer = OpenAIImageAnalyzer(api_key=api_key, enabled=True,
            session=BudgetedOpenAISession(budget, session=api_session), image_session=image_session)
