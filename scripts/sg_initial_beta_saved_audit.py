"""Read-only four-product evidence audit. Never promotes cache defaults to JP."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.sg_beta_facts import facts_from_saved_keepa
from modules.sg_beta_workbench import auto_category, auto_brand
from modules.sg_beta_workbench_ui import context_from_bundle

def audit(cache_db, context_file, asins):
    from modules.keepa_client import normalize_asin
    asins = tuple(normalize_asin(a) for a in asins)
    if not asins or len(set(asins)) != len(asins):
        raise ValueError('Explicit unique audit ASIN selection required')
    context = context_from_bundle(Path(context_file).read_bytes(), inventories=(),
            shop_id='synthetic-shop', inventory_current=False, inventory_ref='OFFLINE_AUDIT_NO_INVENTORY')
    rows = []
    conn = sqlite3.connect(Path(cache_db).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        for asin in asins:
            row = conn.execute('SELECT response_json FROM products WHERE asin=?', (asin,)).fetchone()
            if row is None:
                rows.append({'asin': asin, 'source_status': 'MISSING', 'auto_category': False, 'auto_brand': False})
                continue
            source = json.loads(row[0])
            facts = facts_from_saved_keepa(source, source_format='cache_snapshot',
                                         evidence_ref='OWNER_SAVED_CACHE_READONLY')
            category = auto_category(facts, context)
            brand = auto_brand(facts, category, context, shop_id='synthetic-shop')
            rows.append({'asin': asin, 'source_status': 'SAVED_CACHE',
                'jp_market_proven': facts.fields['title'].acquired_market == 'JP',
                'field_origins': {k: f.origin for k, f in facts.fields.items()},
                'auto_category': category is not None, 'auto_brand': brand is not None,
                'reason': ('SOURCE_PROVENANCE_UNPROVEN' if not all(facts.fields[k].owned_by(asin)
                           for k in ('title', 'category_tree')) else
                           'OFFLINE_RULE_MATCH' if category is not None else 'RULE_OR_CATALOG_STOP'),
                'brand_catalog_source': 'OFFLINE_MOCK_NOT_CURRENT_OFFICIAL'})
    finally:
        conn.close()
    return {'schema': 'SG_INITIAL_BETA_SAVED_AUDIT_V1', 'mode': 'OFFLINE_READONLY',
            'live_api_executed': False, 'listing_safety_accepted': False, 'products': rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-db', type=Path, required=True)
    parser.add_argument('--context-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--asin', action='append', required=True)
    args = parser.parse_args()
    inputs = (args.cache_db, args.context_file)
    if any(args.output.resolve() == path.resolve()
           or args.output.exists() and path.exists() and args.output.samefile(path) for path in inputs):
        raise ValueError('Output must be separate from the saved cache and context inputs')
    report = audit(args.cache_db, args.context_file, args.asin)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for row in report['products']:
        print(row['asin'], row.get('reason', 'MISSING'), row['auto_category'], row['auto_brand'])


if __name__ == '__main__':
    main()
