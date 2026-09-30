"""Synthetic SG catalog subset with exact adopted IDs; no production DB or API."""
from modules.sls_category_assets import load_sg_context
from modules.category_mapper_store import CategoryMapperStore
from modules.category_mapper_sg import (SGMapperRecommendation, build_sg_category_catalog_csv,
    parse_sg_category_catalog, refresh_sg_sls_results)


def sg_item(tmp_path, category_id=100869):
    context = load_sg_context()
    names = context.names[category_id]
    rows = []
    for depth, name in enumerate(names):
        cid = category_id if depth == len(names) - 1 else 9000000 + depth
        parent = None if depth == 0 else 9000000 + depth - 1
        rows.append(dict(category_id=cid, parent_category_id=parent,
                         category_name=name, is_leaf=depth == len(names) - 1))
    store = CategoryMapperStore(tmp_path / "sg.sqlite3")
    data = build_sg_category_catalog_csv(rows, marketplace="SG")
    store.replace_sg_category_catalog(parse_sg_category_catalog(data, filename="sg.csv"))
    item = SGMapperRecommendation("SG", "EXPANSION", "B000000000", "B000000001",
        "Synthetic item", "Maker", "Synthetic category", "", "GATE_ELIGIBLE",
        recommended_category_id=category_id, recommended_category_path=" > ".join(names),
        category_verification_status="USER_CONFIRMED", category_is_confirmed=True)
    return store, refresh_sg_sls_results((item,), store=store)[0]
