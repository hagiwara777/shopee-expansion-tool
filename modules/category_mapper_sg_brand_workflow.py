"""Explicit offline Brand acquisition/confirmation session for SG development."""

from __future__ import annotations

from modules.category_mapper_sg import (
    SGBrandSession, SGBrandSyncResult, SGMapperRecommendation, SGCategoryMapperError,
    _require_sg_brand_product, sync_sg_brand_catalog_offline,
)
from modules.category_mapper_store import CategoryMapperStore
from modules.shopee_catalog_client import ShopeeCatalogClient
from modules.category_mapper import AttributeFlattenResult, flatten_attribute_tree
from modules.product_review import WeaponImageReviewSession


class SGBrandWorkflow:
    """Inject an isolated DB and offline client; never discover credentials.

    Acquisition happens only on an explicit action. Input changes invalidate
    acquired Category catalogs, even when timestamps or Brand names are unchanged.
    """

    def __init__(self, *, store: CategoryMapperStore, client: ShopeeCatalogClient, product_evidence_loader=None,
                 image_inspector=None, live_validation_scope=None) -> None:
        store._require_sg_brand_acceptance()
        from modules.sg_live_validation import SGLiveValidationScope
        if live_validation_scope is not None:
            if not isinstance(live_validation_scope, SGLiveValidationScope):
                raise ValueError("Explicit limited SG validation scope required")
            live_validation_scope.require_client(client, store)
        if client.marketplace != "SG" or client.uses_default_transport and live_validation_scope is None:
            raise ValueError("SG development workflow requires an offline SG client.")
        self._live_scope = live_validation_scope
        self.store = store
        self._client = client
        self.session = SGBrandSession(marketplace="SG", shop_id=client.credentials.shop_id)
        self._input_bound = False
        self._input_fingerprint: str | None = None
        self._acquired_categories: set[int] = set()
        self._attributes: dict[int, tuple[str, AttributeFlattenResult]] = {}
        from modules.weapon_image_inspection import OfflineWeaponImageInspector, BudgetedLiveWeaponImageInspector
        if image_inspector is not None and not isinstance(image_inspector, OfflineWeaponImageInspector):
            raise ValueError("Explicit offline image inspector required")
        if isinstance(image_inspector, BudgetedLiveWeaponImageInspector) and self._live_scope is None:
            raise ValueError("Live image adapter requires limited SG live scope")
        self._image_inspector = image_inspector
        self._image_system_error = False
        self.product_review = WeaponImageReviewSession("SG")
        self._product_evidence_loader = product_evidence_loader
        self._evidence_files_bound = False
        self._evidence_files_fingerprint = None

    def bind_input(self, fingerprint: str | None) -> None:
        if self._input_bound and fingerprint != self._input_fingerprint:
            for category_id in self._acquired_categories:
                self.session.invalidate(category_id)
            self._acquired_categories.clear()
            self._attributes.clear()
            self.product_review.clear()
        self._input_fingerprint = fingerprint
        self._input_bound = True

    def require_catalog_current(self):
        if getattr(self._client,"catalog_refresh_failed",False):
            raise ValueError("Successful current SG catalog acquisition required")

    def fetch(self, item: SGMapperRecommendation) -> SGBrandSyncResult:
        self.require_catalog_current()
        if self._live_scope is not None:
            self._live_scope.require_product(item)
        category_id = _require_sg_brand_product(item, self.store)
        self._acquired_categories.add(category_id)
        if self._live_scope is not None:
            from modules.category_mapper_sg import sync_sg_brand_catalog_live_validation
            return sync_sg_brand_catalog_live_validation(client=self._client, session=self.session,
                store=self.store, confirmed_category_id=category_id, scope=self._live_scope)
        return sync_sg_brand_catalog_offline(
            client=self._client, session=self.session, store=self.store,
            confirmed_category_id=category_id,
        )

    def fetch_attributes(self, item: SGMapperRecommendation) -> AttributeFlattenResult:
        self.require_catalog_current()
        if self._live_scope is not None:
            self._live_scope.require_product(item)
            self._live_scope.require_client(self._client, self.store)
        category_id = _require_sg_brand_product(item, self.store)
        self._attributes.pop(category_id, None)
        if (self._client.marketplace != "SG" or self._client.uses_default_transport and self._live_scope is None
                or self._client.credentials.shop_id != self.session.shop_id):
            raise ValueError("Offline attribute client binding changed.")
        tree = self._client.get_attribute_tree("SG", category_id)
        result = flatten_attribute_tree(tree)
        if result.depth_limited or result.skipped_node_count:
            raise ValueError("Attribute tree could not be fully read.")
        # Check the current Category again before retaining a response.
        _require_sg_brand_product(item, self.store)
        self._attributes[category_id] = (item.recommended_category_path, result)
        return result

    def current_attributes(self, item: SGMapperRecommendation) -> AttributeFlattenResult | None:
        try:
            category_id = _require_sg_brand_product(item, self.store)
        except (SGCategoryMapperError, ValueError):
            return None
        saved = self._attributes.get(category_id)
        return saved[1] if saved is not None and saved[0] == item.recommended_category_path else None

    @property
    def can_load_product_evidence(self):
        return self._product_evidence_loader is not None

    def bind_product_evidence_files(self, fingerprint):
        """Changing/removing any uploaded evidence invalidates its human review."""
        if not self._evidence_files_bound and fingerprint is None:
            return
        if not self._evidence_files_bound or fingerprint != self._evidence_files_fingerprint:
            self.product_review.clear()
            self._product_evidence_loader = None
        self._evidence_files_bound = True
        self._evidence_files_fingerprint = fingerprint

    def install_product_evidence_loader(self, loader):
        self.clear_product_evidence_loader()
        from modules.product_review_transport import SGProductEvidenceLoader
        if not self._evidence_files_bound or not isinstance(loader, SGProductEvidenceLoader):
            raise ValueError("Explicitly bound SG evidence files required")
        self._product_evidence_loader = loader

    def clear_product_evidence_loader(self):
        self.product_review.clear()
        self._product_evidence_loader = None

    def load_product_evidence(self, item):
        if self._live_scope is not None:
            self._live_scope.require_product(item)
        self.product_review.invalidate(item.candidate_asin)
        if self._product_evidence_loader is None:
            raise ValueError("Offline evidence loader not supplied")
        text, images = self._product_evidence_loader(item)
        self.product_review.supply(item, text=text, images=images)

    @property
    def can_inspect_images(self):
        return self._image_inspector is not None

    def require_image_system_current(self):
        if self._image_system_error:
            raise ValueError("Image inspection system requires explicit successful recheck")

    def inspect_product_images(self, item):
        if self._live_scope is not None:
            self._live_scope.require_product(item)
        if self._image_inspector is None:
            raise ValueError("Offline image inspector not supplied")
        evidence = self.product_review.begin_image_inspection(item)
        try:
            inspection = self._image_inspector.inspect(evidence)
            self.product_review.finish_image_inspection(item, evidence_binding=evidence.binding, inspection=inspection)
        except Exception:
            self.product_review.clear_review_results()
            self._image_system_error = True
            raise
        self._image_system_error = False
        return inspection

    def image_inspection_targets(self, items):
        """SG development selection: common selector with SG country settings.

        No country compliance inference is made. Missing
        images remain targets so their UNAVAILABLE result cannot become NO_SIGNAL.
        This method performs no acquisition and never adopts a human decision.
        """
        items = tuple(items)
        if (any(item.marketplace != "SG" for item in items)
                or len({item.candidate_asin for item in items}) != len(items)):
            raise ValueError("Unique SG image batch required")
        targets = []
        for item in items:
            evidence = self.product_review.current(item)
            if (evidence is not None and item.input_safety_state == "GATE_ELIGIBLE"
                    and evidence.guardrail_status == "SAFE"
                    and evidence.image_provider == evidence.text.provider == "keepa"
                    and self.product_review.image_selection(item) in {"TARGET_ROOT", "ROOT_UNKNOWN"}):
                targets.append(item)
        return tuple(targets)

    def inspect_image_batch(self, items):
        targets = self.image_inspection_targets(items)
        if not self.can_inspect_images or not targets:
            raise ValueError("Explicit inspector and current SG targets required")
        # Invalidate the whole batch BEFORE the first request. A failure midway
        # must not leave the unprocessed items carrying earlier human approvals.
        for item in targets:
            self.product_review.begin_image_inspection(item)
        return tuple(self.inspect_product_images(item) for item in targets)
