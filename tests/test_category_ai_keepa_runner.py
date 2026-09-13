from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.category_ai_keepa_runner import (
    HARD_REQUEST_CAP,
    HARD_TOKEN_CAP,
    LEAF_PLANS,
    NORMAL_TOKEN_ESTIMATE,
    CategoryAIBenchmarkKeepaRunner,
    ExclusionSet,
    KeepaHTTPTransport,
    KeepaResponse,
    KeepaTransportError,
    RunStopped,
    TokenLedger,
)


def _asin(prefix: str, number: int) -> str:
    return f"{prefix}{number:09d}"


def _exclusions() -> ExclusionSet:
    return ExclusionSet(
        existing_35=frozenset(_asin("E", index) for index in range(35)),
        smoke_5=frozenset(_asin("S", index) for index in range(5)),
    )


class FakeKeepaTransport:
    def __init__(self, *, shortage_leaf: int | None = None, fail_on_query: bool = False) -> None:
        self._api_key = "DUMMY_KEEPA_SECRET"
        self.calls: list[tuple[str, dict]] = []
        self.balance = 2_000
        self.shortage_leaf = shortage_leaf
        self.fail_on_query = fail_on_query
        self.finder: dict[tuple[int, int], list[str]] = {}
        self.candidate_plan = {}
        number = 0
        for plan in LEAF_PLANS:
            count = plan.product_check_target
            if plan.amazon_leaf_category_id == shortage_leaf:
                count -= 1
            page_zero = []
            for _ in range(count):
                asin = _asin("T", number)
                number += 1
                page_zero.append(asin)
                self.candidate_plan[asin] = plan
            self.finder[(plan.amazon_leaf_category_id, 0)] = page_zero
            page_one = []
            if plan.amazon_leaf_category_id == shortage_leaf:
                asin = _asin("T", number)
                number += 1
                page_one.append(asin)
                self.candidate_plan[asin] = plan
            self.finder[(plan.amazon_leaf_category_id, 1)] = page_one

        # Exercise exact exclusions and dedupe without reducing the target pool.
        first = LEAF_PLANS[0]
        original_first = self.finder[(first.amazon_leaf_category_id, 0)]
        self.finder[(first.amazon_leaf_category_id, 0)] = [
            _asin("E", 0),
            _asin("S", 0),
            first.seed_asin,
            original_first[0],
            *original_first,
        ]

    def request(self, endpoint, params):
        self.calls.append((endpoint, dict(params)))
        if endpoint == "query" and self.fail_on_query:
            raise KeepaTransportError("HTTP_403")
        if endpoint == "category":
            ids = [int(value) for value in params["category"].split(",")]
            payload = {"categories": {str(value): {"catId": value} for value in ids}}
            return self._response(payload, 1)
        if endpoint == "query":
            selection = json.loads(params["selection"])
            leaf_id = selection["categories_include"][0]
            page = selection["page"]
            return self._response({"asinList": self.finder[(leaf_id, page)]}, 11)
        if endpoint == "product":
            asins = params["asin"].split(",")
            products = [self._product(asin) for asin in asins]
            return self._response({"products": products}, len(asins))
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    def _response(self, payload, tokens):
        self.balance -= tokens
        return KeepaResponse(
            payload=payload,
            tokens_consumed=tokens,
            tokens_left=self.balance,
            fetched_at="2026-09-12T00:00:00Z",
        )

    def _product(self, asin):
        seed_plan = next((plan for plan in LEAF_PLANS if plan.seed_asin == asin), None)
        plan = seed_plan or self.candidate_plan[asin]
        return {
            "asin": asin,
            "title": f"Mock product {asin}",
            "brand": "Mock Brand",
            "rootCategory": plan.amazon_root_category_id,
            "categoryTree": [
                {"catId": plan.amazon_root_category_id, "name": "Root"},
                {"catId": plan.amazon_leaf_category_id, "name": "Leaf"},
            ],
        }


def _run(tmp_path: Path, transport: FakeKeepaTransport):
    runner = CategoryAIBenchmarkKeepaRunner(
        transport,
        tmp_path,
        _exclusions(),
        initial_available_tokens=2_000,
    )
    return runner.run()


def test_electric_kettle_seed_uses_keepa_root_and_leaf_pair():
    plan = next(plan for plan in LEAF_PLANS if plan.seed_asin == "B0CHHYQHGP")

    assert plan.amazon_root_category_id == 3828871
    assert plan.amazon_leaf_category_id == 16245081
    assert plan.genre == "Home Appliances"


def test_confirmed_taxonomy_corrections_match_live_seed_diagnostic():
    corrected = {
        plan.seed_asin: (
            plan.amazon_root_category_id,
            plan.amazon_leaf_category_id,
            plan.amazon_category_path,
        )
        for plan in LEAF_PLANS
        if plan.seed_asin in {"B099242274", "B0CKWQQXLB", "B0F2NZL4FK"}
    }

    assert corrected == {
        "B099242274": (
            3828871,
            2275305051,
            "ホーム＆キッチン > 家電 > キッチン家電 > 炊飯器・精米器 > 炊飯器",
        ),
        "B0CKWQQXLB": (
            3828871,
            15691411,
            "ホーム＆キッチン > 家電 > キッチン家電 > 電子レンジ・オーブン > 電子レンジ",
        ),
        "B0F2NZL4FK": (
            344845011,
            10395289051,
            "ベビー＆マタニティ > ベビーカー > ベビーカー小物 > ベビーカーシート・クッション",
        ),
    }


def test_full_mock_run_covers_fixed_plan_batches_dedupe_and_blank_resolver_title(tmp_path):
    transport = FakeKeepaTransport()
    result = _run(tmp_path, transport)

    assert result.status == "COMPLETED"
    assert result.stop_code == ""
    assert result.consumed_tokens == NORMAL_TOKEN_ESTIMATE == 617
    assert result.request_count == 42
    assert result.finder_page_count == 32
    assert result.verified_candidate_count == 229

    seed_diagnostic = json.loads((tmp_path / "seed_diagnostic.json").read_text(encoding="utf-8"))
    assert seed_diagnostic["validation_status"] == "PASS"
    assert seed_diagnostic["row_count"] == 32
    assert seed_diagnostic["pass_count"] == 32
    assert seed_diagnostic["failure_count"] == 0
    assert all(row["status"] == "PASS" for row in seed_diagnostic["rows"])

    product_calls = [params for endpoint, params in transport.calls if endpoint == "product"]
    assert [len(params["asin"].split(",")) for params in product_calls] == [32, 50, 50, 50, 50, 29]
    assert all(params["history"] == 0 and params["update"] == -1 for params in product_calls)
    category_calls = [params for endpoint, params in transport.calls if endpoint == "category"]
    assert [len(params["category"].split(",")) for params in category_calls] == [10, 10, 10, 2]
    finder_calls = [params for endpoint, params in transport.calls if endpoint == "query"]
    assert len(finder_calls) == 32
    assert all(json.loads(params["selection"])["page"] == 0 for params in finder_calls)

    verified = [
        json.loads(line)
        for line in (tmp_path / "verified_candidates.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert all(row["resolver_title"] == "" for row in verified)
    excluded = _exclusions().existing_35 | _exclusions().smoke_5 | frozenset(
        plan.seed_asin for plan in LEAF_PLANS
    )
    assert not ({row["asin"] for row in verified} & excluded)
    assert all("live page" in row["verification_scope"] for row in verified)

    serialized = "".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())
    assert "tokensLeft" not in serialized
    assert transport._api_key not in serialized
    assert "OPENAI" not in serialized


def test_seed_validation_records_all_mismatches_and_stops_before_later_endpoints(tmp_path):
    transport = FakeKeepaTransport()
    original = transport._product
    mismatch_roots = {
        LEAF_PLANS[4].seed_asin: 999_000_005,
        LEAF_PLANS[19].seed_asin: 999_000_020,
    }

    def product(asin):
        value = original(asin)
        if asin in mismatch_roots:
            value["rootCategory"] = mismatch_roots[asin]
        return value

    transport._product = product
    result = _run(tmp_path, transport)

    assert result.status == "STOPPED"
    assert result.stop_code == "SEED_CATEGORY_MISMATCH"
    assert result.consumed_tokens == 32
    assert result.request_count == 1
    assert [endpoint for endpoint, _ in transport.calls] == ["product"]

    diagnostic = json.loads((tmp_path / "seed_diagnostic.json").read_text(encoding="utf-8"))
    assert diagnostic["validation_status"] == "FAILED"
    assert diagnostic["row_count"] == 32
    assert diagnostic["failure_count"] == 2
    failures = [row for row in diagnostic["rows"] if row["status"] != "PASS"]
    assert [row["plan_number"] for row in failures] == [5, 20]
    assert all(row["status"] == "ROOT_MISMATCH" for row in failures)
    assert failures[0]["actual_root_category_id"] == 999_000_005
    assert failures[1]["actual_root_category_id"] == 999_000_020
    assert diagnostic["rows"][-1]["plan_number"] == 32
    assert diagnostic["rows"][-1]["status"] == "PASS"


def test_page_one_is_used_only_for_the_shortage_leaf_and_is_frozen(tmp_path):
    shortage_leaf = LEAF_PLANS[3].amazon_leaf_category_id
    transport = FakeKeepaTransport(shortage_leaf=shortage_leaf)
    result = _run(tmp_path, transport)

    assert result.status == "COMPLETED"
    page_one_calls = []
    for endpoint, params in transport.calls:
        if endpoint != "query":
            continue
        selection = json.loads(params["selection"])
        if selection["page"] == 1:
            page_one_calls.append(selection)
    assert len(page_one_calls) == 1
    assert page_one_calls[0]["categories_include"] == [shortage_leaf]

    pages = [
        json.loads(line)
        for line in (tmp_path / "finder_pages.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    frozen = [row for row in pages if row["page"] == 1]
    assert len(frozen) == 1
    assert frozen[0]["amazon_leaf_category_id"] == shortage_leaf
    assert frozen[0]["fetched_at"] == "2026-09-12T00:00:00Z"
    assert frozen[0]["asin_list"]
    assert frozen[0]["selection_hash"]


def test_family_and_identifier_variants_are_excluded(tmp_path):
    transport = FakeKeepaTransport()
    original = transport._product
    candidates = list(transport.candidate_plan)
    first, second, third, fourth = candidates[:4]

    def product(asin):
        value = original(asin)
        if asin in {first, second}:
            value["parentAsin"] = "P000000001"
        if asin in {third, fourth}:
            value["eanList"] = ["4900000000001"]
        return value

    transport._product = product
    result = _run(tmp_path, transport)

    assert result.status == "COMPLETED"
    assert result.verified_candidate_count == 227
    rejected = [
        json.loads(line)
        for line in (tmp_path / "rejected_candidates.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {row["reason"] for row in rejected} == {
        "DUPLICATE_FAMILY",
        "SUBSTANTIAL_DUPLICATE",
    }


def test_valid_pool_shortage_stops_without_more_finder_requests(tmp_path):
    transport = FakeKeepaTransport()
    original = transport._product
    hobby_asins = {
        asin
        for asin, plan in transport.candidate_plan.items()
        if plan.genre == "Hobbies & Collections"
    }

    def product(asin):
        value = original(asin)
        if asin in hobby_asins:
            value["parentAsin"] = "P000000099"
        return value

    transport._product = product
    result = _run(tmp_path, transport)

    assert result.status == "STOPPED"
    assert result.stop_code == "VALID_POOL_SHORTAGE"
    assert result.request_count == 42
    assert sum(endpoint == "query" for endpoint, _ in transport.calls) == 32
    manifest = json.loads((tmp_path / "execution_manifest.json").read_text(encoding="utf-8"))
    assert manifest["verified_pool_count_by_genre"]["Hobbies & Collections"] == 1
    assert manifest["required_new_by_genre"]["Hobbies & Collections"] == 5


def test_token_balance_is_required_and_only_boolean_is_persisted(tmp_path):
    transport = FakeKeepaTransport()
    runner = CategoryAIBenchmarkKeepaRunner(
        transport,
        tmp_path,
        _exclusions(),
        initial_available_tokens=None,
    )
    result = runner.run()

    assert result.status == "STOPPED"
    assert result.stop_code == "TOKEN_BALANCE_NOT_PROVIDED"
    assert transport.calls == []
    manifest = json.loads((tmp_path / "execution_manifest.json").read_text(encoding="utf-8"))
    assert manifest["token_balance_sufficient_for_hard_cap"] is None


def test_balance_below_hard_cap_stops_before_first_request(tmp_path):
    transport = FakeKeepaTransport()
    runner = CategoryAIBenchmarkKeepaRunner(
        transport,
        tmp_path,
        _exclusions(),
        initial_available_tokens=HARD_TOKEN_CAP - 1,
    )
    result = runner.run()

    assert result.status == "STOPPED"
    assert result.stop_code == "TOKEN_BALANCE_BELOW_HARD_CAP"
    assert transport.calls == []
    assert result.token_balance_sufficient_for_hard_cap is False


def test_runner_hard_token_cap_stop_also_persists_partial_manifest(tmp_path):
    transport = FakeKeepaTransport()
    runner = CategoryAIBenchmarkKeepaRunner(
        transport,
        tmp_path,
        _exclusions(),
        initial_available_tokens=2_000,
    )
    runner.ledger.consumed_tokens = HARD_TOKEN_CAP - 31
    result = runner.run()

    assert result.status == "STOPPED"
    assert result.stop_code == "HARD_TOKEN_CAP_BEFORE_REQUEST"
    assert transport.calls == []
    manifest = json.loads((tmp_path / "execution_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "STOPPED"
    assert manifest["stop_code"] == "HARD_TOKEN_CAP_BEFORE_REQUEST"


def test_hard_cap_and_request_cap_stop_before_another_request():
    token_ledger = TokenLedger(consumed_tokens=HARD_TOKEN_CAP)
    with pytest.raises(RunStopped, match="HARD_TOKEN_CAP_BEFORE_REQUEST"):
        token_ledger.reserve("next", 1, HARD_TOKEN_CAP)

    request_ledger = TokenLedger(request_count=HARD_REQUEST_CAP)
    with pytest.raises(RunStopped, match="HARD_REQUEST_CAP_BEFORE_REQUEST"):
        request_ledger.reserve("next", 1, HARD_TOKEN_CAP)


def test_unexpected_token_consumption_stops_and_preserves_partial_result(tmp_path):
    transport = FakeKeepaTransport()
    original = transport.request

    def overcharge(endpoint, params):
        response = original(endpoint, params)
        if len(transport.calls) == 1:
            return KeepaResponse(response.payload, 33, response.tokens_left, response.fetched_at)
        return response

    transport.request = overcharge
    result = _run(tmp_path, transport)

    assert result.status == "STOPPED"
    assert result.stop_code == "UNEXPECTED_TOKEN_CONSUMPTION"
    assert result.request_count == 1
    assert result.consumed_tokens == 33
    assert (tmp_path / "execution_manifest.json").exists()
    assert (tmp_path / "finder_pages.jsonl").exists()


def test_transport_failure_does_not_fallback_and_preserves_partial_result(tmp_path):
    transport = FakeKeepaTransport(fail_on_query=True)
    result = _run(tmp_path, transport)

    assert result.status == "STOPPED"
    assert result.stop_code == "TRANSPORT_FAILURE"
    endpoints = [endpoint for endpoint, _ in transport.calls]
    assert endpoints.count("query") == 1
    assert set(endpoints) <= {"product", "category", "query"}
    manifest = json.loads((tmp_path / "execution_manifest.json").read_text(encoding="utf-8"))
    assert manifest["automatic_fallback"] is False
    assert manifest["status"] == "STOPPED"


def test_http_transport_attempts_once_and_never_exposes_key_in_error():
    secret = "DUMMY_KEEPA_SECRET"

    class Response:
        status_code = 429

        @staticmethod
        def json():
            return {"error": "not_enough_token", "tokensLeft": 0}

    class Session:
        def __init__(self):
            self.calls = []

        def get(self, url, *, params, timeout):
            self.calls.append((url, params, timeout))
            return Response()

    session = Session()
    transport = KeepaHTTPTransport(secret, session=session)
    with pytest.raises(KeepaTransportError) as exc_info:
        transport.request("query", {"domain": 5, "selection": "{}"})

    assert len(session.calls) == 1
    assert session.calls[0][1]["key"] == secret
    assert secret not in str(exc_info.value)
    assert str(exc_info.value) == "HTTP_429"
