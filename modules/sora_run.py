"""One-run Resolver → existing safety Gate handoff and the four Sora outputs."""

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
from io import StringIO
import json

from modules.ingredient_safety import (
    IngredientSafetySidecarResult,
    facts_for_candidate_rows as ingredient_facts, parse_ingredient_safety_sidecar,
    rows_to_ingredient_safety_sidecar,
)
from modules.prelisting_candidate_csv import (
    PrelistingCandidateFileResult,
    normalize_resolver_gate_handoff, parse_prelisting_candidate_csv,
    resolver_rows_to_prelisting_candidates, rows_to_prelisting_candidate_csv,
)
from modules.prelisting_gate import evaluate_prelisting_gate
from modules.prelisting_gate_ui import build_prelisting_gate_preview_rows, localize_prelisting_gate_preview_rows
from modules.product_text_safety import (
    ProductTextSafetySidecarResult,
    facts_for_candidate_rows as text_facts, parse_product_text_safety_sidecar,
    rows_to_product_text_safety_sidecar,
)


@dataclass(frozen=True)
class SoraRun:
    marketplace: str
    candidates: PrelistingCandidateFileResult
    ingredient_safety: IngredientSafetySidecarResult
    product_text_safety: ProductTextSafetySidecarResult
    auth_calls: int
    catalog_calls: int
    input_files: tuple[str, ...]
    input_row_count: int
    unverified_row_count: int
    started_at: str


def prepare_sora_run(verified_rows, *, marketplace, auth_calls, catalog_calls, input_files=()):
    if marketplace not in {"PH", "SG"}:
        raise ValueError("対象国を確認してください。")
    verified_rows = tuple(verified_rows)
    converted = resolver_rows_to_prelisting_candidates(verified_rows)
    if not converted.output_rows:
        raise ValueError("商品情報を確認できた候補がありません。未確認商品は通過させません。")
    handoff = normalize_resolver_gate_handoff(converted.output_rows, verified_rows)
    data = rows_to_prelisting_candidate_csv(handoff.candidate_rows)
    candidates = parse_prelisting_candidate_csv(data, filename="resolver_current_run.csv")
    ingredient_data = rows_to_ingredient_safety_sidecar(data, candidates.rows,
        ingredient_facts(candidates.rows, handoff.source_rows))
    text_data = rows_to_product_text_safety_sidecar(data, candidates.rows,
        text_facts(candidates.rows, handoff.source_rows))
    return SoraRun(marketplace, candidates,
        parse_ingredient_safety_sidecar(ingredient_data, candidate_content=data, candidates=candidates,
                                        filename="current_ingredients.csv"),
        parse_product_text_safety_sidecar(text_data, candidate_content=data, candidates=candidates,
                                         filename="current_product_text.csv"),
        auth_calls, catalog_calls, tuple(input_files), len(verified_rows),
        converted.excluded_row_count, datetime.now(timezone.utc).isoformat())


def evaluate_sora_run(run, inventories=(), *, body_confirmations=None):
    inventories = tuple(inventories)
    return evaluate_prelisting_gate(run.candidates, inventories,
        marketplace=run.marketplace, expected_shop_count=len(inventories),
        check_existing_listings=bool(inventories),
        ingredient_safety=run.ingredient_safety, product_text_safety=run.product_text_safety,
        sg_body_confirmations=body_confirmations)


def sora_exports(run, result):
    if result.marketplace != run.marketplace:
        raise ValueError("出力の対象国が一致しません。")
    eligible = '\n'.join(row.candidate.candidate_asin for row in result.rows
                         if row.final_eligibility == 'ELIGIBLE')
    def reason_csv(status):
        rows = localize_prelisting_gate_preview_rows(
            build_prelisting_gate_preview_rows(result, final_eligibility=status))
        columns = tuple(rows[0]) if rows else ('ASIN', '商品名', '理由')
        output = StringIO(newline='')
        writer = csv.DictWriter(output, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode('utf-8-sig')
    duplicate_checked = all(row.existing_listing_status != 'NOT_CHECKED' for row in result.rows)
    record = {
        '日時': run.started_at, '国': run.marketplace, '入力ファイル名': list(run.input_files),
        '入力行数': run.input_row_count, '判定商品数': result.candidate_count,
        '取得未確認行数': run.unverified_row_count,
        '通過': result.eligible_count, '要確認': result.review_count, '停止': result.exclude_count,
        'SP-API商品取得回数': run.catalog_calls, '認証回数': run.auth_calls,
        'SP-API呼び出し合計': run.catalog_calls + run.auth_calls,
        '重複照合': '実施' if duplicate_checked else '重複照合は未実施',
    }
    return {
        '通過ASIN.txt': ((eligible + '\n') if eligible else '').encode('utf-8'),
        '要確認.csv': reason_csv('REVIEW'), '停止.csv': reason_csv('EXCLUDE'),
        '実行記録.json': (json.dumps(record, ensure_ascii=False, indent=2)+'\n').encode('utf-8'),
    }
