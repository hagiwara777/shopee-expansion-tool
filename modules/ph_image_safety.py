"""Dedicated PH image Safety contract and fail-closed gate overlay (DEC-0051/53/54).

No network or image bytes are retained here. Candidate V1 stays unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import re
import uuid
from typing import Any, Mapping

SCHEMA = "PH_IMAGE_SAFETY_V1"
PROMPT_VERSION = "PH_WEAPON_IMAGE_V1"
MODEL = "gpt-5.6-terra"
TARGET_ROOTS = frozenset({13299531, 2277721051, 14304371, 2016929051})
MAX_IMAGES = 3
IMAGE_REASON_CODES = ("IMAGE_SAFETY_REVIEW", "IMAGE_SAFETY_EXCLUDE")
SEMANTIC_RESULTS = frozenset({"NO_SIGNAL", "REVIEW", "INDETERMINATE"})
SKIP_SELECTORS = frozenset({"OTHER_ROOT", "EXISTING_BLOCK", "PROVIDER_UNSUPPORTED"})
SELECTORS = SKIP_SELECTORS | {"TARGET_ROOT", "ROOT_UNKNOWN"}
SYSTEM_STATES = frozenset({"NOT_RUN", "COMPLETED", "UNAVAILABLE", "ERROR", "PARTIAL"})
_IMAGE_URL = re.compile(
    r"https://m\.media-amazon\.com/images/I/[A-Za-z0-9][A-Za-z0-9+_.%-]{0,250}\.(?:jpg|jpeg|png|webp|gif)"
)
_HASH = re.compile(r"[a-f0-9]{64}")
_ASIN = re.compile(r"[A-Z0-9]{10}")


class ImageSafetyError(RuntimeError):
    """An untrusted contract or whole-system failure: stop the gate."""


def normalize_root(value: Any) -> int | None:
    if type(value) is int and 0 < value <= 2**63 - 1:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,19}", value.strip()):
        return normalize_root(int(value.strip()))
    return None


def valid_image_url(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(_IMAGE_URL.fullmatch(value))
        and "%" not in value
        and ".." not in value
    )


def capture_keepa_image_fact(
    product: Any, *, candidate_asin: str, root_category_id: Any
) -> dict:
    """Read current images, or absent-field legacy imagesCSV, without fetching."""
    missing = object()
    images = (
        product.get("images", missing)
        if isinstance(product, Mapping)
        else getattr(product, "images", missing)
    )
    error = False
    tokens = []
    if images is missing:
        raw = (
            product.get("imagesCSV")
            if isinstance(product, Mapping)
            else getattr(product, "imagesCSV", None)
        )
        error = raw is not None and not isinstance(raw, str)
        tokens = (
            list(dict.fromkeys(x.strip() for x in raw.split(",") if x.strip()))[:MAX_IMAGES]
            if isinstance(raw, str)
            else []
        )
    elif not isinstance(images, list):
        error = True
    else:
        for entry in images:
            if not isinstance(entry, Mapping):
                error = True
                continue
            token = entry.get("l")
            if token is None or token == "":
                token = entry.get("m")
            if not isinstance(token, str):
                error = True
                continue
            tokens.append(token)
    urls = []
    for token in tokens:
        url = "https://m.media-amazon.com/images/I/" + token
        if valid_image_url(url):
            if url not in urls and len(urls) < MAX_IMAGES:
                urls.append(url)
        else:
            error = True
    return {
        "candidate_asin": candidate_asin,
        "provider": "keepa",
        "root_category_id": normalize_root(root_category_id),
        "image_urls": urls,
        "capture_error": error,
    }


def image_fact_from_product(
    product: Any, *, candidate_asin: str, provider: str = "keepa"
) -> dict:
    if provider not in {"keepa", "canopy_test"}:
        raise ImageSafetyError("画像情報providerが不正です。")
    product = product if isinstance(product, Mapping) else {}
    payload = product.get("ph_image_safety_fact")
    if payload is not None:
        fact = deepcopy(payload)
        _validate_fact(fact)
        if fact["candidate_asin"] != candidate_asin or fact["provider"] != provider:
            raise ImageSafetyError("画像情報のASIN/providerが一致しません。")
        return fact
    # Legacy cache has no images marker: preserve known root, never fetch extra.
    fact = {
        "candidate_asin": candidate_asin,
        "provider": provider,
        "root_category_id": normalize_root(product.get("root_category_id"))
        if provider == "keepa"
        else None,
        "image_urls": [],
        "capture_error": False,
    }
    _validate_fact(fact)
    return fact


def select_images(fact: dict, guardrail_status: str) -> str:
    _validate_fact(fact)
    if guardrail_status not in {"SAFE", "REVIEW", "BLOCK"}:
        raise ImageSafetyError("既存Safety状態が不正です。")
    if guardrail_status == "BLOCK":
        return "EXISTING_BLOCK"
    if fact["provider"] == "canopy_test":
        return "PROVIDER_UNSUPPORTED"
    if fact["root_category_id"] is None:
        return "ROOT_UNKNOWN"
    return "TARGET_ROOT" if fact["root_category_id"] in TARGET_ROOTS else "OTHER_ROOT"


def create_image_sidecar(
    candidate_content: bytes, candidate_rows, source_rows
) -> bytes:
    candidates = _bound_candidates(candidate_content, candidate_rows)
    sources = {}
    for source in source_rows:
        asin = (
            str(source.get("candidate_asin") or source.get("asin") or "")
            .strip()
            .upper()
        )
        if asin in sources and source != sources[asin]:
            raise ImageSafetyError("画像情報の元行が重複しています。")
        sources[asin] = source
    rows = []
    for candidate in candidates:
        asin = candidate.candidate_asin
        if asin not in sources:
            raise ImageSafetyError("候補に対応する画像情報がありません。")
        provider = _candidate_provider(candidate)
        fact = image_fact_from_product(
            sources[asin], candidate_asin=asin, provider=provider
        )
        rows.append({"fact": fact, "evaluation": None, "human": None})
    result = {
        "schema_version": SCHEMA,
        "candidate_schema_version": "PRELISTING_CANDIDATE_V1",
        "candidate_sha256": _sha(candidate_content),
        "rows": rows,
    }
    validate_image_sidecar(result, candidate_content, candidates)
    return image_sidecar_bytes(result)


def parse_image_sidecar(
    content: bytes, *, candidate_content: bytes, candidates
) -> dict:
    if not isinstance(content, bytes) or len(content) > 10 * 1024 * 1024:
        raise ImageSafetyError("画像確認ファイルのサイズまたは型が不正です。")
    try:
        result = json.loads(
            content.decode("utf-8-sig"), object_pairs_hook=_unique_object
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ImageSafetyError("画像確認ファイルのJSONが不正です。") from exc
    validate_image_sidecar(result, candidate_content, candidates.rows)
    return result


def image_sidecar_bytes(sidecar: dict) -> bytes:
    return json.dumps(
        sidecar, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ).encode("utf-8")


def validate_image_sidecar(
    sidecar: dict, candidate_content: bytes, candidate_rows
) -> None:
    try:
        _validate_image_sidecar(sidecar, candidate_content, candidate_rows)
    except ImageSafetyError:
        raise
    except (TypeError, ValueError, KeyError, RecursionError) as exc:
        raise ImageSafetyError("画像確認ファイルの値が不正です。") from exc


def _validate_image_sidecar(
    sidecar: dict, candidate_content: bytes, candidate_rows
) -> None:
    candidates = _bound_candidates(candidate_content, candidate_rows)
    _keys(
        sidecar,
        {"schema_version", "candidate_schema_version", "candidate_sha256", "rows"},
    )
    if (
        sidecar["schema_version"] != SCHEMA
        or sidecar["candidate_schema_version"] != "PRELISTING_CANDIDATE_V1"
    ):
        raise ImageSafetyError("画像確認ファイルのschemaが不正です。")
    if sidecar["candidate_sha256"] != _sha(candidate_content):
        raise ImageSafetyError("画像確認ファイルのCandidate SHAが一致しません。")
    if not isinstance(sidecar["rows"], list) or len(sidecar["rows"]) != len(candidates):
        raise ImageSafetyError("画像確認ファイルのASIN集合が一致しません。")
    candidate_map = {c.candidate_asin: c for c in candidates}
    seen = set()
    for row in sidecar["rows"]:
        _keys(row, {"fact", "evaluation", "human"})
        _validate_fact(row["fact"])
        asin = row["fact"]["candidate_asin"]
        if (
            asin in seen
            or asin not in candidate_map
            or row["fact"]["provider"] != _candidate_provider(candidate_map[asin])
        ):
            raise ImageSafetyError("画像確認ファイルのASIN/providerが一致しません。")
        seen.add(asin)
        evaluation = row["evaluation"]
        if evaluation is None:
            if row["human"] is not None:
                raise ImageSafetyError("画像評価なしの人間判断は使用できません。")
            continue
        _validate_evaluation(row, sidecar["candidate_sha256"])
        if row["human"] is not None:
            _validate_human(row, sidecar["candidate_sha256"])


def prepare_image_safety(base_result, sidecar: dict, candidate_content: bytes) -> dict:
    """Apply selector after existing Safety. No network; targets await explicit run."""
    _validate_base(base_result, sidecar, candidate_content)
    result = deepcopy(sidecar)
    base_by_asin = {r.candidate.candidate_asin: r for r in base_result.rows}
    for row in result["rows"]:
        base = base_by_asin[row["fact"]["candidate_asin"]]
        selector = select_images(row["fact"], base.guardrail_status)
        old = row["evaluation"]
        if old is not None:
            if (
                old["selector"] != selector
                or old["base_guardrail_status"] != base.guardrail_status
            ):
                raise ImageSafetyError("既存Safetyが変わりました。元の画像情報ファイルから再確認してください。")
            continue
        state = "NOT_RUN"
        if selector not in SKIP_SELECTORS and not row["fact"]["image_urls"]:
            state = "ERROR" if row["fact"]["capture_error"] else "UNAVAILABLE"
        evaluation = {
            "selector": selector,
            "base_guardrail_status": base.guardrail_status,
            "system_status": state,
            "ai_status": None,
            "note": "",
            "images": [],
            "provider": "",
            "model": "",
            "prompt_version": PROMPT_VERSION,
            "attempts": 0,
            "run_id": uuid.uuid4().hex,
        }
        _seal(row, evaluation, result["candidate_sha256"])
    validate_image_sidecar(
        result, candidate_content, [r.candidate for r in base_result.rows]
    )
    return result


def run_image_safety(
    base_result, sidecar: dict, candidate_content: bytes, *, analyzer
) -> dict:
    """Run only pending target products. A global error returns no partial result."""
    result = prepare_image_safety(base_result, sidecar, candidate_content)
    pending = [
        r
        for r in result["rows"]
        if r["evaluation"]["selector"] not in SKIP_SELECTORS
        and r["evaluation"]["system_status"] == "NOT_RUN"
        and r["human"] is None
    ]
    if pending:
        analyzer.preflight()
    for row in pending:
        response = analyzer.analyze(
            tuple(row["fact"]["image_urls"]), capture_error=row["fact"]["capture_error"]
        )
        _keys(response, {"system_status", "ai_status", "note", "images", "attempts"})
        evaluation = {
            k: v for k, v in row["evaluation"].items() if k != "evaluation_id"
        }
        evaluation.update(response)
        evaluation.update(
            provider="OpenAI" if response["attempts"] else "",
            model=MODEL if response["attempts"] else "",
            run_id=uuid.uuid4().hex,
        )
        _seal(row, evaluation, result["candidate_sha256"])
    validate_image_sidecar(
        result, candidate_content, [r.candidate for r in base_result.rows]
    )
    return result


def record_human_decision(
    base_result,
    sidecar: dict,
    candidate_content: bytes,
    *,
    asin: str,
    decision: str,
    reviewed_images: bool,
    note: str,
) -> dict:
    result = prepare_image_safety(base_result, sidecar, candidate_content)
    if (
        decision not in {"ALLOW_PREPARATION", "EXCLUDE"}
        or type(reviewed_images) is not bool
    ):
        raise ImageSafetyError("人間判断が不正です。")
    if not isinstance(note, str) or not note.strip() or len(note) > 2000:
        raise ImageSafetyError("確認した画像・判断の根拠を記入してください。")
    if decision == "ALLOW_PREPARATION" and not reviewed_images:
        raise ImageSafetyError("十分な画像確認が必要です。確認できない場合は要確認を継続してください。")
    row = next((r for r in result["rows"] if r["fact"]["candidate_asin"] == asin), None)
    if row is None or row["evaluation"]["selector"] in SKIP_SELECTORS:
        raise ImageSafetyError("画像確認対象の商品を選んでください。")
    human = {
        "decision": decision,
        "reviewed_images": reviewed_images,
        "note": note.strip(),
        "candidate_sha256": result["candidate_sha256"],
        "candidate_asin": asin,
        "evaluation_id": row["evaluation"]["evaluation_id"],
    }
    human["binding_sha256"] = _digest(human)
    row["human"] = human
    validate_image_sidecar(
        result, candidate_content, [r.candidate for r in base_result.rows]
    )
    return result


def clear_human_decision(
    base_result, sidecar: dict, candidate_content: bytes, *, asin: str
) -> dict:
    result = prepare_image_safety(base_result, sidecar, candidate_content)
    row = next((r for r in result["rows"] if r["fact"]["candidate_asin"] == asin), None)
    if row is None:
        raise ImageSafetyError("人間判断の対象商品が一致しません。")
    row["human"] = None
    return result


def image_result_status(evaluation: dict) -> str | None:
    """DEC-0051 product result, distinct from the raw AI semantic result.

    Partial success is INDETERMINATE even if the available images got NO_SIGNAL.
    Selector skips and pending execution have no image-confirmed result.
    """
    if (
        evaluation["selector"] in SKIP_SELECTORS
        or evaluation["system_status"] == "NOT_RUN"
    ):
        return None
    if evaluation["system_status"] == "COMPLETED":
        return evaluation["ai_status"]
    return {"PARTIAL": "INDETERMINATE", "UNAVAILABLE": "UNAVAILABLE", "ERROR": "ERROR"}[
        evaluation["system_status"]
    ]


def apply_image_safety(base_result, sidecar: dict, candidate_content: bytes):
    """Overlay image REVIEW/EXCLUDE without changing the original Safety outcome."""
    result = prepare_image_safety(base_result, sidecar, candidate_content)
    by_asin = {r["fact"]["candidate_asin"]: r for r in result["rows"]}
    rows = []
    for base in base_result.rows:
        row = by_asin[base.candidate.candidate_asin]
        evaluation, human = row["evaluation"], row["human"]
        final = base.final_eligibility
        reasons = base.reason_codes
        if evaluation["selector"] not in SKIP_SELECTORS:
            if human and human["decision"] == "EXCLUDE":
                final = "EXCLUDE"
                reasons += ("IMAGE_SAFETY_EXCLUDE",)
            elif not (human and human["decision"] == "ALLOW_PREPARATION"):
                if image_result_status(evaluation) != "NO_SIGNAL":
                    if final != "EXCLUDE":
                        final = "REVIEW"
                    reasons += ("IMAGE_SAFETY_REVIEW",)
        rows.append(replace(base, final_eligibility=final, reason_codes=reasons))
    return replace(
        base_result,
        rows=tuple(rows),
        eligible_count=sum(r.final_eligibility == "ELIGIBLE" for r in rows),
        review_count=sum(r.final_eligibility == "REVIEW" for r in rows),
        exclude_count=sum(r.final_eligibility == "EXCLUDE" for r in rows),
    )


def _validate_base(base, sidecar, content):
    if base.marketplace != "PH" or any(r.marketplace != "PH" for r in base.rows):
        raise ImageSafetyError("画像SafetyはPH専用です。")
    if any(set(r.reason_codes) & set(IMAGE_REASON_CODES) for r in base.rows):
        raise ImageSafetyError("画像判定は既存Safetyの元結果へ適用してください。")
    validate_image_sidecar(sidecar, content, [r.candidate for r in base.rows])


def _validate_fact(fact):
    _keys(
        fact,
        {
            "candidate_asin",
            "provider",
            "root_category_id",
            "image_urls",
            "capture_error",
        },
    )
    if not isinstance(fact["candidate_asin"], str) or not _ASIN.fullmatch(
        fact["candidate_asin"]
    ):
        raise ImageSafetyError("画像情報のASINが不正です。")
    if fact["provider"] not in {"keepa", "canopy_test"}:
        raise ImageSafetyError("画像情報providerが不正です。")
    root = fact["root_category_id"]
    if root is not None and (type(root) is not int or normalize_root(root) != root):
        raise ImageSafetyError("画像情報rootが不正です。")
    urls = fact["image_urls"]
    if (
        not isinstance(urls, list)
        or len(urls) > MAX_IMAGES
        or any(not valid_image_url(u) for u in urls)
        or len(urls) != len(set(urls))
    ):
        raise ImageSafetyError("画像情報URLが不正です。")
    if type(fact["capture_error"]) is not bool:
        raise ImageSafetyError("画像情報取得状態が不正です。")
    if fact["provider"] == "canopy_test" and (
        root is not None or urls or fact["capture_error"]
    ):
        raise ImageSafetyError("Canopyの画像Safety拡張は対象外です。")


def _validate_evaluation(row, candidate_sha):
    e = row["evaluation"]
    _keys(
        e,
        {
            "selector",
            "base_guardrail_status",
            "system_status",
            "ai_status",
            "note",
            "images",
            "provider",
            "model",
            "prompt_version",
            "attempts",
            "run_id",
            "evaluation_id",
        },
    )
    if e["selector"] not in SELECTORS or e["selector"] != select_images(
        row["fact"], e["base_guardrail_status"]
    ):
        raise ImageSafetyError("selectorと元情報が一致しません。")
    if e["system_status"] not in SYSTEM_STATES or (
        e["ai_status"] is not None and e["ai_status"] not in SEMANTIC_RESULTS
    ):
        raise ImageSafetyError("画像Safety statusが不正です。")
    if (
        not isinstance(e["note"], str)
        or len(e["note"]) > 2000
        or e["prompt_version"] != PROMPT_VERSION
    ):
        raise ImageSafetyError("画像Safety応答契約が不正です。")
    if type(e["attempts"]) is not int or e["attempts"] not in {0, 1, 2}:
        raise ImageSafetyError("画像AI試行回数が不正です。")
    if (e["provider"], e["model"]) != (
        ("OpenAI", MODEL) if e["attempts"] else ("", "")
    ):
        raise ImageSafetyError("画像AI provider/modelが不正です。")
    if not isinstance(e["run_id"], str) or not re.fullmatch(
        r"[a-f0-9]{32}", e["run_id"]
    ):
        raise ImageSafetyError("画像評価identityが不正です。")
    images = e["images"]
    if not isinstance(images, list) or len(images) > MAX_IMAGES:
        raise ImageSafetyError("使用画像が不正です。")
    for image in images:
        _keys(image, {"url", "status", "sha256", "mime"})
        if image["status"] not in {"LOADED", "UNAVAILABLE", "ERROR"}:
            raise ImageSafetyError("使用画像状態が不正です。")
        if image["status"] == "LOADED":
            if (
                not isinstance(image["sha256"], str)
                or not _HASH.fullmatch(image["sha256"])
                or image["mime"]
                not in {"image/jpeg", "image/png", "image/webp", "image/gif"}
            ):
                raise ImageSafetyError("使用画像hash/形式が不正です。")
        elif image["sha256"] != "" or image["mime"] != "":
            raise ImageSafetyError("未取得画像に内容hashを設定できません。")
    if images and [i["url"] for i in images] != row["fact"]["image_urls"]:
        raise ImageSafetyError("選択画像と使用画像が一致しません。")
    loaded = sum(i["status"] == "LOADED" for i in images)
    if e["selector"] in SKIP_SELECTORS:
        if (
            e["system_status"] != "NOT_RUN"
            or e["attempts"]
            or images
            or e["ai_status"] is not None
        ):
            raise ImageSafetyError("未実行商品にAI結果は設定できません。")
    elif e["system_status"] == "NOT_RUN":
        if e["attempts"] or images or e["ai_status"] is not None:
            raise ImageSafetyError("未実行とAI結果が混在しています。")
    elif e["system_status"] == "COMPLETED":
        if (
            not e["attempts"]
            or not loaded
            or loaded != len(row["fact"]["image_urls"])
            or row["fact"]["capture_error"]
            or e["ai_status"] is None
        ):
            raise ImageSafetyError("画像確認完了の根拠が不足しています。")
    elif e["system_status"] == "PARTIAL":
        if not loaded or (
            loaded == len(row["fact"]["image_urls"])
            and not row["fact"]["capture_error"]
        ):
            raise ImageSafetyError("一部画像失敗の状態が不正です。")
    elif e["ai_status"] is not None:
        raise ImageSafetyError("システム失敗をAI結果として扱えません。")
    if e["ai_status"] is not None and not e["attempts"]:
        raise ImageSafetyError("AI未実行の意味上の結果は使用できません。")
    if e["attempts"] and not loaded:
        raise ImageSafetyError("AI実行に使用画像がありません。")
    expected = _evaluation_id(
        row["fact"], {k: v for k, v in e.items() if k != "evaluation_id"}, candidate_sha
    )
    if e["evaluation_id"] != expected:
        raise ImageSafetyError("画像評価bindingが一致しません。")


def _validate_human(row, candidate_sha):
    h = row["human"]
    _keys(
        h,
        {
            "decision",
            "reviewed_images",
            "note",
            "candidate_sha256",
            "candidate_asin",
            "evaluation_id",
            "binding_sha256",
        },
    )
    if row["evaluation"]["selector"] in SKIP_SELECTORS or h["decision"] not in {
        "ALLOW_PREPARATION",
        "EXCLUDE",
    }:
        raise ImageSafetyError("人間判断対象/値が不正です。")
    if type(h["reviewed_images"]) is not bool or (
        h["decision"] == "ALLOW_PREPARATION" and not h["reviewed_images"]
    ):
        raise ImageSafetyError("人間による十分な画像確認が必要です。")
    if not isinstance(h["note"], str) or not h["note"].strip() or len(h["note"]) > 2000:
        raise ImageSafetyError("人間判断の根拠が必要です。")
    if (
        h["candidate_sha256"] != candidate_sha
        or h["candidate_asin"] != row["fact"]["candidate_asin"]
        or h["evaluation_id"] != row["evaluation"]["evaluation_id"]
    ):
        raise ImageSafetyError("人間判断bindingが一致しません。")
    if h["binding_sha256"] != _digest(
        {k: v for k, v in h.items() if k != "binding_sha256"}
    ):
        raise ImageSafetyError("人間判断内容bindingが一致しません。")


def _seal(row, evaluation, candidate_sha):
    evaluation["evaluation_id"] = _evaluation_id(row["fact"], evaluation, candidate_sha)
    row["evaluation"] = evaluation
    row["human"] = None


def _evaluation_id(fact, evaluation, candidate_sha):
    return _digest(
        {
            "schema": SCHEMA,
            "candidate_sha256": candidate_sha,
            "fact": fact,
            "evaluation": evaluation,
        }
    )


def _candidate_provider(candidate):
    return (
        "canopy_test"
        if candidate.source_verification == "CANOPY_VERIFIED"
        or candidate.source.startswith("canopy")
        else "keepa"
    )


def _bound_candidates(content, rows):
    from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv

    if not isinstance(content, bytes) or not content:
        raise ImageSafetyError("Candidate bytesが必要です。")
    candidates = tuple(rows)
    try:
        parsed = parse_prelisting_candidate_csv(content, filename="candidate.csv")
    except Exception as exc:
        raise ImageSafetyError("Candidateを検証できません。") from exc
    if parsed.rows != candidates or len({r.candidate_asin for r in candidates}) != len(
        candidates
    ):
        raise ImageSafetyError("Candidate bytes/行/ASIN集合が一致しません。")
    return candidates


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != keys:
        raise ImageSafetyError("画像Safetyのfield構造が不正です。")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _sha(content):
    return hashlib.sha256(content).hexdigest()


def _digest(value):
    return _sha(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )
