"""Read existing SHA-bound raw evidence for isolated SG human review, offline."""

from copy import deepcopy

from modules.category_mapper_sg import parse_sg_category_mapper_input
from modules.ph_image_safety import parse_image_sidecar
from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
from modules.product_text_safety import parse_product_text_safety_sidecar


class SGProductEvidenceLoader:
    """Only raw facts cross markets; PH evaluation and human decisions never do.

    SHA binding detects a different Candidate file, not authenticity of uploads.
    The Gate CSV has no original Candidate digest; compare its available product
    fields without claiming cryptographic provenance for the Gate decision.
    """

    def __init__(self, *, candidate_content, text_content, image_content,
                 gate_content, gate_filename):
        for content in (candidate_content, text_content, image_content, gate_content):
            if not isinstance(content, bytes) or not content or len(content) > 10 * 1024 * 1024:
                raise ValueError("Evidence file size/type invalid")
        candidates = parse_prelisting_candidate_csv(candidate_content, filename="candidate.csv")
        text = parse_product_text_safety_sidecar(
            text_content, filename="product_text.csv", candidate_content=candidate_content,
            candidates=candidates,
        )
        images = parse_image_sidecar(image_content, candidate_content=candidate_content, candidates=candidates)
        # This legacy container also carries PH decisions. Accept only raw rows.
        if any(row["evaluation"] is not None or row["human"] is not None for row in images["rows"]):
            raise ValueError("PH image decisions cannot be imported into SG review")
        gate = parse_sg_category_mapper_input(gate_content, filename=gate_filename)
        original = {row.candidate_asin: row for row in candidates.rows}
        self._gate_rows = {row.candidate_asin: row for row in gate.rows}
        self._text = text.facts_by_asin
        self._images = {row["fact"]["candidate_asin"]: deepcopy(row["fact"]) for row in images["rows"]}
        for row in gate.rows:
            candidate = original.get(row.candidate_asin)
            if candidate is None or self._candidate_identity(candidate) != self._gate_identity(row):
                raise ValueError("SG Gate product does not match original Candidate")
        for candidate in candidates.rows:
            if self._text[candidate.candidate_asin].provider != self._images[candidate.candidate_asin]["provider"]:
                raise ValueError("Text/image evidence provider mismatch")

    @staticmethod
    def _candidate_identity(row):
        return (row.source_type, row.source_asin, row.product_title, row.brand, row.category, row.input_title)

    @staticmethod
    def _gate_identity(row):
        return (row.source_type, row.source_asin, row.product_title, row.keepa_brand, row.keepa_category, row.input_title)

    def __call__(self, item):
        row = self._gate_rows.get(item.candidate_asin)
        if (item.marketplace != "SG" or item.input_safety_state != "GATE_ELIGIBLE" or row is None
                or (item.source_type, item.source_asin, item.product_title, item.keepa_brand, item.keepa_category)
                != self._gate_identity(row)[:5]):
            raise ValueError("Current SG product does not match loaded evidence")
        return self._text[item.candidate_asin], deepcopy(self._images[item.candidate_asin])
