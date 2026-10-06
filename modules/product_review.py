"""Weapon image inspection and targeted human decisions; no general product review."""

from dataclasses import dataclass
import hashlib
import json

from modules.image_inspection_policy import normalize_root, load_image_inspection_policy, select_image_inspection
from modules.guardrails import apply_guardrails
from modules.ph_image_safety import valid_image_url
from modules.product_text_safety import ProductTextSafetyFact, product_text_safety_fact_to_payload


@dataclass(frozen=True)
class ProductReviewEvidence:
    binding: str
    text: ProductTextSafetyFact
    image_urls: tuple[str, ...]
    image_capture_error: bool
    image_provider: str
    guardrail_status: str
    root_category_id: int | None = None


class WeaponImageReviewSession:
    """Keep weapon inspection evidence; never override unrelated Safety."""

    def __init__(self, marketplace: str):
        if marketplace not in {"PH", "SG"}:
            raise ValueError("Unsupported review marketplace")
        self.marketplace = marketplace
        self._evidence = {}
        self._decisions = {}
        self._inspections = {}

    def clear(self):
        self._evidence.clear()
        self._decisions.clear()
        self._inspections.clear()

    def invalidate(self, asin):
        self._evidence.pop(asin, None)
        self._decisions.pop(asin, None)
        self._inspections.pop(asin, None)

    def _identity(self, item):
        if item.marketplace != self.marketplace:
            raise ValueError("Review marketplace mismatch")
        return (item.marketplace, item.candidate_asin, item.source_asin, item.source_type,
                item.product_title, item.keepa_brand, item.keepa_category, item.resolver_input_title,
                item.input_safety_state)

    def supply(self, item, *, text: ProductTextSafetyFact, images: dict):
        identity = self._identity(item)
        self.invalidate(item.candidate_asin)
        payload = product_text_safety_fact_to_payload(text)
        urls = images.get("image_urls")
        if (text.candidate_asin != item.candidate_asin or images.get("candidate_asin") != item.candidate_asin
                or not isinstance(urls, (tuple, list)) or len(urls) > 3
                or any(not valid_image_url(url) for url in urls)
                or images.get("provider") not in {"keepa", "canopy_test"}
                or type(images.get("capture_error")) is not bool):
            raise ValueError("Product evidence identity/images invalid")
        row = {"candidate_asin": item.candidate_asin, "product_title": item.product_title,
               "brand": item.keepa_brand, "category": item.keepa_category,
               **{key: payload[key] for key in ("description", "features", "shortDescription", "safetyWarning", "itemHighlights")}}
        guarded = apply_guardrails((row,), marketplace=self.marketplace)[0]
        root = normalize_root(images.get("root_category_id"))
        binding = hashlib.sha256(json.dumps(
            [identity, payload, list(urls), images["capture_error"], images["provider"], root], ensure_ascii=False, sort_keys=True,
        ).encode()).hexdigest()
        self._evidence[item.candidate_asin] = (
            identity, ProductReviewEvidence(binding, text, tuple(urls), images["capture_error"], images["provider"], guarded["guardrail_status"], root),
        )

    def current(self, item):
        saved = self._evidence.get(item.candidate_asin)
        if saved is None or saved[0] != self._identity(item):
            return None
        # Re-evaluate current rule assets rather than trusting a previous SAFE.
        fact = saved[1]
        payload = product_text_safety_fact_to_payload(fact.text)
        row = {"candidate_asin": item.candidate_asin, "product_title": item.product_title,
               "brand": item.keepa_brand, "category": item.keepa_category,
               **{key: payload[key] for key in ("description", "features", "shortDescription", "safetyWarning", "itemHighlights")}}
        from dataclasses import replace
        return replace(fact, guardrail_status=apply_guardrails((row,), marketplace=self.marketplace)[0]["guardrail_status"])

    def image_selection(self, item):
        evidence = self.current(item)
        if evidence is None:
            raise ValueError("Current product evidence required")
        return select_image_inspection(marketplace=self.marketplace,
            root_category_id=evidence.root_category_id, provider=evidence.image_provider,
            guardrail_status=evidence.guardrail_status)

    def image_inspection_required(self, item):
        return self.image_selection(item) in {"TARGET_ROOT", "ROOT_UNKNOWN"}

    def policy_binding(self, item):
        return (load_image_inspection_policy(self.marketplace).digest, self.image_selection(item))

    def record_weapon_decision(self, item, *, decision: str, reviewed_images: bool, note: str):
        evidence = self.current(item)
        if (evidence is None or not self.image_inspection_required(item)
                or decision not in {"ALLOW_PREPARATION", "EXCLUDE"}
                or not isinstance(note, str) or not note.strip() or len(note) > 2000):
            raise ValueError("Current weapon inspection target and reason required")
        if decision == "ALLOW_PREPARATION" and (
            reviewed_images is not True or not evidence.image_urls
            or evidence.image_capture_error or evidence.guardrail_status != "SAFE"
            or evidence.text.provider != "keepa" or evidence.image_provider != "keepa"
            or item.input_safety_state != "GATE_ELIGIBLE"
            or self.current_image_inspection(item) is None
        ):
            raise ValueError("Missing evidence or existing Safety stop")
        inspection = self.current_image_inspection(item)
        self._decisions[item.candidate_asin] = (evidence.binding, decision, note.strip(),
                                               inspection.evaluation_id if inspection else None, self.policy_binding(item))

    def begin_image_inspection(self, item):
        self._decisions.pop(item.candidate_asin, None)
        self._inspections.pop(item.candidate_asin, None)
        evidence = self.current(item)
        if (evidence is None or evidence.guardrail_status != "SAFE" or item.input_safety_state != "GATE_ELIGIBLE"
                or self.image_selection(item) not in {"TARGET_ROOT", "ROOT_UNKNOWN"}):
            raise ValueError("Current eligible evidence required")
        return evidence

    def finish_image_inspection(self, item, *, evidence_binding, inspection):
        from modules.weapon_image_inspection import WeaponImageInspection
        evidence = self.current(item)
        if (evidence is None or evidence.binding != evidence_binding or evidence.guardrail_status != "SAFE"
                or not isinstance(inspection, WeaponImageInspection) or inspection.evidence_binding != evidence_binding):
            raise ValueError("Image inspection no longer matches current evidence")
        self._inspections[item.candidate_asin] = (evidence_binding, inspection, self.policy_binding(item))

    def current_image_inspection(self, item):
        evidence = self.current(item)
        saved = self._inspections.get(item.candidate_asin)
        return (saved[1] if evidence is not None and saved is not None
                and saved[0] == evidence.binding and saved[2] == self.policy_binding(item) else None)

    def preparation_blocker(self, item):
        """Match PH: non-target and completed NO_SIGNAL need no human decision."""
        if self.current(item) is None:
            return "武器画像検査の対象判定資料"
        selection = self.image_selection(item)
        if selection == "PROVIDER_UNSUPPORTED":
            return "武器画像検査の対応資料"
        if not self.image_inspection_required(item):
            return None
        decision = self.decision(item)
        if decision == "EXCLUDE":
            return "武器画像の人間確認で除外済み"
        if decision == "ALLOW_PREPARATION":
            return None
        inspection = self.current_image_inspection(item)
        if inspection is None:
            return "対象商品の武器画像AI検査"
        if inspection.system_status == "COMPLETED" and inspection.ai_status == "NO_SIGNAL":
            return None
        return "武器疑義・画像判断不能の確認"

    def clear_review_results(self):
        self._decisions.clear()
        self._inspections.clear()

    def decision(self, item):
        evidence = self.current(item)
        saved = self._decisions.get(item.candidate_asin)
        if evidence is None or saved is None or saved[0] != evidence.binding or saved[4] != self.policy_binding(item):
            return None
        if saved[1] == "ALLOW_PREPARATION" and (evidence.guardrail_status != "SAFE" or item.input_safety_state != "GATE_ELIGIBLE"):
            return None
        if saved[1] == "ALLOW_PREPARATION" and self.image_inspection_required(item):
            inspection = self.current_image_inspection(item)
            if inspection is None or inspection.evaluation_id != saved[3]:
                return None
        return saved[1]
