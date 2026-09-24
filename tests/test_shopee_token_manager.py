from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
from pathlib import Path
import threading

import pytest

import modules.shopee_token_manager as token_module
from modules.shopee_catalog_client import (
    ShopeeCatalogClient,
    ShopeeCatalogConfigurationError,
)
from modules.shopee_token_manager import (
    PartnerBinding,
    REFRESH_PATH,
    ShopeeTokenManager,
    TokenManagerError,
    TokenRecord,
)


BINDING = PartnerBinding("PH", 123, 456, "FAKE_PARTNER_KEY")
NEW_RESPONSE = {
    "error": "",
        "access_token": "FAKE_NEW_ACCESS",
        "refresh_token": "FAKE_NEW_REFRESH",
        "expire_in": 14400,
        "partner_id": 123,
        "shop_id": 456,
}


def _seed(path: Path, *, expires: int | None = 500, state: str = "READY") -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "marketplace": "PH",
                "partner_id": 123,
                "shop_id": 456,
                "access_token": "FAKE_OLD_ACCESS",
                "refresh_token": "FAKE_OLD_REFRESH",
                "access_expires_at": expires,
                "acquired_at_lower_bound": 1,
                "generation": 2,
                "state": state,
                "reason_code": None,
            }
        ),
        encoding="utf-8",
    )


def _manager(path: Path, transport, *, now: int = 100, margin: int = 120):
    return ShopeeTokenManager(
        "PH", credential_path=path, transport=transport, clock=lambda: now,
        refresh_margin_seconds=margin,
    )


def test_ready_token_uses_current_generation_without_refresh(tmp_path):
    path = tmp_path / "PH.json"
    _seed(path)
    manager = _manager(path, lambda *args: pytest.fail("refresh called"))
    context = manager.get_context(BINDING)
    assert context.access_token == "FAKE_OLD_ACCESS"
    assert json.loads(path.read_text(encoding="utf-8"))["generation"] == 2


@pytest.mark.parametrize("expires", [219, 100, None])
def test_margin_expired_and_unknown_expiry_rotate_once_with_public_api_contract(tmp_path, expires):
    path = tmp_path / "PH.json"
    _seed(path, expires=expires)
    calls = []

    def transport(url, query, body, timeout):
        calls.append((url, query, body, timeout))
        return NEW_RESPONSE

    manager = _manager(path, transport)
    context = manager.get_context(BINDING)
    assert context.access_token == "FAKE_NEW_ACCESS"
    assert len(calls) == 1
    url, query, body, timeout = calls[0]
    assert url == "https://partner.shopeemobile.com" + REFRESH_PATH
    assert query == {
        "partner_id": "123",
        "timestamp": "100",
        "sign": hmac.new(
            b"FAKE_PARTNER_KEY", f"123{REFRESH_PATH}100".encode(), hashlib.sha256
        ).hexdigest(),
    }
    assert body == {"partner_id": 123, "shop_id": 456, "refresh_token": "FAKE_OLD_REFRESH"}
    assert timeout == 30
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["generation"] == 3
    assert record["state"] == "READY"
    assert record["access_token"] == "FAKE_NEW_ACCESS"
    assert record["refresh_token"] == "FAKE_NEW_REFRESH"
    assert record["access_expires_at"] == 14500
    assert record["acquired_at_lower_bound"] == 100
    manager.get_context(BINDING)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"access_token": ""},
        {"refresh_token": ""},
        {"expire_in": 0},
        {"expire_in": True},
        {"expire_in": 999999},
        {"partner_id": 999},
        {"shop_id": 999},
    ],
)
def test_partial_or_mismatched_response_fails_closed(tmp_path, change):
    path = tmp_path / "PH.json"
    _seed(path, expires=100)
    payload = {**NEW_RESPONSE, **change}
    calls = []
    manager = _manager(path, lambda *args: calls.append(1) or payload)
    with pytest.raises(TokenManagerError):
        manager.get_context(BINDING)
    assert len(calls) == 1
    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "IN_FLIGHT"
    with pytest.raises(TokenManagerError):
        manager.get_context(BINDING)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "transport",
    [
        lambda *args: (_ for _ in ()).throw(TimeoutError("FAKE_OLD_REFRESH")),
        lambda *args: (_ for _ in ()).throw(ConnectionError("FAKE_OLD_REFRESH")),
        lambda *args: (_ for _ in ()).throw(RuntimeError("HTTP 500 FAKE_OLD_REFRESH")),
        lambda *args: (_ for _ in ()).throw(RuntimeError("HTTP 429 FAKE_OLD_REFRESH")),
        lambda *args: {"response": "malformed"},
    ],
)
def test_unknown_outcome_never_resends_old_refresh_token(tmp_path, transport):
    path = tmp_path / "PH.json"
    _seed(path, expires=100)
    calls = []
    manager = _manager(path, lambda *args: calls.append(1) or transport(*args))
    with pytest.raises(TokenManagerError) as error:
        manager.get_context(BINDING)
    assert "FAKE_OLD_REFRESH" not in str(error.value)
    with pytest.raises(TokenManagerError):
        manager.get_context(BINDING)
    assert len(calls) == 1


@pytest.mark.parametrize("state", ["IN_FLIGHT", "BLOCKED"])
def test_persisted_nonready_state_fails_closed_after_restart(tmp_path, state):
    path = tmp_path / "PH.json"
    _seed(path, expires=100, state=state)
    manager = _manager(path, lambda *args: pytest.fail("refresh called"))
    with pytest.raises(TokenManagerError):
        manager.get_context(BINDING)


@pytest.mark.parametrize(
    "binding",
    [
        PartnerBinding("SG", 123, 456, "FAKE_PARTNER_KEY"),
        PartnerBinding("PH", 999, 456, "FAKE_PARTNER_KEY"),
        PartnerBinding("PH", 123, 999, "FAKE_PARTNER_KEY"),
    ],
)
def test_wrong_market_or_shop_binding_rejected(tmp_path, binding):
    path = tmp_path / "PH.json"
    _seed(path)
    manager = _manager(path, lambda *args: pytest.fail("refresh called"))
    with pytest.raises(TokenManagerError):
        manager.get_context(binding)


def test_inflight_persistence_failure_sends_no_request(tmp_path, monkeypatch):
    path = tmp_path / "PH.json"
    _seed(path, expires=100)
    monkeypatch.setattr(token_module, "_atomic_write", lambda *args: (_ for _ in ()).throw(OSError("FAKE_SECRET")))
    manager = _manager(path, lambda *args: pytest.fail("refresh called"))
    with pytest.raises(TokenManagerError):
        manager.get_context(BINDING)


def test_ready_atomic_replace_failure_returns_no_token_and_does_not_retry(tmp_path, monkeypatch):
    path = tmp_path / "PH.json"
    _seed(path, expires=100)
    original = token_module._atomic_write
    writes = []
    def failing_second_write(path, record):
        writes.append(record.state)
        if len(writes) == 2:
            raise OSError("FAKE_SECRET")
        return original(path, record)
    monkeypatch.setattr(token_module, "_atomic_write", failing_second_write)
    calls = []
    manager = _manager(path, lambda *args: calls.append(1) or NEW_RESPONSE)
    with pytest.raises(TokenManagerError):
        manager.get_context(BINDING)
    assert writes == ["IN_FLIGHT", "READY"]
    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "IN_FLIGHT"
    with pytest.raises(TokenManagerError):
        manager.get_context(BINDING)
    assert len(calls) == 1


def test_concurrent_calls_send_one_refresh(tmp_path):
    path = tmp_path / "PH.json"
    _seed(path, expires=100)
    calls = []
    barrier = threading.Barrier(2)
    def transport(*args):
        calls.append(1)
        return NEW_RESPONSE
    manager = _manager(path, transport)
    def run():
        barrier.wait()
        return manager.get_context(BINDING).access_token
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        assert [future.result(timeout=20) for future in futures] == ["FAKE_NEW_ACCESS"] * 2
    assert len(calls) == 1


def test_ph_default_off_override_priority_and_manager_failure(tmp_path, monkeypatch):
    audit = tmp_path / "audit.env"
    audit.write_text(
        "SHOPEE_PARTNER_ID=123\nSHOPEE_PARTNER_KEY=FAKE_PARTNER_KEY\n"
        "SHOPEE_PH_SHOP_ID=456\nSHOPEE_PH_ACCESS_TOKEN=FAKE_LEGACY_ACCESS\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("SHOPEE_PH_TOKEN_MANAGER_ENABLED", raising=False)
    legacy = ShopeeCatalogClient.from_local_audit_env(audit)
    assert legacy.credentials.access_token == "FAKE_LEGACY_ACCESS"
    monkeypatch.setenv("SHOPEE_PH_TOKEN_MANAGER_ENABLED", "1")
    monkeypatch.setattr(
        "modules.shopee_catalog_client.ShopeeTokenManager",
        lambda market: _manager(tmp_path / "missing.json", lambda *args: pytest.fail("refresh called")),
    )
    override = ShopeeCatalogClient.from_local_audit_env(
        audit, access_token_override="FAKE_TEMPORARY_ACCESS"
    )
    assert override._token_manager is None
    assert override.credentials.access_token == "FAKE_TEMPORARY_ACCESS"
    assert not (tmp_path / "missing.json").exists()
    managed = ShopeeCatalogClient.from_local_audit_env(audit)
    with pytest.raises(ShopeeCatalogConfigurationError):
        managed.get_categories("PH")
    assert managed.credentials.access_token == ""


def test_secret_objects_and_errors_redact_values(tmp_path):
    path = tmp_path / "PH.json"
    _seed(path, expires=100)
    manager = _manager(path, lambda *args: (_ for _ in ()).throw(RuntimeError("FAKE_NEW_ACCESS FAKE_NEW_REFRESH FAKE_PARTNER_KEY")))
    with pytest.raises(TokenManagerError) as error:
        manager.get_context(BINDING)
    combined = repr(BINDING) + repr(TokenRecord(1, "PH", 123, 456, "FAKE_OLD_ACCESS", "FAKE_OLD_REFRESH", 1, 1, 1, "READY", None)) + str(error.value)
    for secret in ("FAKE_OLD_ACCESS", "FAKE_OLD_REFRESH", "FAKE_NEW_ACCESS", "FAKE_NEW_REFRESH", "FAKE_PARTNER_KEY"):
        assert secret not in combined



def test_cross_process_lock_prevents_duplicate_refresh(tmp_path):
    import subprocess
    import sys
    import time

    path = tmp_path / "PH.json"
    call_log = tmp_path / "calls.txt"
    start_signal = tmp_path / "start"
    _seed(path, expires=100)
    worker = """
import json, sys, time
from pathlib import Path
from modules.shopee_token_manager import PartnerBinding, ShopeeTokenManager
credential, call_log, start_signal, ready = map(Path, sys.argv[1:])
ready.write_text("ready")
while not start_signal.exists():
    time.sleep(0.01)
def transport(*args):
    with call_log.open("a", encoding="utf-8") as stream:
        stream.write("refresh\\n")
    time.sleep(0.5)
    return {"error": "", "access_token": "FAKE_NEW_ACCESS", "refresh_token": "FAKE_NEW_REFRESH",
            "expire_in": 14400, "partner_id": 123, "shop_id": 456}
manager = ShopeeTokenManager("PH", credential_path=credential, transport=transport, clock=lambda: 100)
print(manager.get_context(PartnerBinding("PH", 123, 456, "FAKE_PARTNER_KEY")).access_token)
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", worker, str(path), str(call_log), str(start_signal), str(tmp_path / f"ready-{index}")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for index in range(2)
    ]
    deadline = time.monotonic() + 10
    while not all((tmp_path / f"ready-{index}").exists() for index in range(2)):
        assert time.monotonic() < deadline
        time.sleep(0.01)
    start_signal.write_text("go")
    outputs = [process.communicate(timeout=20) for process in processes]
    assert all(process.returncode == 0 for process in processes), outputs
    assert [stdout.strip() for stdout, _ in outputs] == ["FAKE_NEW_ACCESS"] * 2
    assert call_log.read_text(encoding="utf-8").splitlines() == ["refresh"]


@pytest.mark.parametrize("market", ["SG", "MY", "TH"])
def test_same_manager_implementation_can_bind_other_markets_offline(tmp_path, market):
    path = tmp_path / f"{market}.json"
    raw = {
        "schema_version": 1, "marketplace": market, "partner_id": 123, "shop_id": 456,
        "access_token": "FAKE_ACCESS", "refresh_token": "FAKE_REFRESH",
        "access_expires_at": 500, "acquired_at_lower_bound": 1,
        "generation": 0, "state": "READY", "reason_code": None,
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    manager = ShopeeTokenManager(
        market, credential_path=path,
        transport=lambda *args: pytest.fail("refresh called"),
        clock=lambda: 100,
    )
    context = manager.get_context(PartnerBinding(market, 123, 456, "FAKE_KEY"))
    assert (context.marketplace, context.partner_id, context.shop_id) == (market, 123, 456)
    assert context.access_token == "FAKE_ACCESS"



def test_managed_ph_category_brand_attribute_use_bound_context(tmp_path, monkeypatch):
    from modules.shopee_catalog_client import ShopeeCatalogCredentials
    path = tmp_path / "PH.json"
    _seed(path, expires=500)
    manager = _manager(path, lambda *args: pytest.fail("refresh called"))
    requests = []
    def request_json(url, query, timeout):
        requests.append((url, query))
        if url.endswith("get_category"):
            return {"error": "", "response": {"category_list": [{"category_id": 11, "display_category_name": "Test", "has_children": False}]}}
        if url.endswith("get_attribute_tree"):
            return {"error": "", "response": {"list": [{"category_id": 11, "attribute_tree": []}]}}
        return {"error": "", "response": {"brand_list": [{"brand_id": 0, "brand_name": "No Brand"}], "next_offset": 1, "has_next_page": False}}
    client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(123, "FAKE_PARTNER_KEY", 456, ""),
        token_manager=manager, request_json=request_json,
    )
    assert client.get_categories("PH")[0]["category_id"] == 11
    assert client.get_attribute_tree("PH", 11) == []
    assert client.get_brand_list("PH", 11).brands[0]["is_no_brand"]
    assert len(requests) == 3
    assert all(query["access_token"] == "FAKE_OLD_ACCESS" for _, query in requests)
    assert json.loads(path.read_text(encoding="utf-8"))["generation"] == 2


def test_temporary_override_has_priority_even_if_manager_flag_invalid(tmp_path, monkeypatch):
    audit = tmp_path / "audit.env"
    audit.write_text(
        "SHOPEE_PARTNER_ID=123\nSHOPEE_PARTNER_KEY=FAKE_PARTNER_KEY\n"
        "SHOPEE_PH_SHOP_ID=456\nSHOPEE_PH_ACCESS_TOKEN=FAKE_LEGACY_ACCESS\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SHOPEE_PH_TOKEN_MANAGER_ENABLED", "invalid")
    client = ShopeeCatalogClient.from_local_audit_env(audit, access_token_override="FAKE_OVERRIDE")
    assert client.credentials.access_token == "FAKE_OVERRIDE"
    assert client._token_manager is None



def test_default_transport_posts_json_without_following_redirects(monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    observed = {}
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps(NEW_RESPONSE).encode("utf-8")
    class Opener:
        def open(self, request, timeout):
            observed["request"] = request
            observed["timeout"] = timeout
            return Response()
    def fake_build_opener(handler):
        observed["redirect_handler"] = handler
        return Opener()
    monkeypatch.setattr(token_module, "build_opener", fake_build_opener)
    query = {"partner_id": "123", "timestamp": "100", "sign": "FAKE_SIGNATURE"}
    body = {"partner_id": 123, "shop_id": 456, "refresh_token": "FAKE_OLD_REFRESH"}
    assert token_module._post_refresh(
        "https://partner.shopeemobile.com" + REFRESH_PATH, query, body, 30
    ) == NEW_RESPONSE
    request = observed["request"]
    assert request.get_method() == "POST"
    assert urlsplit(request.full_url).path == REFRESH_PATH
    assert parse_qs(urlsplit(request.full_url).query) == {key: [value] for key, value in query.items()}
    assert json.loads(request.data) == body
    assert request.get_header("Content-type") == "application/json"
    assert observed["timeout"] == 30
    assert observed["redirect_handler"].redirect_request(None, None, 302, "", {}, "") is None
