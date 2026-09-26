"""Offline PH/SG binding contract for the shared read-only catalog client."""

from pathlib import Path

import pytest

from modules.shopee_access_token_source import AccessToken, GoogleSheetAccessTokenSource
from modules.shopee_catalog_client import (
    ShopeeCatalogClient,
    ShopeeCatalogConfigurationError,
    ShopeeCatalogCredentials,
    _read_env_values,
)


@pytest.mark.parametrize("marketplace", ["PH", "SG"])
def test_bound_marketplace_uses_shared_category_attribute_brand_contract(marketplace):
    calls = []

    def fake_request(url, query, timeout):
        calls.append((url, query, timeout))
        if url.endswith("get_category"):
            return {"response": {"category_list": [{"category_id": 10, "category_name": "Care"}]}}
        if url.endswith("get_attribute_tree"):
            return {"response": {"list": [{"category_id": 10, "attribute_tree": []}]}}
        return {"response": {"brand_list": [{"brand_id": 0, "brand_name": "No Brand"}],
                             "next_offset": 1, "has_next_page": False}}

    client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "DUMMY_PARTNER_KEY", 2, "DUMMY_ACCESS_TOKEN"),
        marketplace=marketplace,
        request_json=fake_request,
    )
    assert client.get_categories(marketplace)[0]["category_id"] == 10
    assert client.get_attribute_tree(marketplace, 10) == []
    assert client.get_attribute_trees(marketplace, [10])[0]["category_id"] == 10
    assert client.get_brand_list(marketplace, 10).brands[0]["is_no_brand"]
    assert len(calls) == 4
    assert all(query["shop_id"] == "2" for _, query, _ in calls)
    assert "DUMMY_PARTNER_KEY" not in repr(client.credentials)
    assert "DUMMY_ACCESS_TOKEN" not in repr(client.credentials)


@pytest.mark.parametrize("bound,requested", [("PH", "SG"), ("SG", "PH"),
                                                ("PH", "MY"), ("SG", "TH")])
def test_marketplace_mismatch_fails_before_request(bound, requested):
    def forbidden_request(*args):
        pytest.fail("Marketplace mismatch reached external request")

    client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "DUMMY_KEY", 2, "DUMMY_TOKEN"),
        marketplace=bound,
        request_json=forbidden_request,
    )
    for method in (
        lambda: client.get_categories(requested),
        lambda: client.get_attribute_tree(requested, 10),
        lambda: client.get_attribute_trees(requested, [10]),
        lambda: client.get_brand_list(requested, 10),
    ):
        with pytest.raises(ValueError):
            method()


@pytest.mark.parametrize("marketplace", ["MY", "TH", ""])
def test_unsupported_marketplace_fails_at_creation(marketplace):
    with pytest.raises(ValueError):
        ShopeeCatalogClient(
            ShopeeCatalogCredentials(1, "DUMMY_KEY", 2, "DUMMY_TOKEN"),
            marketplace=marketplace,
        )


def test_existing_ph_marketplace_argument_normalization_is_preserved():
    client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "DUMMY_KEY", 2, "DUMMY_TOKEN"),
        marketplace="PH",
        request_json=lambda *args: {"response": {"category_list": []}},
    )
    assert client.get_categories(" ph ") == ()


def test_sg_env_reads_only_requested_marketplace_values(tmp_path: Path, monkeypatch):
    env_file = tmp_path / "audit.env"
    env_file.write_text(
        "SHOPEE_PARTNER_ID=123\nSHOPEE_PARTNER_KEY=DUMMY_PARTNER_KEY\n"
        "SHOPEE_PH_SHOP_ID=456\nSHOPEE_PH_ACCESS_TOKEN=DUMMY_PH_TOKEN\n"
        "SHOPEE_SG_SHOP_ID=789\nSHOPEE_SG_ACCESS_TOKEN=DUMMY_SG_TOKEN\n"
        "SHOPEE_SG_REFRESH_TOKEN=DUMMY_REFRESH_TOKEN\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("SHOPEE_GOOGLE_SHEET_TOKEN_SOURCE_ENABLED", raising=False)
    assert "SHOPEE_PH_ACCESS_TOKEN" not in _read_env_values(env_file, marketplace="SG")
    assert "SHOPEE_SG_REFRESH_TOKEN" not in _read_env_values(env_file, marketplace="SG")
    client = ShopeeCatalogClient.from_local_audit_env(env_file, marketplace="SG")
    assert client.marketplace == "SG"
    assert (client.credentials.shop_id, client.credentials.access_token) == (789, "DUMMY_SG_TOKEN")
    assert "DUMMY_SG_TOKEN" not in repr(client.credentials)


def test_sg_bridge_uses_bound_shop_and_does_not_fallback(tmp_path: Path, monkeypatch):
    env_file = tmp_path / "audit.env"
    env_file.write_text(
        "SHOPEE_PARTNER_ID=123\nSHOPEE_PARTNER_KEY=DUMMY_PARTNER_KEY\n"
        "SHOPEE_SG_SHOP_ID=789\nSHOPEE_SG_ACCESS_TOKEN=DUMMY_LEGACY_TOKEN\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SHOPEE_GOOGLE_SHEET_TOKEN_SOURCE_ENABLED", "1")
    monkeypatch.setenv("SHOPEE_GOOGLE_SHEET_BRIDGE_SPREADSHEET_ID", "bridge-id")
    bindings = []

    def get_token(self, marketplace, shop_id):
        bindings.append((marketplace, shop_id))
        return AccessToken("DUMMY_BRIDGE_TOKEN")

    monkeypatch.setattr(GoogleSheetAccessTokenSource, "get_access_token", get_token)
    client = ShopeeCatalogClient.from_local_audit_env(env_file, marketplace="SG")
    assert bindings == [("SG", 789)]
    assert client.credentials.access_token == "DUMMY_BRIDGE_TOKEN"

    def fail(*args):
        raise RuntimeError("DUMMY_LEGACY_TOKEN")

    monkeypatch.setattr(GoogleSheetAccessTokenSource, "get_access_token", fail)
    with pytest.raises(ShopeeCatalogConfigurationError) as caught:
        ShopeeCatalogClient.from_local_audit_env(env_file, marketplace="SG")
    assert "DUMMY_LEGACY_TOKEN" not in str(caught.value)


def test_unsupported_marketplace_fails_before_source_or_env_read(monkeypatch):
    monkeypatch.setattr(GoogleSheetAccessTokenSource, "get_access_token",
                        lambda *args: pytest.fail("Source must not be called"))
    for marketplace in ("MY", "TH"):
        with pytest.raises(ValueError):
            ShopeeCatalogClient.from_local_audit_env("missing.env", marketplace=marketplace)


def test_api_error_does_not_repeat_token_or_partner_key():
    def fake_request(url, query, timeout):
        return {"error": "DUMMY_ACCESS_TOKEN", "message": "DUMMY_PARTNER_KEY"}

    client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "DUMMY_PARTNER_KEY", 2, "DUMMY_ACCESS_TOKEN"),
        marketplace="SG", request_json=fake_request,
    )
    with pytest.raises(Exception) as caught:
        client.get_categories("SG")
    assert "DUMMY_ACCESS_TOKEN" not in str(caught.value)
    assert "DUMMY_PARTNER_KEY" not in str(caught.value)
