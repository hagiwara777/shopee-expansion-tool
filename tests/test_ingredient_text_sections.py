"""Headed ingredient intervals are review evidence, never a general release."""

import pytest

from modules.guardrails import apply_guardrails


NEW_INGREDIENT_TERMS = (
    "アゼライン酸", "ハイドロキノン", "ヒドロキノン", "レチノール", "ナイアシンアミド",
    "アルブチン", "トランサミン", "トラネキサム酸", "AHA", "グリコール酸", "サリチル酸",
    "コウジ酸", "ビタミンA", "ビタミンB3", "ボトックス", "ボツリヌス", "トレチノイン", "レチノイン酸",
)
EXPLANATION_FIELDS = ("description", "features", "shortDescription", "safetyWarning", "itemHighlights")


def guarded(*, market="SG", title="普通の化粧品", **facts):
    return apply_guardrails([{"product_title": title, **facts}], marketplace=market)[0]


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("term", NEW_INGREDIENT_TERMS)
def test_every_new_ingredient_term_in_a_confirmed_description_list_is_review(market, term):
    row = guarded(market=market, description=f"全成分：水、{term}、香料")
    assert row["guardrail_status"] == "REVIEW"
    assert term in row["guardrail_matched_terms"]
    assert "成分一覧" in row["guardrail_note"]
    assert "description" in row["guardrail_note"]


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("term", NEW_INGREDIENT_TERMS)
def test_every_new_ingredient_term_in_normal_description_remains_blocked(market, term):
    assert guarded(market=market, description=f"{term}配合で肌を整える化粧品です。")["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("field", EXPLANATION_FIELDS)
@pytest.mark.parametrize("label", ["全成分：", "【成分】", "原材料:", "原材料・成分：", "原材料／成分："])
def test_clear_ingredient_headers_apply_in_each_explanation_field(field, label):
    row = guarded(**{field: label + "水、サリチル酸、香料"})
    assert row["guardrail_status"] == "REVIEW"


@pytest.mark.parametrize("text", [
    "<h3>全成分</h3><p>水、サリチル酸、香料</p>",
    "<p><strong>原材料・成分</strong><br>水、サリチル酸、香料</p>",
    "<div>【成分】水、サリチル酸、香料</div>",
    "<b>成分：</b>水、サリチル酸、香料",
    "全成分\n水、サリチル酸、香料",
])
def test_plain_and_html_headings_identify_only_an_ingredient_interval(text):
    assert guarded(description=text)["guardrail_status"] == "REVIEW"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("text", [
    "サリチル酸配合の化粧品です。全成分：水、サリチル酸、香料",
    "全成分：水、サリチル酸、香料。サリチル酸配合で肌を整えます。",
    "全成分：水、サリチル酸、香料\nサリチル酸配合で肌を整えます。",
    "全成分：水、サリチル酸、香料\n効能：サリチル酸配合で肌を整えます。",
    "全成分：水、サリチル酸、香料\n使用方法：サリチル酸配合の製品として使用します。",
    "全成分：水、サリチル酸、香料\n注意：サリチル酸配合の製品です。",
    "全成分：水、香料\nサリチル酸配合",
    "全成分：水、香料\n効能 サリチル酸配合",
    "全成分：水、香料<br>サリチル酸美白効果",
    "全成分：水、サリチル酸配合、香料",
    "全成分：水、香料\nサリチル酸美容液",
    "全成分：水、香料\n商品説明 サリチル酸、添加剤",
    "全成分：水、香料<br><br>サリチル酸、ナイアシンアミド",
    "全成分：水、香料\n\nサリチル酸、ナイアシンアミド",
    "<p>全成分：水</p><p>サリチル酸美容液</p>",
    "全成分：水、香料<p>サリチル酸美容液、添加剤",
    "全成分:water,AHA,fragrance. AHA serum",
    "全成分：水、香料【商品説明】サリチル酸美容液",
    "全成分：水、香料【使用方法】サリチル酸美容液",
    "全成分：水、サリチル酸、香料[商品説明]サリチル酸美容液",
    "全成分：水、香料〈特徴〉サリチル酸美容液",
    "全成分：水、香料《効能》サリチル酸美容液",
    "全成分：水、香料〔使い方〕サリチル酸美容液",
    "全成分：水、香料<strong>商品説明</strong>サリチル酸美容液",
    "全成分：水、香料<h3>集中ケア</h3>サリチル酸美容液",
    "全成分：水、香料（商品説明）サリチル酸美容液",
    "全成分：水、香料(使用方法)サリチル酸美容液",
    "全成分：水、サリチル酸、香料<br>商品説明：サリチル酸配合の化粧品です。",
    "<h3>全成分</h3><p>水、サリチル酸、香料</p><p>サリチル酸配合の化粧品です。</p>",
    "<div>成分：水、サリチル酸、香料</div><div>サリチル酸を配合しています。</div>",
])
def test_normal_claim_before_or_after_ingredient_interval_wins(market, text):
    assert guarded(market=market, description=text)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("text", [
    "水、サリチル酸、香料",
    "保湿成分としてサリチル酸を配合しています。",
    "成分としてサリチル酸を配合しています。",
    "原材料を厳選し、サリチル酸を配合しています。",
    "全 成 分：水、サリチル酸、香料",
    "全成分?水、サリチル酸、香料",
    "【成分 水、サリチル酸、香料",
    "【 全成分：水、サリチル酸、香料",
    "[ 全成分：水、サリチル酸、香料",
    "<h3>全成分</b><p>水、サリチル酸、香料</p>",
    "効能 成分：水、サリチル酸、香料",
    "全成分サリチル酸配合の化粧品です。",
    "全成分：サリチル酸が肌を整えます。",
    "全成分：水、サリチル酸配合で肌を整えます。",
])
def test_missing_or_unconfirmed_list_header_or_body_fails_closed(market, text):
    assert guarded(market=market, description=text)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_an_ingredient_section_does_not_release_another_field_or_bullet(market):
    listing = "全成分：水、サリチル酸、香料"
    assert guarded(market=market, title="サリチル酸配合化粧品", description=listing)["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description=listing, features=["サリチル酸配合化粧品"])["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description=[listing, "サリチル酸配合化粧品"])["guardrail_status"] == "BLOCK"
    assert guarded(market=market, features=["全成分", "サリチル酸配合化粧品"])["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_ingredient_sections_do_not_lower_other_independent_stops(market):
    assert guarded(market=market, description="全成分：水、サリチル酸、ジフェンヒドラミン")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description="全成分：水、サリチル酸、香料。医薬部外品")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, brand="Adidas", description="全成分：水、サリチル酸、香料")["guardrail_status"] == "BLOCK"
