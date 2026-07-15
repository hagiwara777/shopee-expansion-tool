"""Independent OpenAI Web search test helpers for the ASIN Resolver UI."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time
from typing import Any, Callable, Iterable
from urllib.parse import urlparse


MAX_OPENAI_TEST_ITEMS = 5
MAX_CANDIDATES_PER_ITEM = 3
OPENAI_SEARCH_MODEL = "gpt-5.6-luna"
OPENAI_REQUEST_TIMEOUT_SECONDS = 60.0

MODEL_STATUS_CANDIDATES = "CANDIDATES"
MODEL_STATUS_UNKNOWN = "UNKNOWN"
MODEL_STATUS_ERROR = "ERROR"
MODEL_STATUSES = {
    MODEL_STATUS_CANDIDATES,
    MODEL_STATUS_UNKNOWN,
    MODEL_STATUS_ERROR,
}

VALIDATION_STATUS_VALID = "URL_FORMAT_VALIDATED"
VALIDATION_STATUS_INVALID = "INVALID_URLS"
VALIDATION_STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"
KEEPA_NOT_CHECKED = "KEEPA_NOT_CHECKED"
EXISTENCE_NOT_VERIFIED = "EXISTENCE_NOT_VERIFIED"

_TEST_SOURCE_ID_PATTERN = re.compile(r"^T\d{4}$")
_AMAZON_JP_HOSTS = {"amazon.co.jp", "www.amazon.co.jp"}
_AMAZON_ASIN_PATH_PATTERN = re.compile(
    r"(?:^|/)(?:dp/|gp/product/)([A-Z0-9]{10})(?=/|$)",
    re.IGNORECASE,
)


OPENAI_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "name": "amazon_jp_candidate_results",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["results"],
        "properties": {
            "results": {
                "type": "array",
                "maxItems": MAX_OPENAI_TEST_ITEMS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "source_id",
                        "searched_title",
                        "status",
                        "candidates",
                        "note",
                    ],
                    "properties": {
                        "source_id": {"type": "string"},
                        "searched_title": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": sorted(MODEL_STATUSES),
                        },
                        "candidates": {
                            "type": "array",
                            "maxItems": MAX_CANDIDATES_PER_ITEM,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["amazon_url", "note"],
                                "properties": {
                                    "amazon_url": {"type": "string"},
                                    "note": {"type": "string"},
                                },
                            },
                        },
                        "note": {"type": "string"},
                    },
                },
            }
        },
    },
}


@dataclass(frozen=True)
class OpenAISearchInput:
    source_id: str
    input_title: str
    search_title: str


@dataclass(frozen=True)
class OpenAISearchRun:
    rows: list[dict[str, str]]
    usage: dict[str, int | str | None]
    sources: list[dict[str, str]]
    diagnostics: list[str]


class OpenAISearchError(RuntimeError):
    """A concise, user-safe error raised by the independent test client."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.user_message = message


def build_openai_search_inputs(
    product_names_text: str,
    search_title_builder: Callable[[str], str],
) -> list[OpenAISearchInput]:
    """Build isolated T-series inputs without changing the source title text."""

    titles = [line for line in (product_names_text or "").splitlines() if line.strip()]
    if not titles:
        raise OpenAISearchError("INPUT_EMPTY", "商品名を1件以上入力してください。")
    if len(titles) > MAX_OPENAI_TEST_ITEMS:
        raise OpenAISearchError(
            "INPUT_LIMIT_EXCEEDED",
            f"OpenAI検索テストは1回につき最大{MAX_OPENAI_TEST_ITEMS}件です。",
        )

    return [
        OpenAISearchInput(
            source_id=f"T{index:04d}",
            input_title=title,
            search_title=search_title_builder(title),
        )
        for index, title in enumerate(titles, 1)
    ]


def openai_search_fingerprint(
    inputs: Iterable[OpenAISearchInput],
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (item.source_id, item.input_title, item.search_title)
        for item in inputs
    )


def build_openai_search_prompt(inputs: Iterable[OpenAISearchInput]) -> str:
    materialized = list(inputs)
    _validate_inputs(materialized)
    input_items = [
        {"source_id": item.source_id, "search_title": item.search_title}
        for item in materialized
    ]
    return (
        "Use web search to identify each input item, then find Amazon.co.jp product-page candidates.\n"
        "For each item, first extract or infer the brand, product series, product type, model number, size, and other identifying details from the input title.\n"
        "Consider English names as well as Japanese product names, katakana transliterations, and official brand naming.\n"
        "Use manufacturer websites, official information, and trustworthy product references to identify the product before searching for its Amazon.co.jp page.\n"
        "Then find an Amazon.co.jp page for that product or a sufficiently close related product.\n"
        "Return only HTTPS Amazon.co.jp product-page URLs. Do not return overseas Amazon, other marketplaces, or general web URLs.\n"
        "Do not invent or guess URLs. If no Amazon.co.jp candidate URL is confirmed, return UNKNOWN.\n"
        "A related product in the same series, size, color, capacity, set, or variant is allowed.\n"
        "Return every provided source_id exactly once. Return at most three candidates per item.\n"
        "These are search candidates only; do not claim that a product or ASIN is verified.\n\n"
        "Input items:\n"
        f"{json.dumps(input_items, ensure_ascii=False)}"
    )


def validate_amazon_jp_url(amazon_url: str) -> tuple[str, str]:
    """Return a normalized ASIN and validation status for an Amazon.co.jp URL."""

    value = (amazon_url or "").strip()
    if not value:
        return "", "INVALID_URL_EMPTY"

    parsed = urlparse(value)
    if parsed.scheme.lower() != "https":
        return "", "INVALID_URL_SCHEME"
    if (parsed.hostname or "").lower() not in _AMAZON_JP_HOSTS:
        return "", "INVALID_URL_HOST"
    match = _AMAZON_ASIN_PATH_PATTERN.search(parsed.path)
    if match is None:
        return "", "INVALID_URL_PATH"
    return match.group(1).upper(), VALIDATION_STATUS_VALID


def execute_openai_web_search(
    inputs: Iterable[OpenAISearchInput],
    api_key: str,
    *,
    client_factory: Callable[..., Any] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> OpenAISearchRun:
    """Make exactly one explicit Responses API request for the supplied test inputs."""

    materialized = list(inputs)
    _validate_inputs(materialized)
    if not (api_key or "").strip():
        raise OpenAISearchError(
            "OPENAI_API_KEY_MISSING",
            "OpenAI APIキーが未設定です。プロジェクト直下の .env の OPENAI_API_KEY を確認してください。",
        )

    client = _create_client(api_key, client_factory)
    started_at = clock()
    try:
        response = client.responses.create(
            model=OPENAI_SEARCH_MODEL,
            input=build_openai_search_prompt(materialized),
            tools=[
                {
                    "type": "web_search",
                    "user_location": {"type": "approximate", "country": "JP"},
                    "search_context_size": "medium",
                }
            ],
            tool_choice="auto",
            include=["web_search_call.action.sources"],
            text={"format": OPENAI_RESPONSE_SCHEMA},
            reasoning={"effort": "low"},
            store=False,
        )
    except Exception as exc:
        raise _translate_openai_exception(exc) from exc
    elapsed_ms = int((clock() - started_at) * 1000)

    payload = _response_payload(response)
    rows, diagnostics = _rows_from_payload(materialized, payload)
    usage, sources = _response_metadata(response, elapsed_ms)
    return OpenAISearchRun(
        rows=rows,
        usage=usage,
        sources=sources,
        diagnostics=diagnostics,
    )


def summarize_openai_results(rows: Iterable[dict[str, str]]) -> dict[str, int]:
    materialized = list(rows)
    return {
        "candidate_products": len(
            {
                row["source_id"]
                for row in materialized
                if row.get("validation_status") == VALIDATION_STATUS_VALID
            }
        ),
        "valid_url_candidates": sum(
            1
            for row in materialized
            if row.get("validation_status") == VALIDATION_STATUS_VALID
        ),
        "unknown_products": len(
            {
                row["source_id"]
                for row in materialized
                if row.get("model_status") == MODEL_STATUS_UNKNOWN
            }
        ),
        "error_products": len(
            {
                row["source_id"]
                for row in materialized
                if row.get("model_status") == MODEL_STATUS_ERROR
            }
        ),
    }


def summarize_openai_sources(sources: Iterable[dict[str, str]]) -> dict[str, int]:
    materialized = list(sources)
    return {
        "deduplicated_sources": len(materialized),
        "amazon_jp_sources": sum(
            1
            for source in materialized
            if str(source.get("domain") or "").lower()
            in _AMAZON_JP_HOSTS
        ),
    }


def _create_client(api_key: str, client_factory: Callable[..., Any] | None) -> Any:
    if client_factory is not None:
        return client_factory(
            api_key=api_key,
            timeout=OPENAI_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OpenAISearchError(
            "OPENAI_SDK_NOT_INSTALLED",
            "OpenAI SDKが未導入です。requirements.txtの依存関係をインストールしてください。",
        ) from exc
    return OpenAI(
        api_key=api_key,
        timeout=OPENAI_REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )


def _validate_inputs(inputs: list[OpenAISearchInput]) -> None:
    if not inputs:
        raise OpenAISearchError("INPUT_EMPTY", "商品名を1件以上入力してください。")
    if len(inputs) > MAX_OPENAI_TEST_ITEMS:
        raise OpenAISearchError(
            "INPUT_LIMIT_EXCEEDED",
            f"OpenAI検索テストは1回につき最大{MAX_OPENAI_TEST_ITEMS}件です。",
        )
    source_ids = [item.source_id for item in inputs]
    if any(not _TEST_SOURCE_ID_PATTERN.fullmatch(source_id) for source_id in source_ids):
        raise OpenAISearchError("INVALID_SOURCE_ID", "検証用source_idの形式が不正です。")
    if len(set(source_ids)) != len(source_ids):
        raise OpenAISearchError("DUPLICATE_SOURCE_ID", "検証用source_idが重複しています。")


def _response_payload(response: Any) -> dict[str, Any]:
    output_text = _value(response, "output_text", "")
    if not isinstance(output_text, str) or not output_text.strip():
        raise OpenAISearchError(
            "EMPTY_RESPONSE",
            "OpenAIから構造化された応答を取得できませんでした。",
        )
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise OpenAISearchError(
            "STRUCTURED_OUTPUT_INVALID",
            "OpenAIの構造化出力を解析できませんでした。",
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise OpenAISearchError(
            "STRUCTURED_OUTPUT_INVALID",
            "OpenAIの構造化出力にresultsがありません。",
        )
    return payload


def _rows_from_payload(
    inputs: list[OpenAISearchInput],
    payload: dict[str, Any],
) -> tuple[list[dict[str, str]], list[str]]:
    expected = {item.source_id: item for item in inputs}
    response_rows: dict[str, dict[str, Any]] = {}
    duplicate_source_ids: set[str] = set()
    diagnostics: list[str] = []

    for item in payload["results"]:
        if not isinstance(item, dict):
            diagnostics.append("OpenAI response included a non-object result.")
            continue
        source_id = str(item.get("source_id") or "").strip().upper()
        if not source_id:
            diagnostics.append("OpenAI response included a result without source_id.")
            continue
        if source_id not in expected:
            diagnostics.append(f"Unexpected source_id in OpenAI response: {source_id}")
            continue
        if source_id in response_rows:
            duplicate_source_ids.add(source_id)
            continue
        response_rows[source_id] = item

    normalized_rows: list[dict[str, str]] = []
    for input_item in inputs:
        if input_item.source_id in duplicate_source_ids:
            normalized_rows.append(
                _result_row(
                    input_item,
                    MODEL_STATUS_ERROR,
                    VALIDATION_STATUS_NOT_APPLICABLE,
                    "",
                    "",
                    "Duplicate source_id in OpenAI response",
                    "",
                )
            )
            continue
        raw_result = response_rows.get(input_item.source_id)
        if raw_result is None:
            normalized_rows.append(
                _result_row(
                    input_item,
                    MODEL_STATUS_ERROR,
                    VALIDATION_STATUS_NOT_APPLICABLE,
                    "",
                    "",
                    "OpenAI response missing source_id",
                    "",
                )
            )
            continue
        normalized_rows.extend(_normalize_result(input_item, raw_result))
    return normalized_rows, diagnostics


def _normalize_result(
    input_item: OpenAISearchInput,
    raw_result: dict[str, Any],
) -> list[dict[str, str]]:
    status = str(raw_result.get("status") or "").strip().upper()
    searched_title = raw_result.get("searched_title")
    note = raw_result.get("note")
    candidates = raw_result.get("candidates")
    if (
        status not in MODEL_STATUSES
        or not isinstance(searched_title, str)
        or not isinstance(note, str)
        or not isinstance(candidates, list)
    ):
        return [
            _result_row(
                input_item,
                MODEL_STATUS_ERROR,
                VALIDATION_STATUS_NOT_APPLICABLE,
                "",
                "",
                "OpenAI response did not match the expected schema",
                "",
            )
        ]

    if status != MODEL_STATUS_CANDIDATES:
        return [
            _result_row(
                input_item,
                status,
                VALIDATION_STATUS_NOT_APPLICABLE,
                "",
                "",
                note,
                searched_title,
            )
        ]

    valid_candidates, invalid_count = _validated_candidates(candidates)
    if not valid_candidates:
        invalid_note = "All OpenAI candidate URLs failed format validation"
        if invalid_count == 0:
            invalid_note = "OpenAI returned CANDIDATES without candidate URLs"
        return [
            _result_row(
                input_item,
                MODEL_STATUS_CANDIDATES,
                VALIDATION_STATUS_INVALID,
                "",
                "",
                _join_notes(note, invalid_note),
                searched_title,
            )
        ]

    return [
        _result_row(
            input_item,
            MODEL_STATUS_CANDIDATES,
            VALIDATION_STATUS_VALID,
            candidate["amazon_url"],
            candidate["asin"],
            _join_notes(note, candidate["note"]),
            searched_title,
        )
        for candidate in valid_candidates
    ]


def _validated_candidates(candidates: list[Any]) -> tuple[list[dict[str, str]], int]:
    valid_candidates: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    seen_asins: set[str] = set()
    invalid_count = 0
    for candidate in candidates:
        if not isinstance(candidate, dict):
            invalid_count += 1
            continue
        amazon_url = candidate.get("amazon_url")
        note = candidate.get("note")
        if not isinstance(amazon_url, str) or not isinstance(note, str):
            invalid_count += 1
            continue
        asin, validation_status = validate_amazon_jp_url(amazon_url)
        if validation_status != VALIDATION_STATUS_VALID:
            invalid_count += 1
            continue
        normalized_url = amazon_url.strip().lower()
        if normalized_url in seen_urls or asin in seen_asins:
            continue
        seen_urls.add(normalized_url)
        seen_asins.add(asin)
        valid_candidates.append(
            {
                "amazon_url": amazon_url.strip(),
                "asin": asin,
                "note": note.strip(),
            }
        )
        if len(valid_candidates) == MAX_CANDIDATES_PER_ITEM:
            break
    return valid_candidates, invalid_count


def _result_row(
    input_item: OpenAISearchInput,
    model_status: str,
    validation_status: str,
    amazon_url: str,
    asin: str,
    note: str,
    searched_title: str,
) -> dict[str, str]:
    return {
        "source_id": input_item.source_id,
        "input_title": input_item.input_title,
        "search_title": input_item.search_title,
        "searched_title": searched_title,
        "model_status": model_status,
        "validation_status": validation_status,
        "candidate_state": "OPENAI_CANDIDATE" if amazon_url else "",
        "amazon_url": amazon_url,
        "asin": asin,
        "keepa_status": KEEPA_NOT_CHECKED,
        "existence_status": EXISTENCE_NOT_VERIFIED,
        "note": note,
    }


def _response_metadata(
    response: Any,
    elapsed_ms: int,
) -> tuple[dict[str, int | str | None], list[dict[str, str]]]:
    usage = _value(response, "usage", {})
    output_items = _value(response, "output", [])
    if not isinstance(output_items, list):
        output_items = []

    web_search_calls = 0
    source_count = 0
    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for output_item in output_items:
        if _value(output_item, "type", "") != "web_search_call":
            continue
        web_search_calls += 1
        action_sources = _value(_value(output_item, "action", {}), "sources", [])
        if not isinstance(action_sources, list):
            continue
        source_count += len(action_sources)
        for source in action_sources:
            source_detail = _source_detail(source)
            url = source_detail["url"]
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            sources.append(source_detail)

    return (
        {
            "model": _value(response, "model", OPENAI_SEARCH_MODEL),
            "api_request_count": 1,
            "input_tokens": _value(usage, "input_tokens", None),
            "output_tokens": _value(usage, "output_tokens", None),
            "total_tokens": _value(usage, "total_tokens", None),
            "web_search_call_count": web_search_calls,
            "source_count": source_count,
            "elapsed_ms": elapsed_ms,
            "request_id": _value(response, "_request_id", None),
        },
        sources,
    )


def _source_detail(source: Any) -> dict[str, str]:
    url = _string_value(_value(source, "url", ""))
    title = _string_value(_value(source, "title", ""))
    source_type = _string_value(
        _value(source, "type", _value(source, "source_type", ""))
    )
    try:
        domain = (urlparse(url).hostname or "").lower()
    except ValueError:
        domain = ""
    return {
        "url": url,
        "title": title,
        "domain": domain,
        "source_type": source_type,
    }


def _translate_openai_exception(exc: Exception) -> OpenAISearchError:
    exception_name = type(exc).__name__
    message = str(exc).lower()
    if exception_name in {"AuthenticationError", "PermissionDeniedError"}:
        return OpenAISearchError("AUTHENTICATION_ERROR", "OpenAI APIの認証に失敗しました。")
    if exception_name == "RateLimitError":
        return OpenAISearchError("RATE_LIMIT", "OpenAI APIのレート制限に達しました。")
    if exception_name == "APITimeoutError":
        return OpenAISearchError("TIMEOUT", "OpenAI APIの応答がタイムアウトしました。")
    if exception_name == "APIConnectionError":
        return OpenAISearchError("CONNECTION_ERROR", "OpenAI APIへ接続できませんでした。")
    if exception_name in {"InternalServerError", "APIStatusError"}:
        return OpenAISearchError("SERVER_ERROR", "OpenAI API側でエラーが発生しました。")
    if "web search" in message:
        return OpenAISearchError("WEB_SEARCH_UNAVAILABLE", "OpenAI Web searchを利用できませんでした。")
    if "model" in message:
        return OpenAISearchError("MODEL_UNSUPPORTED", "指定したOpenAIモデルを利用できませんでした。")
    if exception_name in {"BadRequestError", "NotFoundError"}:
        return OpenAISearchError("REQUEST_ERROR", "OpenAI APIリクエストが受け付けられませんでした。")
    return OpenAISearchError("UNEXPECTED_ERROR", "OpenAI検索テスト中に想定外のエラーが発生しました。")


def _value(source: Any, name: str, default: Any) -> Any:
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _join_notes(*notes: str) -> str:
    return " / ".join(note.strip() for note in notes if note and note.strip())
