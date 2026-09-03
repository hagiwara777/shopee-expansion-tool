"""No external I/O: fake HTTP responses and tiny in-memory synthetic images only."""
from copy import deepcopy
from io import BytesIO
import json

import pytest
import requests
from PIL import Image

from modules.ph_image_safety import ImageSafetyError, MODEL
from modules.ph_image_safety_api import OpenAIImageAnalyzer, RESPONSES_URL

URL = "https://m.media-amazon.com/images/I/one.png"
URL2 = "https://m.media-amazon.com/images/I/two.png"


def png():
    output = BytesIO()
    Image.new("RGB", (4, 4), "white").save(output, format="PNG")
    return output.getvalue()


def body(semantic="NO_SIGNAL", **overrides):
    result = {
        "status": "completed",
        "model": MODEL,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps({"status": semantic, "note": "synthetic"}),
                    }
                ],
            }
        ],
    }
    result.update(overrides)
    return result


class Response:
    def __init__(self, status=200, data=None, raw=None):
        self.status_code, self.data, self.raw = (
            status,
            data,
            raw if raw is not None else png(),
        )
        self.closed = False

    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data

    def iter_content(self, chunk_size):
        yield self.raw

    def close(self):
        self.closed = True


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def _call(self, url, **kwargs):
        self.calls.append((url, deepcopy(kwargs)))
        assert self.responses, "unexpected extra external call"
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    get = _call
    post = _call


def analyzer(*responses, images=None, enabled=True, key="synthetic-test-credential"):
    api = Session(*(responses or [Response(data=body())]))
    imgs = Session(*(images or [Response()]))
    waits = []
    client = OpenAIImageAnalyzer(
        api_key=key,
        enabled=enabled,
        session=api,
        image_session=imgs,
        sleep=waits.append,
    )
    return client, api, imgs, waits


def test_request_uses_pinned_model_structured_output_storage_off_and_exact_images():
    client, api, imgs, _ = analyzer(images=[Response(), Response(), Response()])
    result = client.analyze(
        (URL, URL2, "https://m.media-amazon.com/images/I/three.png")
    )
    assert result["system_status"] == "COMPLETED" and result["ai_status"] == "NO_SIGNAL"
    assert len(api.calls) == 1 and len(imgs.calls) == 3
    url, request = api.calls[0]
    assert url == RESPONSES_URL
    payload = request["json"]
    assert payload["model"] == MODEL and payload["store"] is False
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert payload["text"]["format"]["schema"]["additionalProperties"] is False
    inputs = payload["input"][0]["content"]
    assert sum(p["type"] == "input_image" for p in inputs) == 3
    assert all(
        p["image_url"].startswith("data:image/png;base64,")
        for p in inputs
        if p["type"] == "input_image"
    )
    assert "data:" not in json.dumps(
        result
    ) and "synthetic-test-credential" not in json.dumps(result)
    assert request["allow_redirects"] is False
    assert all(kwargs["allow_redirects"] is False for _, kwargs in imgs.calls)


@pytest.mark.parametrize(
    "first",
    [
        Response(429),
        Response(500),
        Response(503),
        requests.Timeout(),
        requests.ConnectionError(),
    ],
)
def test_api_transient_retries_once(first):
    client, api, _, waits = analyzer(first, Response(data=body("REVIEW")))
    result = client.analyze((URL,))
    assert result["attempts"] == 2 and result["ai_status"] == "REVIEW"
    assert len(api.calls) == 2 and waits == [1]


@pytest.mark.parametrize(
    "responses",
    [
        (Response(429), Response(429)),
        (Response(503), Response(500)),
        (requests.Timeout(), requests.Timeout()),
    ],
)
def test_retry_exhaustion_is_product_error(responses):
    client, api, _, _ = analyzer(*responses)
    result = client.analyze((URL,))
    assert result["system_status"] == "ERROR" and result["ai_status"] is None
    assert result["attempts"] == len(api.calls) == 2


@pytest.mark.parametrize(
    "code,data",
    [
        (400, None),
        (401, None),
        (402, None),
        (403, None),
        (404, None),
        (422, None),
        (429, {"error": {"code": "insufficient_quota"}}),
        (200, {"error": {"code": "invalid_api_key"}}),
    ],
)
def test_auth_contract_unsupported_configuration_is_global_stop_without_retry(
    code, data
):
    client, api, _, waits = analyzer(Response(code, data))
    with pytest.raises(ImageSafetyError):
        client.analyze((URL,))
    assert len(api.calls) == 1 and waits == []


@pytest.mark.parametrize(
    "enabled,key", [(False, "test"), (True, ""), (True, "bad\nkey")]
)
def test_preflight_stops_before_any_network(enabled, key):
    client, api, imgs, _ = analyzer(enabled=enabled, key=key)
    with pytest.raises(ImageSafetyError):
        client.analyze((URL,))
    assert not api.calls and not imgs.calls


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/private",
        "https://example.com/one.jpg",
        "file:///private",
        "https://m.media-amazon.com.evil.test/images/I/one.jpg",
        "https://m.media-amazon.com/images/I/../one.jpg",
    ],
)
def test_image_url_is_restricted_before_network(url):
    client, api, imgs, _ = analyzer()
    with pytest.raises(ImageSafetyError):
        client.analyze((url,))
    assert not api.calls and not imgs.calls


def test_more_than_three_images_stops_before_network():
    client, api, imgs, _ = analyzer()
    with pytest.raises(ImageSafetyError):
        client.analyze(
            tuple(f"https://m.media-amazon.com/images/I/{i}.jpg" for i in range(4))
        )
    assert not api.calls and not imgs.calls


def test_missing_images_does_not_call_api():
    client, api, _, _ = analyzer(images=[Response(404)])
    result = client.analyze((URL,))
    assert result["system_status"] == "UNAVAILABLE" and result["attempts"] == 0
    assert not api.calls


@pytest.mark.parametrize(
    "response",
    [Response(302), Response(raw=b"not an image"), Response(raw=b"<html>error</html>")],
)
def test_invalid_image_or_redirect_is_product_error(response):
    client, api, _, _ = analyzer(images=[response])
    result = client.analyze((URL,))
    assert result["system_status"] == "ERROR" and not api.calls
    assert response.closed


def test_large_image_is_rejected_without_api(monkeypatch):
    monkeypatch.setattr("modules.ph_image_safety_api.MAX_IMAGE_BYTES", 10)
    client, api, _, _ = analyzer()
    assert client.analyze((URL,))["system_status"] == "ERROR"
    assert not api.calls


def test_image_transient_get_retries_once_and_closes_responses():
    first, second = Response(500), Response()
    client, api, imgs, waits = analyzer(images=[first, second])
    assert client.analyze((URL,))["ai_status"] == "NO_SIGNAL"
    assert len(imgs.calls) == 2 and len(api.calls) == 1 and waits == [1]
    assert first.closed and second.closed


def test_partial_images_do_not_hide_failure_with_no_signal():
    client, _, _, _ = analyzer(images=[Response(), Response(404)])
    result = client.analyze((URL, URL2))
    assert result["system_status"] == "PARTIAL" and result["ai_status"] == "NO_SIGNAL"
    assert [i["status"] for i in result["images"]] == ["LOADED", "UNAVAILABLE"]


@pytest.mark.parametrize(
    "modified",
    [
        body("BLOCK"),
        body("SAFE"),
        body(output=[]),
        body(output="wrong"),
        body(status="failed"),
        body(
            output=[
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"status":"NO_SIGNAL","note":"x","extra":true}',
                        }
                    ],
                }
            ]
        ),
        body(
            output=[
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"status":"REVIEW","status":"NO_SIGNAL","note":"x"}',
                        }
                    ],
                }
            ]
        ),
    ],
)
def test_bad_ai_output_is_product_error(modified):
    client, api, _, _ = analyzer(Response(data=modified))
    result = client.analyze((URL,))
    assert result["system_status"] == "ERROR" and result["ai_status"] is None
    assert len(api.calls) == 1


@pytest.mark.parametrize(
    "modified",
    [
        body(status="incomplete"),
        body(
            output=[
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "refusal", "refusal": "x"}],
                }
            ]
        ),
    ],
)
def test_incomplete_or_refusal_has_no_invented_semantic_result(modified):
    client, _, _, _ = analyzer(Response(data=modified))
    result = client.analyze((URL,))
    assert result["ai_status"] is None and result["system_status"] == "ERROR"


def test_wrong_response_model_stops():
    client, _, _, _ = analyzer(Response(data=body(model="gpt-5.6-luna")))
    with pytest.raises(ImageSafetyError):
        client.analyze((URL,))


@pytest.mark.parametrize(
    "code",
    ["invalid_image_format", "image_parse_error", "image_content_policy_violation"],
)
def test_api_image_failure_is_product_error_not_global_configuration_error(code):
    client, api, _, _ = analyzer(Response(400, {"error": {"code": code}}))
    result = client.analyze((URL,))
    assert result["system_status"] == "ERROR" and result["ai_status"] is None
    assert len(api.calls) == 1
