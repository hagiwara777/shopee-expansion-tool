"""Build the NG ledger: one index of every stop / review decision Sora knows (DEC-0185).

The ledger is a generated, read-only view.  The source files under ``guardrails/`` and the
rules written in code stay the single place where a decision is changed; this script only
reads them, so running it can never change a gate result.

    python scripts/build_ng_ledger.py            # rewrite NG/LEDGER.md and NG/ledger.csv
    python scripts/build_ng_ledger.py --check    # fail when the committed ledger is stale

No network, clock, environment or local path is used: the same sources give the same bytes.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from modules.brand_monitoring import country_brand_names

GUARDRAILS = ROOT / "guardrails"
OUT_DIR = ROOT / "NG"
COLUMNS = ("group", "id", "markets", "action", "scope", "target", "basis", "note", "source_file")

BASIS = {
    "shopee_policy": "Shopee公式",
    "shopee_brand_list": "Shopee公式",
    "internal_rule": "自分の方針",
    "own_penalty_case": "ペナルティ経験",
    "community_report": "仲間内報告",
}
ACTION = {"BLOCK": "停止", "REVIEW": "要確認"}

# Decisions that live in code rather than in a data file.  They cannot be edited here; the
# ledger lists them so that nothing that stops a product is invisible.
CODE_RULES = (
    ("CODE-QUASI-DRUG", "ALL", "BLOCK", "医薬部外品・薬用・有効成分・medicated などの表示（否定文は区別）",
     "自分の方針", "QUASI_DRUG_TERMS", "modules/guardrails.py"),
    ("CODE-HOME-APPLIANCE", "ALL", "BLOCK", "家電本体・電動の商品（未確定は要確認。受動的な付属品は対象外）",
     "自分の方針", "DEC-0166", "modules/home_appliances_classifier.py"),
    ("CODE-BATTERY-PRESENCE", "ALL", "BLOCK", "電池入り・電池付属の商品（電池別売の明記は区別）",
     "自分の方針", "電池入りは出品しない", "modules/battery_presence.py"),
    ("CODE-SG-BODY", "SG", "REVIEW", "SGの本体・実同梱の確認が必要な商品",
     "自分の方針", "SG本体確認", "modules/prelisting_sg_body_safety.py"),
    ("CODE-MARKET-NG-INCOMPLETE", "ALL", "REVIEW", "国別の禁止設定が未完成の国だけ、通過候補を要確認にする",
     "自分の方針", "DEC-0183／0184／0189（SG・PH・MY・TH・TWは設定済み）", "modules/sora_markets.py"),
    ("MY-VOLUMETRIC", "MY", "REVIEW", "寸法・重量が未取得・換算不能、または容積重量を計算できないMY商品",
     "自分の方針", "DEC-0191; 梱包値を優先、商品値へfallback。容積重量超過はメモのみ、サイズ情報なしは要確認", "modules/sora_volumetric.py"),
    ("CODE-SLS-CATEGORY-PH", "PH", "BLOCK", "Shopeeカテゴリ確定後、SLSで発送不可のカテゴリ（Sora保安ゲートには未接続）",
     "Shopee公式", "カテゴリ対応画面のみ", "modules/sls_category_rules.py"),
    ("CODE-SLS-CATEGORY-SG", "SG", "BLOCK", "Shopeeカテゴリ確定後、SLSで発送不可のカテゴリ（Sora保安ゲートには未接続）",
     "Shopee公式", "カテゴリ対応画面のみ", "modules/sls_category_rules_sg.py"),
)

# Every data file below guardrails/ must be claimed by a reader here or listed as support
# material; tests fail when a new file is added without being placed in the ledger.
SUPPORT_FILES = (
    "community_ng/README.md", "community_ng/source_manifest.csv",
    "sls_shared/README.md", "sls_market_categories/README.md",
    "sls_market_categories/.gitattributes", "sls_market_categories/source-lock.json",
    "sls_market_categories/canonical.manifest.json",
)
# SLS tables listed row by row; VN/BR remain stored for later work.
SLS_LEDGER_MARKETS = ("SG", "PH", "MY", "TH", "TW")
SUPPORT_PREFIXES = ("sls_market_categories/provenance/",)


# Policy terms are joined with this separator in ledger.csv (all terms); LEDGER.md shows the first 8.
TERM_SEPARATOR = "、"


def _short(target: str, limit: int = 8) -> str:
    terms = target.split(TERM_SEPARATOR)
    return TERM_SEPARATOR.join(terms[:limit]) + (f" ほか{len(terms) - limit}語" if len(terms) > limit else "")


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _enabled(row: dict[str, str]) -> bool:
    return str(row.get("enabled", "TRUE")).strip().upper() == "TRUE"


def _policy_rows(used: set[str]) -> list[dict[str, str]]:
    path = GUARDRAILS / "policy" / "rules.json"
    used.add(_rel(path))
    rows = []
    for rule in json.loads(path.read_text(encoding="utf-8"))["rules"]:
        terms = rule["terms"]
        rows.append({"group": "保安ルール", "id": rule["id"], "markets": "/".join(rule["markets"]),
                     "action": rule["action"], "scope": rule["scope"],
                     "target": TERM_SEPARATOR.join(terms), "basis": BASIS[rule["source"]],
                     "note": rule["note"], "source_file": _rel(path)})
    return rows


def _brand_rows(used: set[str]) -> list[dict[str, str]]:
    base = GUARDRAILS / "brand_monitoring"
    rows = []
    for name, group, markets, basis in (
            ("ipr.json", "ブランド（IPR）", "ALL", "Shopee公式"),
            ("counterfeit_sg.json", "ブランド（Counterfeit）", "SG", "Shopee公式"),
            ("counterfeit_ph.json", "ブランド（Counterfeit）", "PH", "Shopee公式"),
            ("counterfeit_my.json", "ブランド（Counterfeit）", "MY", "Shopee公式"),
            ("counterfeit_th.json", "ブランド（Counterfeit）", "TH", "Shopee公式"),
            ("counterfeit_tw.json", "ブランド（Counterfeit）", "TW", "Shopee公式"),
            ("company.json", "ブランド（自社方針）", "ALL", "自分の方針")):
        path = base / name
        used.add(_rel(path))
        names = dict.fromkeys(name for brand in json.loads(path.read_text(encoding="utf-8"))["brands"]
                             for name in country_brand_names(brand, markets))
        for brand in names:
            rows.append({"group": group, "id": f"{name.split('.')[0].upper()}:{brand}", "markets": markets,
                         "action": "BLOCK", "target": brand, "basis": basis, "note": "", "source_file": _rel(path)})
    path = base / "title_review.json"
    used.add(_rel(path))
    review = json.loads(path.read_text(encoding="utf-8"))
    for key, note in (("company_names", "商品名に会社名だけがある場合"), ("ambiguous_names", "一般語と紛らわしいブランド名")):
        for name in review[key]:
            rows.append({"group": "ブランド（商品名の確認）", "id": f"TITLE_REVIEW:{name}", "markets": "ALL",
                         "action": "REVIEW", "target": name, "basis": "自分の方針", "note": note,
                         "source_file": _rel(path)})
    path = base / "aliases.json"
    used.add(_rel(path))
    for item in json.loads(path.read_text(encoding="utf-8"))["aliases"]:
        markets = "/".join(item["markets"]) if item.get("markets") else "ALL"
        rows.append({"group": "ブランド（別表記）", "id": f"ALIAS:{item['alias']}", "markets": markets,
                     "action": "", "target": f"{item['alias']} → {item['canonical']}", "basis": "自分の方針",
                     "note": "別表記を正式名に読み替える（単独では止めない）", "source_file": _rel(path)})
    return rows


def _dictionary_rows(used: set[str]) -> list[dict[str, str]]:
    rows = []
    for market in ("SG", "PH"):
        for stem, group in (("prohibited_brands", "国別の禁止ブランド"), ("risk_keywords", "国別の危険語")):
            path = GUARDRAILS / f"{stem}_{market.lower()}.csv"
            used.add(_rel(path))
            for row in _csv_rows(path):
                if not _enabled(row):
                    continue
                rows.append({"group": group, "id": f"{stem.upper()}_{market}:{row['term']}", "markets": market,
                             "action": row["action"], "target": row["term"],
                             "basis": BASIS.get(row["source_type"], row["source_type"]),
                             "note": row["note"], "source_file": _rel(path)})
    path = GUARDRAILS / "sls_shared" / "battery_review_rules.csv"
    used.add(_rel(path))
    for row in _csv_rows(path):
        if _enabled(row):
            rows.append({"group": "電池の確認", "id": f"SLS_BATTERY:{row['term']}", "markets": "PH/SG/MY/TH/TW",
                         "action": row["action"], "target": row["term"],
                         "basis": BASIS.get(row["source_type"], row["source_type"]),
                         "note": row["note"], "source_file": _rel(path)})
    path = GUARDRAILS / "deterministic_block_rules_v2.csv"
    used.add(_rel(path))
    for row in _csv_rows(path):
        markets = "ALL" if row["scope"] == "COMMON_BLOCK" else row["scope"].split("_")[0]
        rows.append({"group": "成分・事実による停止", "id": row["rule_id"], "markets": markets,
                     "action": row["action"], "target": f"{row['fact_field']}: {row['canonical_term']}",
                     "basis": BASIS.get(row["source_type"], row["source_type"]),
                     "note": f"{row['decision_ref']}; {row['note']}", "source_file": _rel(path)})
    return rows


def _community_rows(used: set[str]) -> list[dict[str, str]]:
    rows = []
    base = GUARDRAILS / "community_ng"
    for name, group, key in (("marketplace_asin_blocks.csv", "仲間内報告（ASIN）", "asin"),
                             ("marketplace_brand_blocks.csv", "仲間内報告（ブランド）", "match_value")):
        path = base / name
        used.add(_rel(path))
        for row in _csv_rows(path):
            if _enabled(row):
                rows.append({"group": group, "id": f"{row['source_id']}:{row['source_row']}:{row['marketplace']}:{row[key]}",
                             "markets": row["marketplace"], "action": row["action"], "target": row[key],
                             "basis": "仲間内報告", "note": "", "source_file": _rel(path)})
    return rows


def _sls_rows(used: set[str]) -> list[dict[str, str]]:
    base = GUARDRAILS / "sls_market_categories"
    canonical_path = base / "canonical.json"
    used.add(_rel(canonical_path))
    names = {r["category_id"]: " > ".join(n for n in r["names"] if n)
             for r in json.loads(canonical_path.read_text(encoding="utf-8"))["records"]}
    rows = []
    for path in sorted((base / "markets").glob("*.json")):
        used.add(_rel(path))
        if path.name.endswith(".manifest.json"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        market = data["marketplace"]
        if market not in SLS_LEDGER_MARKETS:
            continue  # stored for later markets; their source columns differ and are not listed yet
        for record in data["records"]:
            status = " ".join(str(record.get("status") or "").split())
            if status == "YES":
                continue
            action = "BLOCK" if status == "NO" else "REVIEW"
            note = "発送不可" if status == "NO" else (status[:60] or "状態の記載なし")
            rows.append({"group": "SLS発送可否（カテゴリ）", "id": f"SLS:{market}:{record['category_id']}",
                         "markets": market, "action": action, "target": names.get(record["category_id"], ""),
                         "basis": "Shopee公式", "note": note, "source_file": _rel(path)})
    return rows


def _code_rows() -> list[dict[str, str]]:
    rows = []
    for rule_id, markets, action, target, basis, note, source in CODE_RULES:
        if not (ROOT / source).is_file():
            raise SystemExit(f"NG ledger: code rule source is missing: {source}")
        rows.append({"group": "コード内のルール", "id": rule_id, "markets": markets, "action": action,
                     "target": target, "basis": basis, "note": note, "source_file": source})
    return rows


def unclaimed_files(used: set[str]) -> list[str]:
    missing = []
    for path in sorted(GUARDRAILS.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(GUARDRAILS).as_posix()
        if _rel(path) in used or rel in SUPPORT_FILES or rel.startswith(SUPPORT_PREFIXES):
            continue
        missing.append(rel)
    return missing


def build() -> tuple[list[dict[str, str]], list[str]]:
    used: set[str] = set()
    rows = (_policy_rows(used) + _code_rows() + _brand_rows(used) + _dictionary_rows(used)
            + _community_rows(used) + _sls_rows(used))
    return rows, unclaimed_files(used)


def render_csv(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def render_markdown(rows: list[dict[str, str]]) -> str:
    lines = [
        "# NG台帳（自動生成・編集しない）",
        "",
        "Soraが「停止」「要確認」を出す根拠の一覧です。`python scripts/build_ng_ledger.py` が",
        "`guardrails/` のファイルとコード内のルールから作ります。**このファイルを直接直しても判定は変わりません。**",
        "直すときは「元ファイル」を直し、もう一度このスクリプトを実行します。全行は `NG/ledger.csv` にあります。",
        "保安ルールの `scope` は `item`（物そのもの）／`content`（中身・表示）です。他の元資産にはこの区分を付けず空欄にします。",
        "",
        "## 全体（グループ別の件数）",
        "",
        "| グループ | 停止 | 要確認 | その他 | 元ファイル |",
        "|---|---:|---:|---:|---|",
    ]
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(row["group"], []).append(row)
    for group, items in groups.items():
        counts = Counter(item["action"] for item in items)
        files = sorted({item["source_file"].rsplit("/", 1)[0] if group.startswith("SLS") else item["source_file"]
                        for item in items})
        shown = "<br>".join(f"`{name}`" for name in files[:4]) + (f"<br>ほか{len(files) - 4}件" if len(files) > 4 else "")
        other = len(items) - counts["BLOCK"] - counts["REVIEW"]
        lines.append(f"| {group} | {counts['BLOCK']} | {counts['REVIEW']} | {other} | {shown} |")
    lines += ["", "## 国別の件数（停止／要確認）", "", "| 国 | 停止 | 要確認 |", "|---|---:|---:|"]
    per_market: dict[str, Counter] = {}
    for row in rows:
        for market in row["markets"].split("/"):
            per_market.setdefault(market, Counter())[row["action"]] += 1
    for market in sorted(per_market, key=lambda m: (m != "ALL", m)):
        label = "全ての国" if market == "ALL" else market
        lines.append(f"| {label} | {per_market[market]['BLOCK']} | {per_market[market]['REVIEW']} |")
    for group in ("保安ルール", "コード内のルール", "成分・事実による停止"):
        lines += ["", f"## {group}", "", "| ID | 国 | 動作 | scope | 対象 | 根拠 | メモ |", "|---|---|---|---|---|---|---|"]
        for row in groups.get(group, []):
            cells = [row["id"], row["markets"], ACTION.get(row["action"], row["action"]), row.get("scope", ""), _short(row["target"]),
                     row["basis"], row["note"]]
            lines.append("| " + " | ".join(cell.replace("|", "／").replace("\n", " ") for cell in cells) + " |")
    lines += [
        "",
        "## 一覧に載せていない細目",
        "",
        "ブランド、国別辞書、仲間内報告、SLS発送可否（発送不可・要確認のカテゴリ）は件数が多いため、",
        "上の表は件数だけです。1件ずつの内容は `NG/ledger.csv` を表計算ソフトで開いて絞り込みます。",
        "SLS発送可否は、Shopeeのカテゴリが確定した後のカテゴリ対応画面でだけ使われ、Soraの保安ゲートには接続していません。",
        "SLSの表はSG・PH・MY・TH・TWを載せています（VN・BRは保存済みで後続工程）。",
        "",
        "## 同じ語が2か所にある場合",
        "",
        "自分たちで書いたルール（保安ルール・国別辞書・電池・成分・自社方針ブランド）で、同じ語が複数の行にあるものは",
        "`NG/overlaps.csv` に出ます。新しい重なりができるとテストが失敗します。1つにまとめるか、意図的な重なり",
        "（例：商品名は停止・説明文は要確認）なら `NG/overlaps_accepted.txt` に語を足します。",
        "",
    ]
    return "\n".join(lines)


# Groups whose rows we write ourselves.  Shopee's own lists (IPR, Counterfeit, title check),
# community reports and SLS tables overlap by nature and are not checked here.
AUTHORED_GROUPS = ("保安ルール", "国別の危険語", "国別の禁止ブランド", "電池の確認", "成分・事実による停止",
                   "ブランド（自社方針）")
ACCEPTED_OVERLAPS = OUT_DIR / "overlaps_accepted.txt"


def _terms(row: dict[str, str]) -> list[str]:
    if row["group"] == "成分・事実による停止":
        return [row["target"].split(": ", 1)[-1]]
    return row["target"].split(TERM_SEPARATOR) if row["group"] == "保安ルール" else [row["target"]]


def _markets_overlap(left: str, right: str) -> bool:
    a, b = set(left.split("/")), set(right.split("/"))
    return "ALL" in a or "ALL" in b or bool(a & b)


def overlaps(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """The same word written in two or more of our own rows that apply to a common market."""
    index: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row["group"] not in AUTHORED_GROUPS:
            continue
        for term in _terms(row):
            key = unicodedata.normalize("NFKC", term).strip().lower()
            if key and row not in index.setdefault(key, []):
                index[key].append(row)
    found = {}
    for key, items in index.items():
        if len({item["id"] for item in items}) < 2:
            continue
        if any(_markets_overlap(a["markets"], b["markets"]) for i, a in enumerate(items) for b in items[i + 1:]):
            found[key] = items
    return dict(sorted(found.items()))


def render_overlaps(found: dict[str, list[dict[str, str]]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(("term", "rows"))
    for key, items in found.items():
        writer.writerow((key, " | ".join(f"{i['id']}[{i['markets']} {i['action']}]" for i in items)))
    return buffer.getvalue()


def accepted_overlaps() -> set[str]:
    if not ACCEPTED_OVERLAPS.is_file():
        return set()
    return {line.strip() for line in ACCEPTED_OVERLAPS.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="compare with the committed ledger without writing")
    args = parser.parse_args()
    rows, unclaimed = build()
    if unclaimed:
        print("NG ledger: files under guardrails/ are not placed in the ledger: " + ", ".join(unclaimed), file=sys.stderr)
        return 1
    outputs = {OUT_DIR / "LEDGER.md": render_markdown(rows), OUT_DIR / "ledger.csv": render_csv(rows),
               OUT_DIR / "overlaps.csv": render_overlaps(overlaps(rows))}
    new_overlaps = sorted(set(overlaps(rows)) - accepted_overlaps())
    if new_overlaps:
        print("NG ledger: the same word is now written in two places (see NG/overlaps.csv). Merge them into one "
              "rule, or add the word to NG/overlaps_accepted.txt with the reason in the PR: " + ", ".join(new_overlaps),
              file=sys.stderr)
    if args.check:
        stale = [path.name for path, text in outputs.items()
                 if not path.is_file() or path.read_text(encoding="utf-8") != text]
        if stale:
            print("NG ledger is stale; run python scripts/build_ng_ledger.py: " + ", ".join(stale), file=sys.stderr)
            return 1
        return 0
    OUT_DIR.mkdir(exist_ok=True)
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    print(f"NG ledger: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
