"""OpenAI Responses API transport for the Category AI benchmark.

This module never persists or logs credentials or raw API responses.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from dotenv import load_dotenv
import requests

from modules.category_ai_core import (
    BenchmarkRequestProfile,
    CategoryAIError,
    StepRequest,
    StepResult,
    TokenUsage,
    parse_step_result,
)
from modules.category_ai_prompts import RESPONSE_SCHEMA_VERSION, SYSTEM_PROMPT, response_schema


RESPONSES_URL = "https://api.openai.com/v1/responses"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OpenAIResponsesCategoryProvider:
    name = "openai_responses"

    def __init__(self, api_key: str, *, session: Any | None = None) -> None:
        key = api_key.strip()
        if not key or "\n" in key or "\r" in key:
            raise CategoryAIError("OPENAI_API_KEY_UNAVAILABLE")
        self._api_key = key
        self._session = session or requests.Session()

    @classmethod
    def from_environment(cls) -> "OpenAIResponsesCategoryProvider":
        load_dotenv(PROJECT_ROOT / ".env")
        return cls(os.getenv("OPENAI_API_KEY", ""))

    def select(self, request: StepRequest, profile: BenchmarkRequestProfile) -> StepResult:
        if profile.provider != self.name:
            raise CategoryAIError("REQUEST_PROFILE_PROVIDER_MISMATCH")
        user_input = request.user_input()
        payload = {
            "model": profile.model,
            "input": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(user_input, ensure_ascii=False, separators=(",", ":")),
                },
            ],
            "reasoning": {"effort": profile.reasoning_effort},
            "text": {
                "verbosity": profile.text_verbosity,
                "format": {
                    "type": "json_schema",
                    "name": RESPONSE_SCHEMA_VERSION.lower(),
                    "strict": True,
                    "schema": response_schema(),
                },
            },
            "max_output_tokens": profile.max_output_tokens,
            "service_tier": profile.service_tier,
            "store": profile.store,
            "stream": profile.stream,
            "truncation": profile.truncation,
            "tool_choice": profile.tool_choice,
            "parallel_tool_calls": profile.parallel_tool_calls,
        }
        started = perf_counter()
        try:
            response = self._session.post(
                RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=profile.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise CategoryAIError(
                "TIMEOUT", api_call_count=1, latency_seconds=perf_counter() - started
            ) from exc
        except requests.RequestException as exc:
            raise CategoryAIError(
                "NETWORK_ERROR", api_call_count=1, latency_seconds=perf_counter() - started
            ) from exc
        latency = perf_counter() - started
        status_code = getattr(response, "status_code", 0)
        if status_code == 429:
            raise CategoryAIError(
                "RATE_LIMIT", api_call_count=1, latency_seconds=latency
            )
        if status_code < 200 or status_code >= 300:
            raise CategoryAIError(
                f"HTTP_{status_code or 'ERROR'}",
                api_call_count=1,
                latency_seconds=latency,
            )
        try:
            body = response.json()
        except (TypeError, ValueError) as exc:
            raise CategoryAIError(
                "INVALID_JSON", api_call_count=1, latency_seconds=latency
            ) from exc
        if not isinstance(body, Mapping) or not body:
            raise CategoryAIError(
                "EMPTY_RESPONSE", api_call_count=1, latency_seconds=latency
            )
        if body.get("status") != "completed":
            raise CategoryAIError(
                "INCOMPLETE_RESPONSE", api_call_count=1, latency_seconds=latency
            )
        if body.get("model") != profile.model:
            raise CategoryAIError(
                "RESPONSE_MODEL_MISMATCH", api_call_count=1, latency_seconds=latency
            )
        output_text = _extract_output_text(body)
        usage = _parse_usage(body.get("usage"))
        served_service_tier = str(body.get("service_tier") or "")
        return parse_step_result(
            output_text,
            allowed_category_ids={candidate.category_id for candidate in request.candidates},
            usage=usage,
            api_call_count=1,
            latency_seconds=latency,
            served_service_tier=served_service_tier,
        )


def _extract_output_text(body: Mapping[str, Any]) -> str:
    direct = body.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    output = body.get("output")
    if not isinstance(output, list):
        raise CategoryAIError("EMPTY_RESPONSE", api_call_count=1)
    texts: list[str] = []
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, Mapping):
                continue
            if part.get("type") == "refusal":
                raise CategoryAIError("REFUSAL", api_call_count=1)
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    if len(texts) != 1 or not texts[0].strip():
        raise CategoryAIError("EMPTY_RESPONSE", api_call_count=1)
    return texts[0]


def _parse_usage(value: Any) -> TokenUsage:
    if value is None:
        return TokenUsage()
    if not isinstance(value, Mapping):
        raise CategoryAIError("USAGE_SCHEMA_VIOLATION", api_call_count=1)
    details = value.get("input_tokens_details") or {}
    if not isinstance(details, Mapping):
        raise CategoryAIError("USAGE_SCHEMA_VIOLATION", api_call_count=1)
    try:
        return TokenUsage(
            input_tokens=_strict_token(value.get("input_tokens", 0)),
            cached_tokens=_strict_token(details.get("cached_tokens", 0)),
            cache_write_tokens=_strict_token(details.get("cache_write_tokens", 0)),
            output_tokens=_strict_token(value.get("output_tokens", 0)),
        )
    except ValueError as exc:
        raise CategoryAIError("USAGE_SCHEMA_VIOLATION", api_call_count=1) from exc


def _strict_token(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("invalid token count")
    return value
