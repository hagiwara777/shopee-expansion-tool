"""Offline contract tests for the dedicated Bridge token source."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from modules.shopee_access_token_source import (
    AccessTokenSourceError,
    GoogleSheetAccessTokenSource,
    GoogleSheetsTransport,
)
from modules.shopee_catalog_client import (
    ShopeeCatalogClient,
    ShopeeCatalogConfigurationError,
)


TOKEN = "DUMMY_BRIDGE_TOKEN_FOR_TEST"
HEADERS = ["marketplace", "shop_id", "access_token"]


class FakeTransport:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    def read_values(self, spreadsheet_id, cell_range):
        self.calls.append((spreadsheet_id, cell_range))
        if self.error:
            raise self.error
        return self.payload


@pytest.mark.parametrize("marketplace", ["PH", "SG", "MY", "TH"])
def test_shared_interface_binds_each_marketplace(marketplace):
    transport = FakeTransport({"values": [HEADERS, [marketplace, "456", TOKEN]]})
    result = GoogleSheetAccessTokenSource("bridge-id", transport).get_access_token(
        marketplace, 456
    )
    assert result.value == TOKEN
    assert transport.calls == [("bridge-id", "A:C")]
    assert TOKEN not in repr(result)
    assert TOKEN not in str(result)


@pytest.mark.parametrize("payload", [
    {"values": [HEADERS, ["PH", "999", TOKEN]]},
    {"values": [HEADERS, ["SG", "456", TOKEN]]},
    {"values": [HEADERS, ["PH", "456", TOKEN], ["PH", "456", TOKEN]]},
    {"values": [HEADERS, ["PH", "456", ""]]},
    {"values": [HEADERS, ["PH", "456", "BAD TOKEN"]]},
    {"values": [HEADERS, ["PH", "9" * 5000, TOKEN]]},
    {"values": [["marketplace", "shop_id", "refresh_token"], ["PH", "456", TOKEN]]},
    {"values": [HEADERS, ["PH", "456", TOKEN, "EXTRA"]]},
    {"values": [HEADERS, ["PH"]]},
    {"values": "bad"},
    {"majorDimension": "COLUMNS", "values": [HEADERS, ["PH", "456", TOKEN]]},
    {},
    None,
])
def test_invalid_bridge_data_fails_closed_without_secret(payload, caplog):
    with caplog.at_level(logging.DEBUG), pytest.raises(AccessTokenSourceError) as caught:
        GoogleSheetAccessTokenSource("bridge-id", FakeTransport(payload)).get_access_token("PH", 456)
    assert TOKEN not in repr(caught.value)
    assert TOKEN not in str(caught.value)
    assert TOKEN not in caplog.text


@pytest.mark.parametrize("reason", [
    "authentication failure", "timeout", "HTTP 401", "HTTP 403", "HTTP 429", "HTTP 500"
])
def test_transport_failure_fails_closed_without_error_detail(reason):
    transport = FakeTransport(error=RuntimeError(f"{reason}: {TOKEN}"))
    with pytest.raises(AccessTokenSourceError) as caught:
        GoogleSheetAccessTokenSource("bridge-id", transport).get_access_token("PH", 456)
    assert reason not in str(caught.value)
    assert TOKEN not in repr(caught.value)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("status", [200, 401, 403, 429, 500, 503])
def test_google_adapter_http_status_is_read_only_and_fail_closed(monkeypatch, status):
    import google.auth
    import google.auth.transport.requests

    calls = []

    class FakeResponse:
        status_code = status

        def json(self):
            return {"values": [HEADERS, ["PH", "456", TOKEN]]}

    class FakeSession:
        def get(self, url, *, params, timeout):
            calls.append((url, params, timeout))
            return FakeResponse()

    monkeypatch.setattr(google.auth, "default", lambda *, scopes: (object(), None))
    monkeypatch.setattr(
        google.auth.transport.requests, "AuthorizedSession", lambda credentials: FakeSession()
    )
    transport = GoogleSheetsTransport()
    if status == 200:
        assert transport.read_values("bridge-id", "A:C") == {
            "values": [HEADERS, ["PH", "456", TOKEN]]
        }
    else:
        with pytest.raises(AccessTokenSourceError) as caught:
            transport.read_values("bridge-id", "A:C")
        assert TOKEN not in repr(caught.value)
    assert calls == [(
        "https://sheets.googleapis.com/v4/spreadsheets/bridge-id/values/A%3AC",
        {"majorDimension": "ROWS"},
        10,
    )]


@pytest.mark.parametrize("failure_point", ["auth", "timeout"])
def test_google_adapter_auth_and_timeout_are_redacted(monkeypatch, failure_point):
    import google.auth
    import google.auth.transport.requests

    def failing_auth(*, scopes):
        raise RuntimeError(TOKEN)

    class TimedOutSession:
        def get(self, *args, **kwargs):
            raise TimeoutError(TOKEN)

    if failure_point == "auth":
        monkeypatch.setattr(google.auth, "default", failing_auth)
    else:
        monkeypatch.setattr(google.auth, "default", lambda *, scopes: (object(), None))
        monkeypatch.setattr(
            google.auth.transport.requests,
            "AuthorizedSession",
            lambda credentials: TimedOutSession(),
        )
    with pytest.raises(AccessTokenSourceError) as caught:
        GoogleSheetsTransport().read_values("bridge-id", "A:C")
    assert TOKEN not in repr(caught.value)
    assert caught.value.__context__ is None


def _env_file(tmp_path: Path) -> Path:
    path = tmp_path / "audit.env"
    path.write_text(
        "SHOPEE_PARTNER_ID=123\n"
        "SHOPEE_PARTNER_KEY=DUMMY_PARTNER_KEY_FOR_TEST\n"
        "SHOPEE_PH_SHOP_ID=456\n"
        "SHOPEE_PH_ACCESS_TOKEN=DUMMY_LEGACY_TOKEN_FOR_TEST\n",
        encoding="utf-8",
    )
    return path


def test_legacy_when_source_off(monkeypatch, tmp_path):
    monkeypatch.delenv("SHOPEE_GOOGLE_SHEET_TOKEN_SOURCE_ENABLED", raising=False)
    client = ShopeeCatalogClient.from_local_audit_env(_env_file(tmp_path))
    assert client.credentials.access_token == "DUMMY_LEGACY_TOKEN_FOR_TEST"
    assert "DUMMY_LEGACY_TOKEN_FOR_TEST" not in repr(client.credentials)


def test_explicit_zero_keeps_legacy_source(monkeypatch, tmp_path):
    monkeypatch.setenv("SHOPEE_GOOGLE_SHEET_TOKEN_SOURCE_ENABLED", "0")
    client = ShopeeCatalogClient.from_local_audit_env(_env_file(tmp_path))
    assert client.credentials.access_token == "DUMMY_LEGACY_TOKEN_FOR_TEST"


@pytest.mark.parametrize("invalid_setting", ["true", "TRUE", "", " 1 ", "off"])
def test_invalid_source_setting_fails_closed_without_legacy(
    monkeypatch, tmp_path, invalid_setting, caplog
):
    monkeypatch.setenv("SHOPEE_GOOGLE_SHEET_TOKEN_SOURCE_ENABLED", invalid_setting)
    with caplog.at_level(logging.DEBUG), pytest.raises(ShopeeCatalogConfigurationError) as caught:
        ShopeeCatalogClient.from_local_audit_env(_env_file(tmp_path))
    if invalid_setting:
        assert invalid_setting not in str(caught.value)
    assert "DUMMY_LEGACY_TOKEN_FOR_TEST" not in str(caught.value)
    assert "DUMMY_LEGACY_TOKEN_FOR_TEST" not in caplog.text


@pytest.mark.parametrize("source_setting", ["1", "true"])
def test_override_precedes_enabled_source(monkeypatch, tmp_path, source_setting):
    monkeypatch.setenv("SHOPEE_GOOGLE_SHEET_TOKEN_SOURCE_ENABLED", source_setting)
    monkeypatch.setattr(
        GoogleSheetAccessTokenSource, "get_access_token",
        lambda *args: pytest.fail("Source must not be called for temporary override"),
    )
    client = ShopeeCatalogClient.from_local_audit_env(
        _env_file(tmp_path), access_token_override="DUMMY_OVERRIDE_FOR_TEST"
    )
    assert client.credentials.access_token == "DUMMY_OVERRIDE_FOR_TEST"


def test_enabled_source_uses_bridge_without_legacy_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("SHOPEE_GOOGLE_SHEET_TOKEN_SOURCE_ENABLED", "1")
    monkeypatch.setenv("SHOPEE_GOOGLE_SHEET_BRIDGE_SPREADSHEET_ID", "bridge-id")
    from modules.shopee_access_token_source import AccessToken
    monkeypatch.setattr(
        GoogleSheetAccessTokenSource, "get_access_token",
        lambda self, market, shop: AccessToken(TOKEN) if (market, shop) == ("PH", 456) else None,
    )
    client = ShopeeCatalogClient.from_local_audit_env(_env_file(tmp_path))
    assert client.credentials.access_token == TOKEN
    assert TOKEN not in repr(client.credentials)

    def fail(*args):
        raise AccessTokenSourceError("unavailable")
    monkeypatch.setattr(GoogleSheetAccessTokenSource, "get_access_token", fail)
    with pytest.raises(ShopeeCatalogConfigurationError) as caught:
        ShopeeCatalogClient.from_local_audit_env(_env_file(tmp_path))
    assert "DUMMY_LEGACY_TOKEN_FOR_TEST" not in str(caught.value)


def test_my_th_runtime_not_activated():
    import json
    state = json.loads(Path("governance/state.json").read_text(encoding="utf-8"))
    assert state["markets"]["MY"]["operation"] == "INACTIVE"
    assert state["markets"]["TH"]["operation"] == "INACTIVE"
