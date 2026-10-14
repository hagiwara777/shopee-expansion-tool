"""Offline input/output and bounded classification boundary tests."""
from copy import deepcopy
import csv
import io
import json
import socket
import sqlite3

import pytest

from modules.home_appliances_classifier import A, B, C, VERSION
from modules.home_appliances_files import InputError, classify_input, csv_bytes, load_inputs
from modules.sg_beta_facts import facts_from_saved_keepa
from scripts.classify_home_appliances import main


def product(title="掃除機用交換フィルター", **changes):
    return dict(asin="B000000001", title=title, brand="Example", domainId=5,
                categoryTree=[{"catId": 100, "name": "ホーム＆キッチン"},
                              {"catId": 101, "name": "家電"}], **changes)


def save(tmp_path, payload, name="products.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8-sig")
    return path


def evaluate(tmp_path, payload, source_format="keepa_response"):
    return classify_input(load_inputs([save(tmp_path, payload)], source_format=source_format)[0])


@pytest.mark.parametrize("title,details,expected", [
    ("掃除機本体", {}, B),
    ("掃除機本体 フィルター付き", {}, C),
    ("掃除機本体用フィルター", {}, A),
    ("掃除機用交換フィルター", {}, A),
    ("炊飯器用内釜", {}, A),
    ("浄水ポット + カートリッジセット", {}, C),
    ("浄水ポット + カートリッジセット", {"features": ["液晶メモ付き"]}, B),
    ("浄水ポット + カートリッジセット", {"features": ["電池で動作"]}, B),
    ("浄水器 ポット型 交換用カートリッジ", {}, A),
    ("浄水器 ポット型 交換用カートリッジ 本体セット", {"features": ["液晶メモ付き"]}, B),
    ("掃除機用ブラケット", {"features": ["別売の充電器と組み合わせれば収納できます"]}, A),
    ("掃除機用充電器", {}, B),
    ("掃除機用電動ヘッド", {}, B),
    ("掃除機用ヘッド", {}, C),
    ("電子 レンジ 調理器", {"description": "電子レンジで使うシリコン容器。容量1L"}, A),
    ("電子レンジ調理器", {}, C),
    ("Replacement\nFilter for Vacuum", {}, A),
    ("掃除機用ホース ブラシ キット", {"description": "包装内容:\nホース\nブラシ"}, A),
    ("掃除機用ホース ブラシ キット", {}, C),
    ("IH対応フライパン", {}, A),
    ("電気フライパン", {}, B),
    ("掃除機用フィルター", {"features": ["本製品は電池内蔵で動作します"]}, B),
    ("Replacement Filter for Vacuum", {"features": ["This device uses a battery"]}, B),
    ("", {}, C),
    ("商品セット", {}, C),
])
def test_product_boundaries(tmp_path, title, details, expected):
    result = evaluate(tmp_path, product(title, **details))
    assert result.classification == expected
    assert result.evidence and result.reason_code
    if expected == C:
        assert result.missing_information


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p.pop("domainId"), "PRODUCT_MARKET_UNVERIFIED"),
    (lambda p: p.update(domainId=1), "PRODUCT_MARKET_MISMATCH"),
    (lambda p: p.update(domainId=True), "PRODUCT_MARKET_MISMATCH"),
    (lambda p: p.update(acquired_market="SG"), "PRODUCT_MARKET_MISMATCH"),
    (lambda p: p.update(source_asin="B000000099"), "PRODUCT_ASIN_MISMATCH"),
    (lambda p: p.update(category_origin="SEED_FALLBACK"), "FACT_PROVENANCE_UNVERIFIED"),
    (lambda p: p.update(field_origins={"title": "UNKNOWN"}), "FACT_PROVENANCE_UNVERIFIED"),
    (lambda p: p.update(field_origins={"features": "SEED_FALLBACK"}, features=["電池付き"]), "FACT_PROVENANCE_UNVERIFIED"),
])
def test_unverified_facts_never_pass(tmp_path, mutation, code):
    p = product()
    mutation(p)
    result = evaluate(tmp_path, p)
    assert result.classification == C
    assert result.reason_code == code


def test_market_envelope_conflict(tmp_path):
    assert evaluate(tmp_path, {"domainId": 1, "products": [product()]}).classification == C


def test_old_cache_even_with_claimed_origins(tmp_path):
    p = product()
    p["category_tree"] = p.pop("categoryTree")
    p["field_origins"] = {"title": "OWN_PRODUCT", "brand": "OWN_PRODUCT", "category_tree": "OWN_PRODUCT"}
    assert evaluate(tmp_path, p, "cache_snapshot").classification == C


def fact_dict():
    return facts_from_saved_keepa(product(), source_format="keepa_response",
                                 fetched_at="2026-10-14T01:00:00Z", evidence_ref="saved-response").to_dict()


def test_native_fact_reuse(tmp_path):
    result = evaluate(tmp_path, fact_dict(), "saved_fact")
    assert result.classification == A


def test_native_fact_envelope_market_conflict(tmp_path):
    assert evaluate(tmp_path, {"domainId": 1, "products": [fact_dict()]}, "saved_fact").classification == C


def test_cli_publish_failure_no_partial_csv(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("simulated write failure")
    monkeypatch.setattr("scripts.classify_home_appliances.os.link", fail)
    path, output = save(tmp_path, product()), tmp_path / "result.csv"
    assert main(["--input", str(path), "--source-format", "keepa_response", "--output", str(output)]) == 2
    assert not output.exists() and not list(tmp_path.glob(".home-appliances-*"))


@pytest.mark.parametrize("key,value", [("source_asin", "B000000099"), ("acquired_market", "SG"),
                                      ("origin", "SEED_FALLBACK"), ("evidence_ref", ""),
                                      ("fetched_at", "")])
def test_native_fact_field_binding(tmp_path, key, value):
    facts = fact_dict()
    facts["fields"]["title"][key] = value
    assert evaluate(tmp_path, facts, "saved_fact").classification == C


@pytest.mark.parametrize("payload,code", [
    ({"products": []}, "EMPTY_PRODUCTS"),
    ({"products": [product()], "error": "API_ERROR"}, "INVALID_PRODUCT_RESPONSE"),
    ({"products": "invalid"}, "INVALID_PRODUCT_RESPONSE"),
    ([42], "INVALID_PRODUCT_ASIN"),
    ({"asin": "invalid"}, "INVALID_PRODUCT_ASIN"),
    (dict(product(), title=["invalid"]), "INVALID_PRODUCT_FACT"),
    (dict(product(), features={"invalid": "text"}), "INVALID_PRODUCT_FACT"),
    (dict(product(), categoryTree=[{"catId": True, "name": "家電"}]), "INVALID_PRODUCT_FACT"),
    (dict(product(), field_origins=[]), "INVALID_FIELD_ORIGINS"),
    (dict(product(), fetched_at="yesterday"), "INVALID_FETCHED_AT"),
    (dict(product(), fetched_at="2026-10-14T01:00:00"), "INVALID_FETCHED_AT"),
])
def test_invalid_input(tmp_path, payload, code):
    with pytest.raises(InputError, match=code):
        load_inputs([save(tmp_path, payload)], source_format="keepa_response")


@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_asin_rejected_across_files(tmp_path, conflicting):
    p = product("掃除機本体" if conflicting else "掃除機用交換フィルター")
    paths = [save(tmp_path, product()), save(tmp_path, p, "other.json")]
    with pytest.raises(InputError, match="DUPLICATE_ASIN"):
        load_inputs(paths, source_format="keepa_response")


@pytest.mark.parametrize("content,code", [
    (b'{"asin":"B000000001","asin":"B000000099"}', "DUPLICATE_JSON_KEY"),
    (b'{"products": [NaN]}', "INVALID_JSON_NUMBER"),
    (b'{broken', "INVALID_JSON"), (b'\xff', "INPUT_NOT_UTF8"), (b' ', "EMPTY_INPUT"),
])
def test_strict_json(tmp_path, content, code):
    path = tmp_path / "bad.json"
    path.write_bytes(content)
    with pytest.raises(InputError, match=code):
        load_inputs([path], source_format="keepa_response")


def test_jsonl_and_response_time(tmp_path):
    path = tmp_path / "products.jsonl"
    p2 = dict(product("掃除機本体"), asin="B000000002")
    path.write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in [product(), p2]), encoding="utf-8")
    items = load_inputs([path], source_format="keepa_response")
    assert [classify_input(i).letter for i in items] == ["A", "B"]
    assert "取得時刻（未記録）" in classify_input(items[0]).missing_information
    envelope = {"products": [product()], "timestamp": 1, "research_fetched_at": "2026-10-14T00:00:00Z"}
    item = load_inputs([save(tmp_path, envelope)], source_format="keepa_response")[0]
    assert item.facts.fields["title"].fetched_at == envelope["research_fetched_at"]


def test_missing_category_and_other_category(tmp_path):
    p = product()
    p.pop("categoryTree")
    assert evaluate(tmp_path, p).classification == C
    p["categoryTree"] = [{"catId": 999, "name": "自動車用部品"}]
    assert evaluate(tmp_path, p).classification == C


@pytest.mark.parametrize("title,category", [
    ("水筒 パッキン一体型", "ホーム＆キッチン > キッチン用品 > 水筒"),
    ("浴槽洗い 本体＋スペア", "ホーム＆キッチン > 掃除用品 > 浴室掃除用ブラシ"),
])
def test_general_household_outside_scope(tmp_path, title, category):
    p = dict(product(title), categoryTree=[{"catId": 100, "name": category}])
    assert evaluate(tmp_path, p).reason_code == "HOME_APPLIANCES_CONTEXT_UNVERIFIED"


def test_cli_bom_csv_and_no_network_or_input_mutation(tmp_path, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("network attempted")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    p1, p2, p3 = product(), dict(product("掃除機本体"), asin="B000000002"), dict(product("商品セット"), asin="B000000003")
    payload = {"products": [p1, p2, p3]}
    before = deepcopy(payload)
    path, output = save(tmp_path, payload), tmp_path / "result.csv"
    bytes_before = path.read_bytes()
    assert main(["--input", str(path), "--source-format", "keepa_response", "--output", str(output)]) == 0
    assert payload == before and path.read_bytes() == bytes_before
    content = output.read_bytes()
    assert content.startswith(b'\xef\xbb\xbf')
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    assert [r["分類結果"] for r in rows] == ["A", "B", "C"]
    assert all(r["判断根拠"] and r["分類ルールバージョン"] == VERSION for r in rows)
    assert all("出品許可" in r["注意事項"] for r in rows)


def test_csv_formula_escape(tmp_path):
    p = dict(product(), title="=掃除機用交換フィルター", brand="\t@Example")
    rows = list(csv.reader(io.StringIO(csv_bytes(load_inputs([save(tmp_path, p)], source_format="keepa_response")).decode("utf-8-sig"))))
    assert rows[1][1].startswith("'=") and rows[1][2].startswith("'\t@")


def test_cli_no_overwrite_and_error_no_output(tmp_path):
    path, output = save(tmp_path, [product(), product()]), tmp_path / "result.csv"
    args = ["--input", str(path), "--source-format", "keepa_response", "--output", str(output)]
    assert main(args) == 2 and not output.exists()
    output.write_bytes(b"existing")
    assert main(args) == 2 and output.read_bytes() == b"existing"
    assert main(["--input", str(path), "--source-format", "keepa_response", "--output", str(path)]) == 2
