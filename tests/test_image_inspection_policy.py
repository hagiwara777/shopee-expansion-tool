import json
import pytest
from modules import image_inspection_policy as policy
from modules.ph_image_safety import select_images
from modules.product_review import WeaponImageReviewSession
from test_product_review import evidence, allow, inspect
from test_sg_brand_confirmation_ui import preview

@pytest.mark.parametrize("market", ["PH", "SG", "MY", "TH"])
@pytest.mark.parametrize("root,expected", [(13299531,"TARGET_ROOT"),(2277721051,"TARGET_ROOT"),(14304371,"TARGET_ROOT"),(2016929051,"TARGET_ROOT"),(3210981,"OTHER_ROOT"),(None,"ROOT_UNKNOWN"),(True,"ROOT_UNKNOWN"),(-1,"ROOT_UNKNOWN"),("invalid","ROOT_UNKNOWN")])
def test_country_selection(market,root,expected):
    assert policy.select_image_inspection(marketplace=market,root_category_id=root,provider="keepa",guardrail_status="SAFE")==expected

@pytest.mark.parametrize("root", [None,13299531,3210981])
def test_ph_contract_and_block_priority(root):
    fact={"candidate_asin":"B000000001","provider":"keepa","root_category_id":root,"image_urls":[],"capture_error":False}
    assert select_images(fact,"BLOCK")=="EXISTING_BLOCK"
    assert select_images(fact,"SAFE")==policy.select_image_inspection(marketplace="PH",root_category_id=root,provider="keepa",guardrail_status="SAFE")

def test_independent_country_data_and_invalid_configuration(tmp_path,monkeypatch):
    for m in ("PH","SG","MY","TH"):
        (tmp_path/f"{m.lower()}.json").write_bytes((policy.POLICY_DIR/f"{m.lower()}.json").read_bytes())
    monkeypatch.setattr(policy,"POLICY_DIR",tmp_path)
    d=json.loads((tmp_path/"sg.json").read_text()); d["target_root_category_ids"]=[3210981]
    (tmp_path/"sg.json").write_text(json.dumps(d))
    assert policy.load_image_inspection_policy("PH").target_roots!=policy.load_image_inspection_policy("SG").target_roots
    (tmp_path/"sg.json").unlink()
    with pytest.raises(ValueError): policy.load_image_inspection_policy("SG")
    with pytest.raises(ValueError): policy.load_image_inspection_policy("XX")
    d["marketplace"]="PH"; (tmp_path/"sg.json").write_text(json.dumps(d))
    with pytest.raises(ValueError): policy.load_image_inspection_policy("SG")

def test_skip_requires_no_human_review_and_root_change_requires_inspection(preview):
    app,_,_=preview; item=app.session_state["sg_category_mapper_recommendations"][0]
    s=WeaponImageReviewSession("SG"); text,images=evidence(item); images["root_category_id"]=3210981
    s.supply(item,text=text,images=images)
    assert s.image_selection(item)=="OTHER_ROOT" and s.decision(item) is None
    assert s.preparation_blocker(item) is None and s.current_image_inspection(item) is None
    with pytest.raises(ValueError): allow(s,item)
    with pytest.raises(ValueError): s.begin_image_inspection(item)
    images["root_category_id"]=13299531; s.supply(item,text=text,images=images)
    assert s.decision(item) is None
    assert s.preparation_blocker(item) == "対象商品の武器画像AI検査"
    with pytest.raises(ValueError): allow(s,item)

def test_policy_change_invalidates_review(preview,tmp_path,monkeypatch):
    (tmp_path/"sg.json").write_bytes((policy.POLICY_DIR/"sg.json").read_bytes()); monkeypatch.setattr(policy,"POLICY_DIR",tmp_path)
    app,_,_=preview; item=app.session_state["sg_category_mapper_recommendations"][0]
    s=WeaponImageReviewSession("SG"); text,images=evidence(item); images["root_category_id"]=13299531
    s.supply(item,text=text,images=images); inspect(s,item); allow(s,item)
    d=json.loads((tmp_path/"sg.json").read_text()); d["target_root_category_ids"].append(3210981); (tmp_path/"sg.json").write_text(json.dumps(d))
    assert s.decision(item) is None
    assert s.current_image_inspection(item) is None
    with pytest.raises(ValueError): allow(s,item)
