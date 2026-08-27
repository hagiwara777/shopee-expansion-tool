import csv
from io import StringIO
import logging
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from modules.category_mapper_store import CategoryMapperStore
from modules.prelisting_candidate_csv import PRELISTING_CANDIDATE_COLUMNS
from modules.prelisting_gate_csv import PRELISTING_GATE_RESULT_COLUMNS
from modules.shopee_catalog_client import BrandPage, ShopeeCatalogClient, ShopeeCatalogError


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


def test_category_mapper_hides_catalog_admin_controls_by_default(monkeypatch, tmp_path):
    app = _test_app(monkeypatch, tmp_path)

    assert not app.exception
    assert not any("PH catalog sync status" in str(caption.value) for caption in app.caption)
    assert not any(button.key == "category_mapper_sync_categories" for button in app.button)


def test_category_mapper_shows_catalog_admin_controls_when_explicitly_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("CATEGORY_MAPPER_CATALOG_ADMIN_UI_ENABLED", "1")
    app = _test_app(monkeypatch, tmp_path)

    assert not app.exception
    assert any("PH catalog sync status" in str(caption.value) for caption in app.caption)
    assert app.button(key="category_mapper_sync_categories").label == "PH Category Treeを同期"

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


def test_category_mapper_temporary_access_token_input_is_masked_and_session_only(
    monkeypatch, tmp_path, caplog
):
    app = _test_app(monkeypatch, tmp_path)
    token_input = app.text_input(key="category_mapper_temporary_access_token")
    dummy_token = "DUMMY_TEMPORARY_ACCESS_TOKEN_FOR_TEST"

    assert token_input.label == "Shopee ACCESS_TOKEN（一時利用）"
    assert token_input.proto.type == token_input.proto.PASSWORD
    assert token_input.value == ""

    token_input.set_value(dummy_token).run()

    assert not app.exception
    assert app.session_state["category_mapper_temporary_access_token"] == dummy_token
    for elements in (app.caption, app.markdown, app.info, app.warning, app.error, app.success):
        assert all(dummy_token not in str(element.value) for element in elements)
    assert dummy_token not in caplog.text
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert dummy_token.encode("utf-8") not in path.read_bytes()


@pytest.mark.parametrize("catalog_action", ("category", "brand", "attribute"))
def test_category_mapper_catalog_actions_use_session_token_without_persisting_it(
    monkeypatch, tmp_path, caplog, catalog_action
):
    dummy_token = "DUMMY_TEMPORARY_ACCESS_TOKEN_FOR_TEST"
    observed_overrides: list[str | None] = []

    class FakeCatalogClient:
        def get_categories(self, marketplace):
            assert marketplace == "PH"
            return (
                {
                    "category_id": 100872,
                    "parent_category_id": None,
                    "category_name": "Conditioner",
                    "is_leaf": True,
                    "is_others": False,
                },
            )

        def get_brand_list(self, marketplace, category_id, **kwargs):
            assert (marketplace, category_id) == ("PH", 100872)
            return BrandPage(brands=(), next_offset=0, is_complete=True)

        def get_attribute_tree(self, marketplace, category_id):
            assert (marketplace, category_id) == ("PH", 100872)
            return []

    def fake_catalog_client(*, access_token_override=None):
        observed_overrides.append(access_token_override)
        return FakeCatalogClient()

    monkeypatch.setattr(
        ShopeeCatalogClient,
        "from_local_audit_env",
        staticmethod(fake_catalog_client),
    )
    if catalog_action == "category":
        monkeypatch.setenv("CATEGORY_MAPPER_CATALOG_ADMIN_UI_ENABLED", "1")
    else:
        _seed_conditioner_leaf(tmp_path)

    app = _test_app(monkeypatch, tmp_path)
    app.text_input(key="category_mapper_temporary_access_token").set_value(dummy_token).run()
    if catalog_action == "category":
        app.button(key="category_mapper_sync_categories").click().run()
    else:
        app.file_uploader(key="category_mapper_source_csv").set_value(
            (
                "conditioner.csv",
                _gate_csv(category="リンス・コンディショナー", title="Conditioner"),
                "text/csv",
            )
        ).run()
        app.button(key="category_mapper_build").click().run()
        app.button(key="category_mapper_apply_suggested_category_0").click().run()
        action_key = (
            "category_mapper_fetch_brands_0"
            if catalog_action == "brand"
            else "category_mapper_fetch_attributes_0"
        )
        app.button(key=action_key).click().run()

    assert not app.exception
    assert observed_overrides == [dummy_token]
    assert dummy_token not in caplog.text
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert dummy_token.encode("utf-8") not in path.read_bytes()


def test_category_mapper_blank_session_token_keeps_existing_catalog_factory(monkeypatch, tmp_path):
    observed_calls: list[dict[str, str]] = []

    class FakeCatalogClient:
        def get_categories(self, marketplace):
            assert marketplace == "PH"
            return ()

    def fake_catalog_client(**kwargs):
        observed_calls.append(kwargs)
        return FakeCatalogClient()

    monkeypatch.setenv("CATEGORY_MAPPER_CATALOG_ADMIN_UI_ENABLED", "1")
    monkeypatch.setattr(
        ShopeeCatalogClient,
        "from_local_audit_env",
        staticmethod(fake_catalog_client),
    )
    app = _test_app(monkeypatch, tmp_path)

    app.button(key="category_mapper_sync_categories").click().run()

    assert not app.exception
    assert observed_calls == [{}]


def test_category_mapper_brand_failure_with_temporary_token_stays_unconfirmed(
    monkeypatch, tmp_path, caplog
):
    dummy_token = "DUMMY_TEMPORARY_ACCESS_TOKEN_FOR_TEST"
    observed_overrides: list[str | None] = []

    class FailingCatalogClient:
        def get_brand_list(self, marketplace, category_id, **kwargs):
            assert (marketplace, category_id) == ("PH", 100872)
            raise ShopeeCatalogError("dummy catalog failure")

    def fake_catalog_client(*, access_token_override=None):
        observed_overrides.append(access_token_override)
        return FailingCatalogClient()

    _seed_conditioner_leaf(tmp_path)
    monkeypatch.setattr(
        ShopeeCatalogClient,
        "from_local_audit_env",
        staticmethod(fake_catalog_client),
    )
    app = _test_app(monkeypatch, tmp_path)
    app.text_input(key="category_mapper_temporary_access_token").set_value(dummy_token).run()
    app.file_uploader(key="category_mapper_source_csv").set_value(
        (
            "conditioner.csv",
            _gate_csv(category="リンス・コンディショナー", title="Conditioner"),
            "text/csv",
        )
    ).run()
    app.button(key="category_mapper_build").click().run()
    app.button(key="category_mapper_apply_suggested_category_0").click().run()
    app.button(key="category_mapper_fetch_brands_0").click().run()

    assert not app.exception
    assert observed_overrides == [dummy_token]
    assert any("Brand未確定のまま停止" in str(item.value) for item in app.warning)
    assert app.session_state["category_mapper_recommendations"][0].listing_ready is False
    assert dummy_token not in caplog.text


def test_category_mapper_does_not_add_refresh_token_or_refresh_endpoint():
    client_source = (PROJECT_ROOT / "modules" / "shopee_catalog_client.py").read_text(
        encoding="utf-8"
    )
    ui_source = (PROJECT_ROOT / "modules" / "category_mapper_ui.py").read_text(encoding="utf-8")

    assert "SHOPEE_PH_REFRESH_TOKEN" not in client_source
    assert "REFRESH_TOKEN" not in ui_source
    assert "/api/v2/auth/access_token/get" not in client_source
    assert "/api/v2/auth/access_token/get" not in ui_source


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
