"""Fixed Expansion artifacts in one session; no provider, DB or Safety decisions."""
from dataclasses import dataclass

from modules.ingredient_safety import parse_ingredient_safety_sidecar
from modules.product_text_safety import parse_product_text_safety_sidecar
from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
from modules.ph_image_safety import parse_image_sidecar
from modules.prelisting_sg_body_safety import (
    SGBodySafetyError, body_checks, parse_body_confirmations,
    prepare_body_confirmations, record_body_confirmation,
)

MANUAL = "CSVをアップロード"
INTERNAL = "Expansionの生成結果を使う"
PACKET_KEY = "expansion_gate_packet"
GENERATION_KEY = "expansion_gate_generation"
SOURCE_KEY = "prelisting_gate_input_source"
BODY_CACHE_KEY = "prelisting_gate_bound_sg_confirmations"


class HandoffError(ValueError):
    """An incomplete, stale or cross-market handoff cannot be used."""


@dataclass(frozen=True)
class Artifact:
    name: str
    content: bytes

    def getvalue(self):
        return self.content


@dataclass(frozen=True)
class ExpansionPacket:
    marketplace: str
    generation: str
    source_asin: str
    candidate: Artifact
    ingredient: Artifact
    product_text: Artifact
    image: Artifact


def validate_packet(packet, *, marketplace, generation):
    """Keep the downloaded bytes, and use the existing four file validators."""
    if (not isinstance(packet, ExpansionPacket) or marketplace not in {"PH", "SG"}
            or packet.marketplace != marketplace or not generation
            or packet.generation != generation or not packet.source_asin):
        raise HandoffError("現在の対象国・生成結果との対応を確認できません。")
    for artifact in (packet.candidate, packet.ingredient, packet.product_text, packet.image):
        if (not isinstance(artifact, Artifact) or not isinstance(artifact.name, str)
                or not artifact.name.strip() or not isinstance(artifact.content, bytes)
                or not artifact.content):
            raise HandoffError("候補と関連Safety資料が一式揃っていません。")
    raw = packet.candidate.content
    candidates = parse_prelisting_candidate_csv(raw, filename=packet.candidate.name)
    if (candidates.source_type != "EXPANSION"
            or any(row.source_asin != packet.source_asin for row in candidates.rows)):
        raise HandoffError("Expansionの起点商品と一致しません。")
    parse_ingredient_safety_sidecar(packet.ingredient.content, filename=packet.ingredient.name,
                                  candidate_content=raw, candidates=candidates)
    parse_product_text_safety_sidecar(packet.product_text.content, filename=packet.product_text.name,
                                    candidate_content=raw, candidates=candidates)
    parse_image_sidecar(packet.image.content, candidate_content=raw, candidates=candidates)
    return candidates


def current_body_confirmations(candidates, product_text, uploaded, cache):
    """Reuse only existing validator bindings, independently of upload filenames.

    Retain confirmed records through temporarily incomplete input and source
    switches. A changed context gets no old confirmation. A previously confirmed
    body whose current name/text no longer raises the question stops the input,
    rather than silently becoming eligible after a Fact change.
    """
    fresh = prepare_body_confirmations(candidates, product_text)
    binding = fresh["context_sha256"]
    current = prepare_body_confirmations(candidates, product_text, cache.get(binding))
    if uploaded is not None:
        incoming = parse_body_confirmations(uploaded, candidates, product_text)
        for record in incoming["records"]:
            current = record_body_confirmation(candidates, product_text, current,
                                               asin=record["candidate_asin"], family=record["family"],
                                               outcome=record["outcome"],
                                               evidence_reviewed=record["evidence_reviewed"], note=record["note"])
    asins = {row.candidate_asin for row in candidates.rows}
    questions = {(c["candidate_asin"], c["family"]) for c in body_checks(candidates, product_text, current)}
    for previous in cache.values():
        for record in previous["records"]:
            key = (record["candidate_asin"], record["family"])
            if (record["outcome"] == "BODY_PRESENT" and record["candidate_asin"] in asins
                    and key not in questions):
                raise SGBodySafetyError("確認済み本体と変更後の商品情報との対応を確認できません。")
    return current


def remember_body_confirmations(state, confirmations):
    # Called only for confirmations already validated by the existing SG core.
    if confirmations is not None and confirmations["records"]:
        cache = dict(state.get(BODY_CACHE_KEY, {}))
        cache[confirmations["context_sha256"]] = confirmations
        state[BODY_CACHE_KEY] = cache
