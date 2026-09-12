"""No external I/O: Responses transport tests use an in-memory fake session."""

from copy import deepcopy
import json

import pytest
import requests

from modules.category_ai_core import (
    BenchmarkRequestProfile,
    CategoryAIError,
    CategoryNode,
    ProductEvidence,
    StepRequest,
)
from modules.category_ai_openai import OpenAIResponsesCategoryProvider, RESPONSES_URL
from modules.category_ai_prompts import PROMPT_VERSION, SYSTEM_PROMPT


def profile():
    return BenchmarkRequestProfile(
        model="gpt-5.6-terra",
        reasoning_effort="low",
        text_verbosity="low",
        max_output_tokens=512,
        service_tier="default",
        timeout_seconds=30,
    )


def step_request():
    return StepRequest(
        product=ProductEvidence(
            "PH",
            "P1",
            "Synthetic powder refill",
            resolver_title="Unrelated tablet accessory",
        ),
        parent_category_id=None,
        current_category_path="ROOT",
        candidates=(CategoryNode(10, None, "Health", "Health", True),),
    )


def response_body(*, output_text=None, **overrides):
    structured = output_text or json.dumps(
        {
            "prompt_version": PROMPT_VERSION,
            "product_type_summary": "synthetic",
            "decision": "SELECT",
            "selected_category_id": 10,
            "confidence": 0.8,
            "short_reason": "synthetic selection",
        }
    )
    body = {
        "status": "completed",
        "model": "gpt-5.6-terra",
        "service_tier": "default",
        "output_text": structured,
        "usage": {
            "input_tokens": 120,
            "input_tokens_details": {
                "cached_tokens": 20,
                "cache_write_tokens": 10,
            },
            "output_tokens": 12,
        },
    }
    body.update(overrides)
    return body


class Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = response_body() if body is None else body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class Session:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, deepcopy(kwargs)))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_request_payload_uses_entire_fixed_profile_and_strict_schema():
    session = Session(Response())
    provider = OpenAIResponsesCategoryProvider("synthetic-secret", session=session)
    result = provider.select(step_request(), profile())
    assert result.selected_category_id == 10
    assert result.usage.input_tokens == 120
    assert result.usage.cached_tokens == 20
    assert result.usage.cache_write_tokens == 10
    assert result.served_service_tier == "default"
    assert len(session.calls) == 1
    url, request = session.calls[0]
    assert url == RESPONSES_URL
    payload = request["json"]
    assert payload["model"] == "gpt-5.6-terra"
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["text"]["verbosity"] == "low"
    assert payload["max_output_tokens"] == 512
    assert payload["service_tier"] == "default"
    assert payload["store"] is False and payload["stream"] is False
    assert payload["truncation"] == "disabled"
    assert payload["tool_choice"] == "none"
    assert payload["parallel_tool_calls"] is False
    assert payload["text"]["format"]["strict"] is True
    assert payload["text"]["format"]["schema"]["additionalProperties"] is False
    assert payload["input"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    user_input = json.loads(payload["input"][1]["content"])
    assert set(user_input) == {
        "prompt_version",
        "marketplace",
        "product",
        "category_context",
    }
    assert "synthetic-secret" not in json.dumps(payload)
    assert request["timeout"] == 30


@pytest.mark.parametrize(
    "outcome,code",
    [
        (requests.Timeout(), "TIMEOUT"),
        (requests.ConnectionError(), "NETWORK_ERROR"),
        (Response(429), "RATE_LIMIT"),
        (Response(500), "HTTP_500"),
        (Response(200, {}), "EMPTY_RESPONSE"),
        (Response(200, ValueError("raw parse detail")), "INVALID_JSON"),
        (Response(200, response_body(status="incomplete")), "INCOMPLETE_RESPONSE"),
    ],
)
def test_transport_failures_return_only_safe_codes(outcome, code):
    provider = OpenAIResponsesCategoryProvider("synthetic-secret", session=Session(outcome))
    with pytest.raises(CategoryAIError) as raised:
        provider.select(step_request(), profile())
    assert raised.value.code == code
    assert "synthetic-secret" not in str(raised.value)
    assert "raw parse detail" not in str(raised.value)


def test_refusal_and_empty_output_fail_closed():
    refusal = response_body(
        output_text="",
        output=[
            {
                "type": "message",
                "content": [{"type": "refusal", "refusal": "synthetic"}],
            }
        ],
    )
    refusal.pop("output_text")
    provider = OpenAIResponsesCategoryProvider(
        "synthetic-secret", session=Session(Response(200, refusal))
    )
    with pytest.raises(CategoryAIError, match="REFUSAL"):
        provider.select(step_request(), profile())


def test_key_preflight_stops_before_any_session_call():
    session = Session(Response())
    with pytest.raises(CategoryAIError, match="OPENAI_API_KEY_UNAVAILABLE"):
        OpenAIResponsesCategoryProvider("\n", session=session)
    assert not session.calls
