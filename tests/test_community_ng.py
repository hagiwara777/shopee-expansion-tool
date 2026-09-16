from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
import shutil

import pytest

from modules.community_ng import CommunityNgDataError, load_community_ng_assets
from modules.guardrails import GuardrailDictionaryError, apply_guardrails


ASSET_DIR = Path(__file__).resolve().parents[1] / "guardrails" / "community_ng"


def candidate(*, marketplace_asin="B000000001", brand="", title="ordinary product"):
    return {
        "seed_asin": "B07TSC47PH",
        "candidate_asin": marketplace_asin,
        "brand": brand,
        "category": "Beauty",
        "product_title": title,
    }


def copied_assets(tmp_path):
    target = tmp_path / "community_ng"
    shutil.copytree(ASSET_DIR, target)
    return target


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def test_production_assets_load_with_expected_market_counts_and_source_hashes():
    assets = load_community_ng_assets()

    assert len(assets.sources) == 2
    assert len(assets.asin_blocks) == 46
    assert len(assets.brand_blocks) == 54
    assert Counter(block.marketplace for block in assets.asin_blocks) == {
        "MY": 3,
        "PH": 8,
        "SG": 20,
        "TH": 2,
        "TW": 13,
    }
    assert Counter(block.marketplace for block in assets.brand_blocks) == {
        "MY": 8,
        "PH": 14,
        "SG": 14,
        "TH": 8,
        "TW": 8,
        "VN": 2,
    }
    assert len({(block.marketplace, block.brand_key) for block in assets.brand_blocks}) == 48
    assert {source.source_id: source.sha256 for source in assets.sources} == {
        "COMMUNITY_NG_ASIN_20260916": "c60137e6d14dfcaeb70e3059b3f640c9601a60f03260f595a842c34fc7322f5b",
        "COMMUNITY_NG_BRAND_20260916": "9c318615ae693428848733d3e391b6c044ee8a9419e64422f8e1ed2c2a53c74c",
    }
    assert {
        source.data_type: (
            source.source_data_rows,
            source.nonblank_records,
            source.duplicate_records,
            source.excluded_records,
            source.quarantined_records,
            source.normalized_output_rows,
        )
        for source in assets.sources
    } == {
        "ASIN": (23, 49, 3, 0, 0, 46),
        "BRAND": (224, 279, 6, 1, 225, 54),
    }


def test_assets_preserve_owner_normalization_decisions_without_reason_fields():
    assets = load_community_ng_assets()
    brand_rows = {(block.marketplace, block.brand_key, block.match_value) for block in assets.brand_blocks}
    all_brand_values = {block.match_value for block in assets.brand_blocks}

    assert ("PH", "bose", "Bose") in brand_rows
    assert ("SG", "g-shock", "G-SHOCK") in brand_rows
    assert ("SG", "g-shock", "G=SHOCK") in brand_rows
    assert ("PH", "gourmandise", "Gourmandise") in brand_rows
    assert ("PH", "gourmandise", "グルマンディーズ") in brand_rows
    assert "Bose ワイヤレススピーカー SoundLink Max Portable Speaker" not in all_brand_values
    assert "SUNTORY" not in all_brand_values
    assert "B08DHKD9T4" not in all_brand_values
    assert "reason" not in read_csv(ASSET_DIR / "marketplace_asin_blocks.csv")[0]
    assert "reason" not in read_csv(ASSET_DIR / "marketplace_brand_blocks.csv")[0]


def test_community_asin_is_exact_normalized_market_scoped_and_traceable():
    rows = apply_guardrails(
        [
            candidate(marketplace_asin="b07rpbdxhm"),
            candidate(marketplace_asin="B07RPBDXHN"),
        ],
        marketplace="SG",
    )
    ph_row = apply_guardrails(
        [candidate(marketplace_asin="B07RPBDXHM")],
        marketplace="PH",
    )[0]

    assert rows[0]["guardrail_status"] == "BLOCK"
    assert rows[0]["guardrail_source"] == "community_ng"
    assert rows[0]["guardrail_matched_terms"] == "B07RPBDXHM"
    assert "source_id=COMMUNITY_NG_ASIN_20260916; source_row=3" in rows[0]["guardrail_note"]
    assert rows[1]["guardrail_status"] == "SAFE"
    assert ph_row["guardrail_status"] == "SAFE"


@pytest.mark.parametrize(
    ("marketplace", "brand"),
    [
        ("SG", "G-SHOCK"),
        ("SG", "G=SHOCK"),
        ("PH", "Gourmandise"),
        ("PH", "グルマンディーズ"),
        ("PH", "Bose"),
    ],
)
def test_community_brand_aliases_are_normalized_exact_blocks(marketplace, brand):
    row = apply_guardrails([candidate(brand=brand)], marketplace=marketplace)[0]

    assert row["guardrail_status"] == "BLOCK"
    assert "community_ng" in row["guardrail_source"].split("|")
    assert "Community NG matched" in row["guardrail_note"]


def test_brand_partial_suntory_and_unscoped_legacy_terms_do_not_match():
    rows = apply_guardrails(
        [
            candidate(brand="Bose SoundLink"),
            candidate(brand="SUNTORY"),
            candidate(brand="Bioderma"),
            candidate(title="浄水器"),
        ],
        marketplace="SG",
    )

    assert [row["guardrail_status"] for row in rows] == ["SAFE", "SAFE", "SAFE", "SAFE"]


def test_non_runtime_market_data_does_not_leak_to_sg_or_ph():
    for marketplace in ("SG", "PH"):
        rows = apply_guardrails(
            [
                candidate(marketplace_asin="B06ZZQWMF2"),
                candidate(marketplace_asin="B07PRT1D4G"),
            ],
            marketplace=marketplace,
        )
        assert [row["guardrail_status"] for row in rows] == ["SAFE", "SAFE"]


def test_community_block_wins_and_preserves_review_official_and_own_penalty_evidence():
    review = apply_guardrails(
        [candidate(brand="OXO", title="alcohol")],
        marketplace="SG",
    )[0]
    official = apply_guardrails([candidate(brand="nivea")], marketplace="SG")[0]
    own_penalty = apply_guardrails(
        [candidate(marketplace_asin="B000FQTRS0", brand="OXO")],
        marketplace="SG",
    )[0]

    assert review["guardrail_status"] == "BLOCK"
    assert review["guardrail_source"] == "shopee_policy|community_ng"
    assert official["guardrail_status"] == "BLOCK"
    assert official["guardrail_source"] == "shopee_brand_list|community_ng"
    assert own_penalty["guardrail_status"] == "BLOCK"
    assert own_penalty["guardrail_source"] == "own_penalty_case|community_ng"


@pytest.mark.parametrize(
    ("file_name", "old", "new", "message"),
    [
        ("marketplace_asin_blocks.csv", "MY,B06ZZQWMF2", "JP,B06ZZQWMF2", "marketplace"),
        ("marketplace_asin_blocks.csv", "MY,B06ZZQWMF2", "my,B06ZZQWMF2", "未正規化"),
        ("marketplace_asin_blocks.csv", "B06ZZQWMF2", "B06ZZ", "ASIN"),
        (
            "marketplace_brand_blocks.csv",
            "MY,eisai,エーザイ",
            "MY,eisai,B08DHKD9T4",
            "ブランド欄にASIN",
        ),
        (
            "marketplace_brand_blocks.csv",
            "COMMUNITY_NG_BRAND_20260916",
            "UNKNOWN_SOURCE",
            "source_id",
        ),
    ],
)
def test_invalid_asset_rows_fail_closed(tmp_path, file_name, old, new, message):
    asset_dir = copied_assets(tmp_path)
    path = asset_dir / file_name
    path.write_text(path.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")

    with pytest.raises(CommunityNgDataError, match=message):
        load_community_ng_assets(asset_dir)


def test_duplicate_and_nondeterministic_assets_fail_closed(tmp_path):
    duplicate_dir = copied_assets(tmp_path / "duplicate")
    duplicate_path = duplicate_dir / "marketplace_asin_blocks.csv"
    duplicate_text = duplicate_path.read_text(encoding="utf-8")
    duplicate_path.write_text(
        duplicate_text.replace("MY,B0BKGKZF91", "MY,B06ZZQWMF2", 1),
        encoding="utf-8",
    )
    order_dir = copied_assets(tmp_path / "order")
    order_path = order_dir / "marketplace_asin_blocks.csv"
    lines = order_path.read_text(encoding="utf-8").splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    order_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(CommunityNgDataError, match="重複"):
        load_community_ng_assets(duplicate_dir)
    with pytest.raises(CommunityNgDataError, match="順"):
        load_community_ng_assets(order_dir)


def test_manifest_count_mismatch_and_runtime_load_failure_fail_closed(tmp_path):
    asset_dir = copied_assets(tmp_path)
    manifest_path = asset_dir / "source_manifest.csv"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            ",46,OWNER_PROVIDED_REPO_EXTERNAL_HASH_PINNED",
            ",45,OWNER_PROVIDED_REPO_EXTERNAL_HASH_PINNED",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CommunityNgDataError, match="row count"):
        load_community_ng_assets(asset_dir)

    dictionary_dir = tmp_path / "guardrails"
    dictionary_dir.mkdir()
    shutil.copy(Path(__file__).resolve().parents[1] / "guardrails" / "prohibited_brands_sg.csv", dictionary_dir)
    shutil.copy(Path(__file__).resolve().parents[1] / "guardrails" / "risk_keywords_sg.csv", dictionary_dir)
    shutil.copytree(asset_dir, dictionary_dir / "community_ng")
    with pytest.raises(GuardrailDictionaryError, match="Community NG asset"):
        apply_guardrails([candidate()], dictionary_dir, marketplace="SG")
