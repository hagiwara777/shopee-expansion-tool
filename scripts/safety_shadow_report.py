"""Explicit offline comparison of saved evidence; never imported by the app."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.guardrails import GuardrailDictionaryError, apply_guardrails
from modules.product_text_safety import ProductTextSafetyError
from modules.safety_shadow import EVALUATOR_VERSION, ROLES, classify_product, fact_from_saved_product

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {
    "TITLE_ONLY": (False, False),
    "TITLE_AND_TEXT": (True, False),
    "TITLE_TEXT_AND_OWN_CATEGORY": (True, True),
}


def _role_signature(signals) -> dict:
    """Compare roles, not the number of evidence matches or label agreement."""
    return {s.family: (s.classification, s.bundle_candidate) for s in signals}


def _variant_changes(classifications: dict, asins: list[str]) -> dict:
    changes = {}
    for first, second in (("TITLE_ONLY", "TITLE_AND_TEXT"),
                          ("TITLE_AND_TEXT", "TITLE_TEXT_AND_OWN_CATEGORY")):
        cases = []
        for asin in asins:
            before = _role_signature(classifications[first][asin])
            after = _role_signature(classifications[second][asin])
            for family in sorted(before.keys() | after.keys()):
                if before.get(family) != after.get(family):
                    cases.append({"asin": asin, "family": family,
                                  "before": before.get(family), "after": after.get(family)})
        changes[first + "_TO_" + second] = {
            "changed_products": len({c["asin"] for c in cases}),
            "changed_family_cases": len(cases), "cases": cases,
        }
    return changes


def _confirmation_questions(family: str) -> list[str]:
    # Offline investigation prompts only; these do not create runtime REVIEW.
    content = ("刃物本体、研ぎ器・ケースのみ、本体付きセット、書籍・装飾のどれか。"
               if family == "KNIFE" else
               "レンズ本体、空ケース、ケア用品、本体付きセットのどれか。")
    return [content, "一致した既存停止理由と他のSafety条件を確認し、付属品候補だけで解除しない。",
            "対象市場の販売・輸入・許認可条件を確認する。SLS ALLOWやカテゴリIDだけで販売可能としない。"]


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bindings() -> dict[str, str]:
    paths = [ROOT / "modules/guardrails.py", ROOT / "modules/community_ng.py", ROOT / "modules/safety_shadow.py",
             ROOT / "modules/product_text_safety.py", ROOT / "scripts/safety_shadow_report.py"]
    paths += sorted(p for p in (ROOT / "guardrails").rglob("*") if p.is_file())
    return {p.relative_to(ROOT).as_posix(): _digest(p.read_bytes()) for p in paths}


def build_report(evidence_paths: list[Path], *, evidence_kind: str,
                 source_format: str, labels_path: Path | None = None) -> dict:
    if evidence_kind not in {"SAVED_PRODUCT", "SYNTHETIC"}:
        raise ValueError("SHADOW_INVALID_EVIDENCE_KIND")
    bindings = _bindings()
    facts, inputs, seen = [], [], set()
    for path in evidence_paths:
        raw = path.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
            raise ValueError("SHADOW_EXPECTED_SAVED_PRODUCT_ENVELOPE")
        if payload.get("evidence_kind", evidence_kind) != evidence_kind:
            raise ValueError("SHADOW_MIXED_EVIDENCE_KIND")
        ref = "sha256:" + _digest(raw)
        for product in payload["products"]:
            if not isinstance(product, dict):
                raise ValueError("SHADOW_INVALID_PRODUCT")
            fact = fact_from_saved_product(product, source_format=source_format,
                                          evidence_ref=ref, fetched_at=payload.get("retrieved_at_utc", ""))
            if fact.asin in seen:
                raise ValueError("SHADOW_DUPLICATE_ASIN")
            seen.add(fact.asin)
            facts.append(fact)
        inputs.append({"evidence_ref": ref, "product_count": len(payload["products"])})
    if not facts:
        raise ValueError("SHADOW_EMPTY_EVIDENCE")
    labels, label_info = {}, None
    if labels_path:
        raw = labels_path.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("label_basis") not in {
            "SYNTHETIC_EXPECTATION", "METADATA_OBSERVATION", "INDEPENDENT_HUMAN_REVIEW"
        } or not isinstance(payload.get("labels"), list):
            raise ValueError("SHADOW_INVALID_LABELS")
        if (evidence_kind == "SYNTHETIC") != (payload["label_basis"] == "SYNTHETIC_EXPECTATION"):
            raise ValueError("SHADOW_LABEL_BASIS_MISMATCH")
        for label in payload["labels"]:
            if not isinstance(label, dict):
                raise ValueError("SHADOW_INVALID_LABEL")
            key = (label.get("asin"), label.get("family"))
            if (key[0] not in seen or key[1] not in {"KNIFE", "CONTACT_LENS"}
                    or label.get("classification") not in ROLES or key in labels):
                raise ValueError("SHADOW_INVALID_LABEL_BINDING")
            labels[key] = label["classification"]
        label_info = {"evidence_ref": "sha256:" + _digest(raw), "label_basis": payload["label_basis"],
                      "limitation": "Agreement with supplied labels; no general or held-out precision claim"}
    baseline_inputs = [fact.guardrail_input() for fact in facts]
    saved_inputs = deepcopy(baseline_inputs)
    before = {market: apply_guardrails(deepcopy(baseline_inputs), marketplace=market) for market in ("PH", "SG")}
    baseline_by_asin = {m: {row["candidate_asin"]: row for row in rows} for m, rows in before.items()}
    products, summaries, elapsed = [], {}, {}
    classifications = {}
    for variant, (text, categories) in VARIANTS.items():
        start = perf_counter()
        classifications[variant] = {f.asin: classify_product(f, include_text=text, include_categories=categories)
                                    for f in facts}
        elapsed[variant] = perf_counter() - start
        counts = Counter(s.classification for signals in classifications[variant].values() for s in signals)
        agreements = sum(any(s.family == family and s.classification == expected
                             for s in classifications[variant][asin])
                         for (asin, family), expected in labels.items())
        summaries[variant] = {"classification_counts": dict(sorted(counts.items())),
                              "labeled_family_cases": len(labels), "label_agreements": agreements}
    for fact in facts:
        baseline = {m: {key: baseline_by_asin[m][fact.asin][key] for key in (
            "guardrail_status", "guardrail_matched_terms", "guardrail_source", "guardrail_note"
        )} for m in before}
        full = classifications["TITLE_TEXT_AND_OWN_CATEGORY"][fact.asin]
        observations = []
        for market, row in baseline.items():
            for signal in full:
                status = row["guardrail_status"]
                if status in {"SAFE", "REVIEW"} and signal.classification == "BODY_CANDIDATE":
                    observations.append({"marketplace": market, "family": signal.family,
                                         "kind": status + "_WITH_BODY_SIGNAL"})
                if status in {"BLOCK", "REVIEW"} and signal.classification == "ACCESSORY_CANDIDATE":
                    observations.append({"marketplace": market, "family": signal.family,
                                         "kind": status + "_WITH_ACCESSORY_SIGNAL"})
        for observation in observations:
            observation["confirmation_questions"] = _confirmation_questions(observation["family"])
        products.append({
            "asin": fact.asin, "title": fact.title, "evidence_ref": fact.evidence_ref,
            "category_origin": fact.category_origin, "domain_id": fact.domain_id,
            "category_tree": fact.category_tree, "categories": fact.categories,
            "categories_capture_status": fact.categories_capture_status, "text_capture_status": fact.text.capture_status,
            "fetched_at": fact.fetched_at, "last_update": fact.last_update, "keepa_type_audit_only": fact.keepa_type,
            "guardrail_baseline": baseline,
            "shadow_variants": {v: [asdict(s) for s in classifications[v][fact.asin]] for v in VARIANTS},
            "investigation_candidates": observations,
            "expected_labels": {family: expected for (asin, family), expected in labels.items() if asin == fact.asin},
        })
    after = {market: apply_guardrails(deepcopy(baseline_inputs), marketplace=market) for market in before}
    if before != after or baseline_inputs != saved_inputs or bindings != _bindings():
        raise ValueError("SHADOW_BASELINE_OR_INPUT_CHANGED")
    grouped = Counter(
        (o["marketplace"], o["family"], o["kind"],
         p["guardrail_baseline"][o["marketplace"]]["guardrail_matched_terms"],
         p["guardrail_baseline"][o["marketplace"]]["guardrail_source"])
        for p in products for o in p["investigation_candidates"]
    )
    investigation_groups = [
        {"marketplace": market, "family": family, "kind": kind,
         "matched_terms": terms, "guardrail_source": source, "product_count": count}
        for (market, family, kind, terms, source), count in sorted(grouped.items())
    ]
    return {
        "schema_version": "SAFETY_SHADOW_REPORT_V2", "evaluator_version": EVALUATOR_VERSION,
        "evidence_kind_declared": evidence_kind, "source_format": source_format,
        "inputs": inputs, "labels": label_info, "code_and_asset_sha256": bindings,
        "product_count": len(facts), "baseline_unchanged": True, "business_api_calls": 0,
        "classification_seconds": elapsed, "variant_summaries": summaries, "products": products,
        "variant_changes": _variant_changes(classifications, [f.asin for f in facts]),
        "investigation_groups": investigation_groups,
        "limitations": ["Classification candidates only; no new sales decisions or Gate connection",
                        "Saved Fact facade replay, not production Gate/sidecar/duplicate/Mapper validation",
                        "SAFE/REVIEW+BODY and BLOCK/REVIEW+ACCESSORY are investigation candidates, not confirmed errors",
                        "Evidence kind and label basis are declared, not authenticated by file hashing"],
    }


def _cell(value: str) -> str:
    value = str(value).replace("\n", " ").replace("\r", " ").replace("<", "&lt;").replace(">", "&gt;")
    for token in ("\\", "|", "[", "]", "`", "*", "_"):
        value = value.replace(token, "\\" + token)
    return value


def render_markdown(report: dict) -> str:
    lines = ["# Offline Safety Shadow比較", "",
             f"Evidence: {report['evidence_kind_declared']} / {report['product_count']} products", "",
             "分類signalは販売判断ではありません。既存PH / SG Guardrailは変更していません。",
             "SAFE/REVIEW + BODY、BLOCK/REVIEW + ACCESSORYは調査候補であり、見逃し・誤検出の確定ではありません。", "",
             "| Variant | 分類件数 | 期待ラベルとの一致 |", "|---|---|---|"]
    for variant, summary in report["variant_summaries"].items():
        lines.append(f"| {variant} | {summary['classification_counts']} | "
                     f"{summary['label_agreements']} / {summary['labeled_family_cases']} |")
    lines += ["", "## 追加Factによる分類の変化", "",
              "根拠の増加と分類の変化は別です。変化件数は精度改善件数ではありません。", "",
              "| 比較 | 分類が変化した商品 | familyケース |", "|---|---:|---:|"]
    for comparison, change in report["variant_changes"].items():
        lines.append(f"| {_cell(comparison)} | {change['changed_products']} | {change['changed_family_cases']} |")
    lines += ["", "## 既存判定との不一致候補", "",
              "以下はoffline調査用です。自動BLOCK / REVIEWや通常画面の人間確認を追加しません。", "",
              "| 市場 | family | 不一致候補 | 既存一致語 | source | 商品件数 |",
              "|---|---|---|---|---|---:|"]
    for group in report["investigation_groups"]:
        lines.append("| " + " | ".join(_cell(group[key]) for key in (
            "marketplace", "family", "kind", "matched_terms", "guardrail_source", "product_count"
        )) + " |")
    for family in sorted({g["family"] for g in report["investigation_groups"]}):
        lines += ["", f"{family}の具体的な確認事項:", ""]
        lines += ["- " + question for question in _confirmation_questions(family)]
    lines += ["", "一致数は指定されたラベルとの比較です。独立標本による一般精度ではありません。",
              "保存実商品の結果はその標本内の観察です。未収録の商品群・表記・セット等の性能は未確認です。", "",
              "| ASIN | Title | Shadow | PH | SG |", "|---|---|---|---|---|"]
    for product in report["products"]:
        signals = "; ".join(s["family"] + ":" + s["classification"] +
                            (" (body+accessory bundle)" if s["bundle_candidate"] else "")
                            for s in product["shadow_variants"]["TITLE_TEXT_AND_OWN_CATEGORY"]) or "OUTSIDE_TARGET_FAMILIES"
        base = product["guardrail_baseline"]
        lines.append("| " + " | ".join(_cell(x) for x in (
            product["asin"], product["title"], signals,
            base["PH"]["guardrail_status"] + ": " + base["PH"]["guardrail_matched_terms"],
            base["SG"]["guardrail_status"] + ": " + base["SG"]["guardrail_matched_terms"]
        )) + " |")
    lines += ["", "分類の一致Evidence・出所SHA・Rule version・取得状態・処理時間は隣接report.jsonに保存しています。",
              "この比較CLIによる追加API・DB更新・既存Safety解除・本番接続はありません。入力資料の取得履歴は別記録です。", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, nargs="+", required=True)
    parser.add_argument("--evidence-kind", choices=["SAVED_PRODUCT", "SYNTHETIC"], required=True)
    parser.add_argument("--source-format", choices=["keepa_response", "cache_snapshot"], required=True)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        destinations = [args.output_dir / "report.json", args.output_dir / "report.md"]
        if any(p.exists() for p in destinations):
            raise ValueError("SHADOW_OUTPUT_ALREADY_EXISTS")
        inputs = {p.resolve() for p in args.evidence}
        if args.labels:
            inputs.add(args.labels.resolve())
        if any(p.resolve() in inputs for p in destinations):
            raise ValueError("SHADOW_OUTPUT_IS_INPUT")
        report = build_report(args.evidence, evidence_kind=args.evidence_kind,
                              source_format=args.source_format, labels_path=args.labels)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for path, value in zip(destinations, (json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                            render_markdown(report))):
            with path.open("x", encoding="utf-8") as output:
                output.write(value)
    except (ValueError, ProductTextSafetyError, GuardrailDictionaryError, OSError):
        print("SHADOW_REPORT_FAILED: check saved evidence, labels, and unused output directory", file=sys.stderr)
        return 2
    print(f"Offline Shadow: {report['product_count']} products; PH/SG baseline unchanged; business API calls 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
