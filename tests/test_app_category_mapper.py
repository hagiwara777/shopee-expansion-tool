import csv
from io import StringIO
import logging
from pathlib import Path

from streamlit.testing.v1 import AppTest

from modules.category_mapper_store import CategoryMapperStore
from modules.prelisting_candidate_csv import PRELISTING_CANDIDATE_COLUMNS
from modules.prelisting_gate_csv import PRELISTING_GATE_RESULT_COLUMNS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"


def _standard_logger_warning(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.WARNING):
        self._log(logging.WARNING, message, args, **kwargs)


def _expansion_csv(title: str = "Shampoo") -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=PRELISTING_CANDIDATE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(
        {
            "schema_version": "PRELISTING_CANDIDATE_V1",
            "source_type": "EXPANSION",
            "source_id": "",
            "source_asin": "B000000000",
            "candidate_asin": "B000000001",
            "input_title": "",
            "product_title": title,
            "brand": "ASIENCE",
            "category": "シャンプー",
            "amazon_url": "",
            "source_status": "",
            "source_verification": "",
            "source": "keepa",
            "fetched_at": "",
            "source_note": "",
        }
    )
    return output.getvalue().encode("utf-8-sig")


def _gate_csv(
    *, asin: str = "B000000001", category: str = "シャンプー", title: str = "Shampoo"
) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=PRELISTING_GATE_RESULT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    row = {column: "" for column in PRELISTING_GATE_RESULT_COLUMNS}
    row.update(
        {
            "gate_schema_version": "PRELISTING_GATE_RESULT_V1",
            "candidate_asin": asin,
            "final_eligibility": "ELIGIBLE",
            "marketplace": "PH",
            "candidate_schema_version": "PRELISTING_CANDIDATE_V1",
            "source_type": "EXPANSION",
            "source_asin": "B000000000",
            "product_title": title,
            "brand": "ASIENCE",
            "category": category,
        }
    )
    writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


def _seed_conditioner_leaf(tmp_path: Path) -> None:
    store = CategoryMapperStore(tmp_path / "localappdata" / "ShopeeCategoryMapper" / "category_mapper.sqlite3")
    store.save_categories(
        "PH",
        [
            {
                "category_id": 100000,
                "parent_category_id": None,
                "category_name": "Beauty",
                "is_leaf": False,
                "is_others": False,
            },
            {
                "category_id": 100659,
                "parent_category_id": 100000,
                "category_name": "Hair Care",
                "is_leaf": False,
                "is_others": False,
            },
            {
                "category_id": 100872,
                "parent_category_id": 100659,
                "category_name": "Hair and Scalp Conditioner",
                "is_leaf": True,
                "is_others": False,
            },
        ],
    )


def _test_app(monkeypatch, tmp_path: Path) -> AppTest:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(logging.Logger, "warning", _standard_logger_warning)
    return AppTest.from_file(str(APP_PATH), default_timeout=10).run()


def test_category_mapper_tab_is_ph_only_and_uploads_csv(monkeypatch, tmp_path):
    app = _test_app(monkeypatch, tmp_path)

    assert not app.exception
    assert [tab.label for tab in app.tabs][-1] == "Category Mapper"
    marketplace = app.selectbox(key="category_mapper_marketplace")
    assert marketplace.value == "PH"
    assert marketplace.disabled is True
    assert any(
        uploader.label == "Expansion候補CSV または Prelisting Gate eligible CSV"
        for uploader in app.file_uploader
    )
    assert any("SG / MY / TH" in str(caption.value) for caption in app.caption)


def test_category_mapper_builds_downloads_and_clears_stale_results(monkeypatch, tmp_path):
    app = _test_app(monkeypatch, tmp_path)
    app.file_uploader(key="category_mapper_source_csv").set_value(
        ("expansion.csv", _expansion_csv(), "text/csv")
    )
    app.run()
    app.button(key="category_mapper_build").click().run()

    assert not app.exception
    assert "category_mapper_recommendations" in app.session_state
    labels = [button.label for button in app.download_button]
    assert "詳細推薦CSVをダウンロード" in labels
    assert "出品グループCSVをダウンロード" not in labels
    assert "出品ツール貼付用TXTをダウンロード" not in labels
    assert any("出力対象がありません" in str(info.value) for info in app.info)
    assert any(expander.label == "阻害条件の対象行を確認" for expander in app.expander)
    assert (
        'file_name=f"category_mapper_recommendations_ph_{source_type}.csv"'
        in (PROJECT_ROOT / "modules" / "category_mapper_ui.py").read_text(encoding="utf-8")
    )

    app.file_uploader(key="category_mapper_source_csv").set_value(
        ("changed.csv", _expansion_csv("Different shampoo"), "text/csv")
    ).run()
    assert "category_mapper_recommendations" not in app.session_state


def test_category_mapper_ai_shadow_ui_is_closed_and_cannot_change_exports(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = _test_app(monkeypatch, tmp_path)
    app.file_uploader(key="category_mapper_source_csv").set_value(
        ("eligible.csv", _gate_csv(), "text/csv")
    )
    app.run()
    app.button(key="category_mapper_build").click().run()

    assert not app.exception
    shadow_expander = next(
        expander
        for expander in app.expander
        if expander.label == "AI Category推薦を試験する（出品結果には反映しません）"
    )
    assert shadow_expander.proto.expanded is False
    assert app.button(key="category_mapper_ai_shadow_run_button").label == "AI試験を実行"
    assert (
        app.button(key="category_mapper_ai_shadow_rescore_button").label
        == "保存済み予測を現在の確認結果で再評価"
    )
    assert any(
        "Category確定、CSV、TXT、出品データには反映されません" in str(caption.value)
        for caption in app.caption
    )
    before = app.session_state["category_mapper_recommendations"]
    app.button(key="category_mapper_ai_shadow_rescore_button").click().run()
    assert not app.exception
    assert app.session_state["category_mapper_recommendations"] == before
    app.button(key="category_mapper_ai_shadow_run_button").click().run()
    assert not app.exception
    assert app.session_state["category_mapper_recommendations"] == before
    assert any("AI認証情報が未設定" in str(info.value) for info in app.info)


def test_category_mapper_applies_no_brand_to_gate_group_and_enables_outputs(monkeypatch, tmp_path):
    app = _test_app(monkeypatch, tmp_path)
    app.file_uploader(key="category_mapper_source_csv").set_value(
        ("eligible.csv", _gate_csv(), "text/csv")
    )
    app.run()
    app.button(key="category_mapper_build").click().run()
    assert "出品グループCSVをダウンロード" not in [button.label for button in app.download_button]

    assert app.button(key="category_mapper_apply_no_brand_0").label == "No brandで確定"
    app.button(key="category_mapper_apply_no_brand_0").click().run()

    assert not app.exception
    labels = [button.label for button in app.download_button]
    assert "出品グループCSVをダウンロード" in labels
    assert "出品ツール貼付用TXTをダウンロード" in labels
    assert app.session_state["category_mapper_recommendations"][0].listing_ready is True
    store = CategoryMapperStore(tmp_path / "localappdata" / "ShopeeCategoryMapper" / "category_mapper.sqlite3")
    assert store.find_confirmed_brand_alias("PH", 100869, "ASIENCE") is None
    assert store.find_confirmed_brand_policy("PH", "シャンプー", "ASIENCE", 100869)["brand_id"] == 0


def test_category_mapper_shows_and_confirms_conditioner_candidate_by_group(monkeypatch, tmp_path):
    _seed_conditioner_leaf(tmp_path)
    app = _test_app(monkeypatch, tmp_path)
    app.file_uploader(key="category_mapper_source_csv").set_value(
        (
            "conditioner.csv",
            _gate_csv(category="リンス・コンディショナー", title="Conditioner"),
            "text/csv",
        )
    )
    app.run()
    app.button(key="category_mapper_build").click().run()

    assert app.button(key="category_mapper_apply_suggested_category_0").label == "このCategoryを採用"
    assert not any(button.key == "category_mapper_apply_no_brand_0" for button in app.button)
    assert app.session_state["category_mapper_recommendations"][0].category_is_confirmed is False
    app.button(key="category_mapper_apply_suggested_category_0").click().run()
    confirmed = app.session_state["category_mapper_recommendations"][0]
    assert confirmed.recommended_category_id == 100872
    assert confirmed.category_verification_status == "USER_CONFIRMED"
    assert confirmed.listing_ready is False
