"""Real pinned SDK, synthetic responses, no live API or operational DB."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import keepa
import pytest
import requests

from modules import keepa_jp_fact_runner as runner


@pytest.fixture(autouse=True)
def prohibit_live(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected live network")
    monkeypatch.setattr(requests.sessions.Session, "send", forbidden)
    monkeypatch.setattr(keepa.Keepa, "update_status", forbidden)
    monkeypatch.setattr(keepa.Keepa, "query", forbidden)
    monkeypatch.setattr(keepa.Keepa, "wait_for_tokens", forbidden)


def product():
    # Entirely synthetic: this is not real product evidence.
    return dict(asin=runner.ASIN, domainId=5, title="Synthetic fixture",
                brand="Synthetic maker", manufacturer="Synthetic factory",
                rootCategory=123, categoryTree=[dict(catId=123, name="Root"),
                                               dict(catId=456, name="Leaf")],
                description="Fixture description", features=["Fixture feature"])


def response(data=None, *, status=200, raw=None):
    result = requests.Response()
    result.status_code = status
    result._content = raw if raw is not None else json.dumps(
        dict(products=[product()]) if data is None else data).encode("utf-8")
    return result


def execute(tmp_path, send, **overrides):
    options = dict(api_key="synthetic-offline", evidence_dir=tmp_path / "evidence",
                   attempt_root=tmp_path / "independent" / "attempt",
                   authorization_ref="synthetic-mock-approval", transport=send)
    options.update(overrides)
    return runner._execute_once(**options)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_sdk_private_raw_contract_and_durable_pre_send_record(tmp_path, monkeypatch):
    calls = []
    original = keepa.Keepa._product_query
    raw_response = response()

    def raw_query(self, items, **options):
        assert items == [runner.ASIN]
        assert options == runner.REQUEST_OPTIONS
        assert options["raw"] is True and options["wait"] is False
        result = original(self, items, **options)
        assert result is raw_response  # SDK 1.5.0 returns the HTTP response.
        assert "data" not in result.json()["products"][0]
        return result

    monkeypatch.setattr(keepa.Keepa, "_product_query", raw_query)

    def send(url, **kwargs):
        record = read(tmp_path / "independent" / "attempt" / "attempt.json")
        assert record["reserved_http_sends"] == 1
        assert record["state"] == "RESERVED_RESULT_UNKNOWN"
        assert "synthetic-offline" not in json.dumps(record)
        assert url == runner.ENDPOINT
        assert kwargs == dict(params=dict(asin=runner.ASIN, domain=5, key="synthetic-offline",
                                         history=0, stock=0, buybox=0, rating=0, videos=0, aplus=0),
                              timeout=10, allow_redirects=False)
        calls.append(kwargs)
        return raw_response

    manifest = execute(tmp_path, send)
    assert len(calls) == manifest["http_send_attempts"] == manifest["max_http_sends"] == 1
    assert manifest["state"] == "SUCCESS"
    assert (tmp_path / "evidence" / "raw-response.json").read_bytes() == raw_response.content
    digest = hashlib.sha256(raw_response.content).hexdigest()
    assert manifest["raw_sha256"] == digest
    assert (tmp_path / "evidence" / "raw-response.sha256").read_text().strip() == digest
    facts = read(tmp_path / "evidence" / "facts.json")["facts"]
    assert facts["categoryTree"]["authority"] == "OWN_PRODUCT"
    assert facts["brand"]["value"] == "Synthetic maker"
    assert facts["category_path"]["value"] == "Root > Leaf"
    assert facts["leaf_category_id"]["value"] == 456
    for fact in facts.values():
        assert fact["asin"] == runner.ASIN and fact["domain_id"] == 5
        assert fact["fetched_at"] == manifest["fetched_at"]
        assert fact["raw_sha256"] == digest
        assert fact["evidence_ref"].startswith("raw-response.json#/products/0/")
    assert facts["ingredients"]["status"] == "MISSING"
    assert manifest["facts_sha256"] == hashlib.sha256(
        (tmp_path / "evidence" / "facts.json").read_bytes()).hexdigest()


@pytest.mark.parametrize("value,status", [(None, "UNKNOWN"), ([], "UNKNOWN")])
def test_missing_category_is_not_seed_fallback(tmp_path, value, status):
    p = product()
    p["categoryTree"] = value
    p.pop("brand")
    p["rootCategory"] = -1
    execute(tmp_path, lambda *a, **kw: response(dict(products=[p])))
    facts = read(tmp_path / "evidence" / "facts.json")["facts"]
    assert facts["categoryTree"]["status"] == status
    assert facts["categoryTree"]["value"] == value
    assert facts["brand"]["authority"] == "MISSING"
    assert facts["rootCategory"]["authority"] == "UNKNOWN"
    assert facts["category_path"]["authority"] == "UNKNOWN"


def test_absent_fields_are_missing_and_empty_fields_unknown(tmp_path):
    p = dict(asin=runner.ASIN, domainId=5, title="", features=["", " "])
    execute(tmp_path, lambda *a, **kw: response(dict(products=[p])))
    facts = read(tmp_path / "evidence" / "facts.json")["facts"]
    assert facts["categoryTree"]["status"] == "MISSING"
    assert facts["title"]["status"] == facts["features"]["status"] == "UNKNOWN"


@pytest.mark.parametrize("changes", [
    dict(asin="B000000001"), dict(asin=None), dict(domainId=1), dict(domainId="5"),
    dict(domainId=True), dict(domainId=None), dict(categoryTree={}),
    dict(categoryTree=[dict(catId=True, name="Root")]),
    dict(categoryTree=[dict(catId=0, name="Root")]),
    dict(categoryTree=[dict(catId=123, name="")]),
    dict(categoryTree=[dict(catId=123, name="Root"), dict(catId=123, name="Again")]),
    dict(rootCategory=999), dict(rootCategory="123"), dict(categories=[True]),
    dict(brand=123), dict(features=[{}]),
])
def test_identity_and_malformed_facts_fail_closed_no_resend(tmp_path, changes):
    p = product()
    p.update(changes)
    calls = []
    def send(*a, **kw):
        calls.append(kw)
        return response(dict(products=[p]))
    with pytest.raises(runner.FactRunStopped, match="RESPONSE_REJECTED"):
        execute(tmp_path, send)
    assert len(calls) == 1
    assert not (tmp_path / "evidence" / "facts.json").exists()
    assert read(tmp_path / "evidence" / "manifest.json")["state"] == "RESPONSE_REJECTED"
    with pytest.raises(runner.FactRunStopped):
        execute(tmp_path, send, evidence_dir=tmp_path / "other-evidence")
    assert len(calls) == 1


@pytest.mark.parametrize("data", [dict(products=[]), dict(products=[product(), product()]),
                                  dict(products=[None]), dict(products=[product()], domainId=1),
                                  dict(products=[product()], error={}), []])
def test_invalid_envelope_is_rejected(tmp_path, data):
    with pytest.raises(runner.FactRunStopped, match="RESPONSE_REJECTED"):
        execute(tmp_path, lambda *a, **kw: response(data))


@pytest.mark.parametrize("raw", [b"not-json", b"[]", b"{\"products\":NaN}",
                                 b'{"products":[],"products":[]}', b"\xff"])
def test_invalid_json_retains_exact_raw_and_stops(tmp_path, raw):
    with pytest.raises(runner.FactRunStopped, match="RESPONSE_REJECTED"):
        execute(tmp_path, lambda *a, **kw: response(raw=raw))
    assert (tmp_path / "evidence" / "raw-response.json").read_bytes() == raw
    assert (tmp_path / "independent" / "attempt" / "attempt.json").exists()


@pytest.mark.parametrize("status", [429, 301, 302, 307, 401, 500])
def test_http_error_no_retry_redirect_wait_or_token_query(tmp_path, status, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *a: pytest.fail("No wait permitted"))
    calls = []
    def send(*a, **kw):
        calls.append(kw)
        return response(status=status)
    with pytest.raises(runner.FactRunStopped, match="RESPONSE_REJECTED"):
        execute(tmp_path, send)
    assert len(calls) == 1 and calls[0]["allow_redirects"] is False
    assert read(tmp_path / "evidence" / "manifest.json")["http_status"] == status


def test_timeout_is_result_unknown_and_new_output_does_not_restore_budget(tmp_path):
    calls = []
    def send(*a, **kw):
        calls.append(kw)
        raise requests.Timeout("credential-bearing exception must not escape")
    with pytest.raises(runner.FactRunStopped, match="^RESULT_UNKNOWN$"):
        execute(tmp_path, send)
    outcome = read(tmp_path / "independent" / "attempt" / "outcome.json")
    assert outcome["state"] == "RESULT_UNKNOWN" and not outcome["automatic_resend_allowed"]
    with pytest.raises(runner.FactRunStopped, match="ATTEMPT_ALREADY_EXISTS"):
        execute(tmp_path, send, evidence_dir=tmp_path / "new-evidence")
    assert len(calls) == 1


@pytest.mark.parametrize("filename,expected_sends", [("attempt.json", 0), ("raw-response.json", 1),
                                                   ("raw-response.sha256", 1), ("facts.json", 1),
                                                   ("manifest.json", 1), ("outcome.json", 1)])
def test_save_failure_never_allows_resend(tmp_path, monkeypatch, filename, expected_sends):
    original = runner._write_new
    calls = []
    def fail(path, content):
        if path.name == filename:
            raise OSError("synthetic save failure")
        return original(path, content)
    monkeypatch.setattr(runner, "_write_new", fail)
    def send(*a, **kw):
        calls.append(kw)
        return response()
    with pytest.raises(runner.FactRunStopped):
        execute(tmp_path, send)
    assert len(calls) == expected_sends
    assert (tmp_path / "independent" / "attempt").is_dir()
    with pytest.raises(runner.FactRunStopped):
        execute(tmp_path, send, evidence_dir=tmp_path / "new-evidence")
    assert len(calls) == expected_sends


def test_success_duplicate_and_concurrent_runs_at_most_one_send(tmp_path):
    calls = []
    def send(*a, **kw):
        calls.append(kw)
        return response()
    def run():
        try:
            return execute(tmp_path, send)["state"]
        except runner.FactRunStopped:
            return "STOPPED"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert sorted(results) == ["STOPPED", "SUCCESS"]
    assert run() == "STOPPED" and len(calls) == 1


def test_send_limit_is_enforced_inside_same_sdk_instance(tmp_path, monkeypatch):
    original = keepa.Keepa._product_query
    calls = []
    def query_twice(self, items, **kwargs):
        original(self, items, **kwargs)
        return original(self, items, **kwargs)
    monkeypatch.setattr(keepa.Keepa, "_product_query", query_twice)
    def send(*a, **kw):
        calls.append(kw)
        return response()
    with pytest.raises(runner.FactRunStopped):
        execute(tmp_path, send)
    assert len(calls) == 1


def test_default_session_has_no_retry_or_environment_proxy(tmp_path, monkeypatch):
    calls = []
    def get(self, url, **kwargs):
        assert self.trust_env is False
        assert self.get_adapter(url).max_retries.total == 0
        assert kwargs["allow_redirects"] is False
        calls.append(url)
        return response()
    monkeypatch.setattr(requests.Session, "get", get)
    execute(tmp_path, None)
    assert calls == [runner.ENDPOINT]


def test_partial_attempt_write_failure_keeps_tombstone(tmp_path, monkeypatch):
    original = runner._write_new
    def fail(path, content):
        if path.name == "attempt.json":
            with path.open("xb") as handle:
                handle.write(content[:10])
            raise OSError("partial save")
        original(path, content)
    monkeypatch.setattr(runner, "_write_new", fail)
    for output in (tmp_path / "evidence", tmp_path / "other"):
        with pytest.raises(runner.FactRunStopped):
            execute(tmp_path, lambda *a, **kw: pytest.fail("No HTTP"), evidence_dir=output)
    assert (tmp_path / "independent" / "attempt" / "attempt.json").stat().st_size == 10


@pytest.mark.parametrize("endpoint", ["token", "query", "category"])
def test_implicit_endpoints_are_rejected_before_reservation(tmp_path, monkeypatch, endpoint):
    def unexpected(self, *a, **kw):
        return self._request(endpoint, {})
    monkeypatch.setattr(keepa.Keepa, "_product_query", unexpected)
    with pytest.raises(runner.FactRunStopped, match="PRE_SEND_STOP"):
        execute(tmp_path, lambda *a, **kw: pytest.fail("No HTTP permitted"))
    assert not (tmp_path / "independent" / "attempt").exists()


def test_git_or_non_independent_or_existing_storage_stops_before_send(tmp_path):
    git_root = tmp_path / "repository"
    git_root.mkdir()
    (git_root / ".git").mkdir()
    for output, attempt in [(git_root / "raw", tmp_path / "attempt"),
                            (tmp_path / "raw", tmp_path / "raw" / "attempt"),
                            (tmp_path, tmp_path / "attempt")]:
        with pytest.raises(runner.FactRunStopped):
            execute(tmp_path, lambda *a, **kw: pytest.fail("No send"),
                    evidence_dir=output, attempt_root=attempt)


def test_sdk_upgrade_or_missing_approval_fails_before_send(tmp_path, monkeypatch):
    with pytest.raises(runner.FactRunStopped):
        execute(tmp_path, lambda *a, **kw: pytest.fail("No send"), authorization_ref="")
    monkeypatch.setattr(runner, "version", lambda _: "1.6.0")
    with pytest.raises(runner.FactRunStopped, match="SDK_VERSION_MISMATCH"):
        execute(tmp_path, lambda *a, **kw: pytest.fail("No send"))


def test_key_in_response_or_authorization_is_never_saved(tmp_path):
    with pytest.raises(runner.FactRunStopped):
        execute(tmp_path, lambda *a, **kw: response(raw=b"synthetic-offline"))
    assert not (tmp_path / "evidence" / "raw-response.json").exists()
    for path in (tmp_path / "independent").rglob("*.json"):
        assert b"synthetic-offline" not in path.read_bytes()
    with pytest.raises(runner.FactRunStopped):
        execute(tmp_path, lambda *a, **kw: pytest.fail("No send"),
                authorization_ref="synthetic-offline", evidence_dir=tmp_path / "other")


def test_cli_no_execute_or_help_is_offline(tmp_path):
    with pytest.raises(SystemExit) as exc:
        runner.main(["--help"])
    assert exc.value.code == 0
    with pytest.raises(SystemExit):
        runner.main(["--authorization-ref", "mock", "--evidence-dir", str(tmp_path / "new")])
