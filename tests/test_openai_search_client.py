import json

import pytest

from modules.asin_resolver import build_search_title
from modules.config import load_settings
from modules.openai_search_client import (
    EXISTENCE_NOT_VERIFIED,
    KEEPA_NOT_CHECKED,
    MAX_CANDIDATES_PER_ITEM,
    MODEL_STATUS_CANDIDATES,
    MODEL_STATUS_ERROR,
    MODEL_STATUS_UNKNOWN,
    OPENAI_RESPONSE_SCHEMA,
    OpenAISearchError,
    VALIDATION_STATUS_INVALID,
    VALIDATION_STATUS_VALID,
    build_openai_search_inputs,
    build_openai_search_prompt,
    execute_openai_web_search,
    summarize_openai_results,
    summarize_openai_sources,
    validate_amazon_jp_url,
)


class FakeResponses:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error=None):
        self.responses = FakeResponses(response=response, error=error)


class FakeFactory:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.client = None

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        self.client = FakeClient(response=self.response, error=self.error)
        return self.client


class FakeResponse:
    def __init__(self, payload, *, output=None, usage=None, request_id="req_test"):
        self.output_text = json.dumps(payload)
        self.output = output or []
        self.usage = usage or {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
        self.model = "gpt-5.6-luna"
        self._request_id = request_id


def _inputs(text="Original title"):
    return build_openai_search_inputs(text, build_search_title)


def _candidate_result(source_id="T0001", url="https://www.amazon.co.jp/dp/B07TSC47PH"):
    return {
        "source_id": source_id,
        "searched_title": "search title",
        "status": "CANDIDATES",
        "candidates": [{"amazon_url": url, "note": "candidate"}],
        "note": "",
    }


def test_build_inputs_assigns_t_ids_and_keeps_input_title_unchanged():
    raw_title = "  [Direct From Japan] Product  "

    rows = _inputs(f"{raw_title}\nSecond Product")

    assert [row.source_id for row in rows] == ["T0001", "T0002"]
    assert rows[0].input_title == raw_title
    assert rows[0].search_title == "Product"
    assert rows[1].input_title == "Second Product"


@pytest.mark.parametrize(
    ("input_text", "error_code"),
    [("", "INPUT_EMPTY"), ("\n\n", "INPUT_EMPTY"), ("\n".join(str(i) for i in range(6)), "INPUT_LIMIT_EXCEEDED")],
)
def test_build_inputs_rejects_empty_and_more_than_five_items(input_text, error_code):
    with pytest.raises(OpenAISearchError) as exc_info:
        _inputs(input_text)

    assert exc_info.value.code == error_code


def test_prompt_uses_search_titles_and_requires_all_source_ids():
    prompt = build_openai_search_prompt(_inputs("[New!] Product\nSecond"))

    assert "T0001" in prompt
    assert '"search_title": "Product"' in prompt
    assert "Return every provided source_id exactly once" in prompt
    assert "Do not invent or guess URLs" in prompt
    assert "Japanese product names, katakana transliterations" in prompt
    assert "manufacturer websites, official information" in prompt
    assert "Return only HTTPS Amazon.co.jp product-page URLs" in prompt


def test_openai_request_uses_responses_web_search_and_strict_schema():
    response = FakeResponse({"results": [_candidate_result()]})
    factory = FakeFactory(response=response)
    timestamps = iter([10.0, 10.25])

    run = execute_openai_web_search(
        _inputs(),
        "test-key",
        client_factory=factory,
        clock=lambda: next(timestamps),
    )

    assert factory.calls == [{"api_key": "test-key", "timeout": 60.0, "max_retries": 0}]
    assert len(factory.client.responses.calls) == 1
    request = factory.client.responses.calls[0]
    assert request["model"] == "gpt-5.6-luna"
    assert request["tools"] == [
        {
            "type": "web_search",
            "user_location": {"type": "approximate", "country": "JP"},
            "search_context_size": "medium",
        }
    ]
    assert "filters" not in request["tools"][0]
    assert request["text"]["format"] == OPENAI_RESPONSE_SCHEMA
    assert request["text"]["format"]["strict"] is True
    assert request["reasoning"] == {"effort": "low"}
    assert request["store"] is False
    assert request["include"] == ["web_search_call.action.sources"]
    assert run.usage["elapsed_ms"] == 250


def test_missing_api_key_stops_before_client_creation():
    factory = FakeFactory()

    with pytest.raises(OpenAISearchError) as exc_info:
        execute_openai_web_search(_inputs(), "", client_factory=factory)

    assert exc_info.value.code == "OPENAI_API_KEY_MISSING"
    assert factory.calls == []


def test_candidate_rows_keep_model_and_validation_states_separate():
    response = FakeResponse({"results": [_candidate_result()]})

    run = execute_openai_web_search(_inputs(), "test-key", client_factory=FakeFactory(response=response))

    row = run.rows[0]
    assert row["model_status"] == MODEL_STATUS_CANDIDATES
    assert row["validation_status"] == VALIDATION_STATUS_VALID
    assert row["candidate_state"] == "OPENAI_CANDIDATE"
    assert row["asin"] == "B07TSC47PH"
    assert row["keepa_status"] == KEEPA_NOT_CHECKED
    assert row["existence_status"] == EXISTENCE_NOT_VERIFIED
    assert "FOUND" not in row.values()


def test_unknown_and_error_model_statuses_are_preserved():
    response = FakeResponse(
        {
            "results": [
                {
                    "source_id": "T0001",
                    "searched_title": "first",
                    "status": "UNKNOWN",
                    "candidates": [],
                    "note": "No candidate found",
                },
                {
                    "source_id": "T0002",
                    "searched_title": "second",
                    "status": "ERROR",
                    "candidates": [],
                    "note": "Model error",
                },
            ]
        }
    )

    run = execute_openai_web_search(
        _inputs("One\nTwo"),
        "test-key",
        client_factory=FakeFactory(response=response),
    )

    assert [row["model_status"] for row in run.rows] == [
        MODEL_STATUS_UNKNOWN,
        MODEL_STATUS_ERROR,
    ]
    assert all(row["amazon_url"] == "" for row in run.rows)


def test_missing_duplicate_and_unexpected_source_ids_are_explicitly_handled():
    response = FakeResponse(
        {
            "results": [
                _candidate_result("T0001"),
                _candidate_result("T0001"),
                _candidate_result("T9999"),
            ]
        }
    )

    run = execute_openai_web_search(
        _inputs("One\nTwo"),
        "test-key",
        client_factory=FakeFactory(response=response),
    )

    assert run.rows[0]["model_status"] == MODEL_STATUS_ERROR
    assert run.rows[0]["note"] == "Duplicate source_id in OpenAI response"
    assert run.rows[1]["model_status"] == MODEL_STATUS_ERROR
    assert run.rows[1]["note"] == "OpenAI response missing source_id"
    assert run.diagnostics == ["Unexpected source_id in OpenAI response: T9999"]


@pytest.mark.parametrize(
    ("url", "expected_asin", "expected_status"),
    [
        ("https://www.amazon.co.jp/dp/B07TSC47PH", "B07TSC47PH", VALIDATION_STATUS_VALID),
        ("https://amazon.co.jp/gp/product/B07TSC47PH?th=1", "B07TSC47PH", VALIDATION_STATUS_VALID),
        ("http://www.amazon.co.jp/dp/B07TSC47PH", "", "INVALID_URL_SCHEME"),
        ("https://amazon.com/dp/B07TSC47PH", "", "INVALID_URL_HOST"),
        ("https://www.amazon.co.jp/dp/INVALID", "", "INVALID_URL_PATH"),
        ("https://example.com/item/B07TSC47PH", "", "INVALID_URL_HOST"),
    ],
)
def test_url_validation_only_accepts_https_amazon_jp_dp_or_gp_product(url, expected_asin, expected_status):
    assert validate_amazon_jp_url(url) == (expected_asin, expected_status)


def test_candidate_urls_are_deduplicated_by_url_and_asin_and_limited_to_three():
    candidates = [
        {"amazon_url": "https://www.amazon.co.jp/dp/B000000001", "note": "first"},
        {"amazon_url": "https://www.amazon.co.jp/gp/product/B000000001", "note": "same asin"},
        {"amazon_url": "https://www.amazon.co.jp/dp/B000000002", "note": "second"},
        {"amazon_url": "https://www.amazon.co.jp/dp/B000000003", "note": "third"},
        {"amazon_url": "https://www.amazon.co.jp/dp/B000000004", "note": "fourth"},
    ]
    response = FakeResponse(
        {
            "results": [
                {
                    "source_id": "T0001",
                    "searched_title": "title",
                    "status": "CANDIDATES",
                    "candidates": candidates,
                    "note": "",
                }
            ]
        }
    )

    run = execute_openai_web_search(_inputs(), "test-key", client_factory=FakeFactory(response=response))

    assert len(run.rows) == MAX_CANDIDATES_PER_ITEM
    assert [row["asin"] for row in run.rows] == ["B000000001", "B000000002", "B000000003"]


def test_all_invalid_urls_are_not_treated_as_valid_candidates():
    response = FakeResponse(
        {
            "results": [
                {
                    "source_id": "T0001",
                    "searched_title": "title",
                    "status": "CANDIDATES",
                    "candidates": [
                        {"amazon_url": "https://amazon.com/dp/B07TSC47PH", "note": "external"},
                        {"amazon_url": "https://www.amazon.co.jp/dp/INVALID", "note": "invalid"},
                    ],
                    "note": "",
                }
            ]
        }
    )

    run = execute_openai_web_search(_inputs(), "test-key", client_factory=FakeFactory(response=response))

    assert run.rows[0]["model_status"] == MODEL_STATUS_CANDIDATES
    assert run.rows[0]["validation_status"] == VALIDATION_STATUS_INVALID
    assert run.rows[0]["amazon_url"] == ""
    assert run.rows[0]["asin"] == ""


def test_empty_and_invalid_structured_outputs_are_errors():
    factory = FakeFactory(response=type("EmptyResponse", (), {"output_text": "", "output": []})())

    with pytest.raises(OpenAISearchError) as exc_info:
        execute_openai_web_search(_inputs(), "test-key", client_factory=factory)

    assert exc_info.value.code == "EMPTY_RESPONSE"


@pytest.mark.parametrize(
    ("exception_name", "expected_code"),
    [
        ("AuthenticationError", "AUTHENTICATION_ERROR"),
        ("RateLimitError", "RATE_LIMIT"),
        ("APITimeoutError", "TIMEOUT"),
        ("APIConnectionError", "CONNECTION_ERROR"),
        ("InternalServerError", "SERVER_ERROR"),
        ("BadRequestError", "REQUEST_ERROR"),
    ],
)
def test_openai_error_categories_are_user_safe(exception_name, expected_code):
    error = type(exception_name, (Exception,), {})()

    with pytest.raises(OpenAISearchError) as exc_info:
        execute_openai_web_search(
            _inputs(),
            "test-key",
            client_factory=FakeFactory(error=error),
        )

    assert exc_info.value.code == expected_code


def test_usage_request_id_web_calls_and_source_count_are_collected():
    response = FakeResponse(
        {"results": [_candidate_result()]},
        output=[
            {"type": "web_search_call", "action": {"sources": [{"url": "a"}, {"url": "b"}]}},
            {"type": "message"},
        ],
        usage={"input_tokens": 11, "output_tokens": 22, "total_tokens": 33},
        request_id="req_123",
    )
    timestamps = iter([1.0, 1.5])

    run = execute_openai_web_search(
        _inputs(),
        "test-key",
        client_factory=FakeFactory(response=response),
        clock=lambda: next(timestamps),
    )

    assert run.usage == {
        "model": "gpt-5.6-luna",
        "api_request_count": 1,
        "input_tokens": 11,
        "output_tokens": 22,
        "total_tokens": 33,
        "web_search_call_count": 1,
        "source_count": 2,
        "elapsed_ms": 500,
        "request_id": "req_123",
    }
    assert run.sources == [
        {"url": "a", "title": "", "domain": "", "source_type": ""},
        {"url": "b", "title": "", "domain": "", "source_type": ""},
    ]


def test_web_search_sources_keep_minimal_details_deduplicate_urls_and_preserve_order():
    response = FakeResponse(
        {"results": [_candidate_result()]},
        output=[
            {
                "type": "web_search_call",
                "action": {
                    "sources": [
                        {
                            "url": "https://www.amazon.co.jp/dp/B0CGR2PP17",
                            "title": "First Amazon page",
                            "type": "url",
                        },
                        {
                            "url": "https://www.amazon.co.jp/dp/B0CGR2PP17",
                            "title": "Duplicate Amazon page",
                        },
                        {
                            "url": "not a valid URL",
                            "title": "Malformed source",
                        },
                        {
                            "url": "https://example.com/item",
                        },
                    ]
                },
            }
        ],
    )

    run = execute_openai_web_search(
        _inputs(),
        "test-key",
        client_factory=FakeFactory(response=response),
    )

    assert run.usage["source_count"] == 4
    assert run.sources == [
        {
            "url": "https://www.amazon.co.jp/dp/B0CGR2PP17",
            "title": "First Amazon page",
            "domain": "www.amazon.co.jp",
            "source_type": "url",
        },
        {
            "url": "not a valid URL",
            "title": "Malformed source",
            "domain": "",
            "source_type": "",
        },
        {
            "url": "https://example.com/item",
            "title": "",
            "domain": "example.com",
            "source_type": "",
        },
    ]
    assert summarize_openai_sources(run.sources) == {
        "deduplicated_sources": 3,
        "amazon_jp_sources": 1,
    }
    assert all("api_key" not in source for source in run.sources)


def test_web_search_source_without_url_is_retained_without_stopping_processing():
    response = FakeResponse(
        {"results": [_candidate_result()]},
        output=[
            {
                "type": "web_search_call",
                "action": {"sources": [{"title": "Title without URL"}]},
            }
        ],
    )

    run = execute_openai_web_search(
        _inputs(),
        "test-key",
        client_factory=FakeFactory(response=response),
    )

    assert run.sources == [
        {"url": "", "title": "Title without URL", "domain": "", "source_type": ""}
    ]


def test_web_search_source_objects_use_safe_attribute_access():
    source = type(
        "Source",
        (),
        {"url": "https://amazon.co.jp/gp/product/B0DCZVRR52", "type": "url"},
    )()
    action = type("Action", (), {"sources": [source]})()
    output_item = type("OutputItem", (), {"type": "web_search_call", "action": action})()
    response = FakeResponse({"results": [_candidate_result()]}, output=[output_item])

    run = execute_openai_web_search(
        _inputs(),
        "test-key",
        client_factory=FakeFactory(response=response),
    )

    assert run.sources == [
        {
            "url": "https://amazon.co.jp/gp/product/B0DCZVRR52",
            "title": "",
            "domain": "amazon.co.jp",
            "source_type": "url",
        }
    ]


def test_summary_counts_only_locally_validated_urls():
    rows = [
        {
            "source_id": "T0001",
            "model_status": "CANDIDATES",
            "validation_status": VALIDATION_STATUS_VALID,
        },
        {
            "source_id": "T0001",
            "model_status": "CANDIDATES",
            "validation_status": VALIDATION_STATUS_VALID,
        },
        {
            "source_id": "T0002",
            "model_status": "UNKNOWN",
            "validation_status": "NOT_APPLICABLE",
        },
        {
            "source_id": "T0003",
            "model_status": "ERROR",
            "validation_status": "NOT_APPLICABLE",
        },
    ]

    assert summarize_openai_results(rows) == {
        "candidate_products": 1,
        "valid_url_candidates": 2,
        "unknown_products": 1,
        "error_products": 1,
    }


def test_config_exposes_openai_key_without_affecting_keepa_settings(monkeypatch):
    monkeypatch.setenv("KEEPA_API_KEY", "keepa-test-value")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-value")

    settings = load_settings()

    assert settings.keepa_api_key == "keepa-test-value"
    assert settings.openai_api_key == "openai-test-value"
