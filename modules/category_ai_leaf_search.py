"""Opt-in leaf-first candidate search; no human adoption or Safety decisions."""
from dataclasses import dataclass, replace, fields
import json
from hashlib import sha256
from time import perf_counter
import requests

from modules.category_ai_core import (
    CategoryAIError, CategoryAIEngine, FakeCategoryAIProvider, StepRequest, StepResult,
    TokenUsage, make_fake_abstain, parse_step_result, content_hash,
)
from modules.category_ai_prompts import PROMPT_VERSION, response_schema
from modules.category_ai_openai import RESPONSES_URL, _extract_output_text, _parse_usage

VERSION = "CATEGORY_LEAF_SEARCH_V2"
SYSTEM = """Classify the actual product using only supplied Shopee candidates.
Use product title first, then Keepa category and brand. Distinguish the main device
from its dedicated case, accessory, replacement part or refill. Do not classify a
case as the device itself. Category classification is not a Safety/legal decision.
Never invent IDs. A dedicated category must match the actual product, not merely
share a keyword. ABSTAIN rather than force an unrelated choice.
Set product_understood=false when the product's identity/purpose is unclear.
Tasks are indicated by category_context.current_category_path:
ROOT: select the best applicable root for the understood product.
ALTERNATIVE_ROOT: select another genuinely applicable root; ABSTAIN if none.
SPECIFIC_LEAVES: compare EVERY supplied full leaf path, excluding Others. SELECT
only a dedicated fitting leaf, otherwise ABSTAIN. Every batch is evaluated.
FINAL_SPECIFIC: choose the best of the dedicated matches from all searched roots.
OTHERS: dedicated leaves and applicable alternative roots have been exhausted.
Only for an understood product, SELECT an Others leaf whose FULL parent path
fits its purpose/accessory type. A valid parent with no dedicated category is
a legitimate reason to choose Others. Do not choose an unrelated Others parent.
ABSTAIN if product unclear or none of the supplied parents fits.
Return the required structured answer, including a brief classification reason.
"""
PROMPT_HASH = sha256(SYSTEM.encode()).hexdigest()


@dataclass(frozen=True)
class LeafResult(StepResult):
    product_understood: bool = True


class LeafSearchProvider:
    name = "openai_responses"

    def __init__(self, api_key, *, session=None):
        if not api_key or not api_key.strip():
            raise CategoryAIError("OPENAI_API_KEY_UNAVAILABLE")
        self.key, self.session = api_key.strip(), session or requests.Session()

    def select(self, request, profile):
        schema = response_schema()
        schema["properties"]["prompt_version"]["const"] = VERSION
        schema["properties"]["product_understood"] = {"type": "boolean"}
        schema["required"].append("product_understood")
        user_input = request.user_input()
        user_input["prompt_version"] = VERSION
        payload = {"model": profile.model, "input": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(user_input, ensure_ascii=False)}],
            "reasoning": {"effort": profile.reasoning_effort},
            "text": {"verbosity": profile.text_verbosity, "format": {
                "type": "json_schema", "name": VERSION.lower(), "strict": True, "schema": schema}},
            "max_output_tokens": profile.max_output_tokens, "service_tier": profile.service_tier,
            "store": False, "stream": False, "truncation": "disabled", "tool_choice": "none",
            "parallel_tool_calls": False}
        try:
            response = self.session.post(RESPONSES_URL, headers={"Authorization": f"Bearer {self.key}"},
                                         json=payload, timeout=profile.timeout_seconds, allow_redirects=False)
        except requests.Timeout as exc:
            raise CategoryAIError("TIMEOUT", api_call_count=1) from exc
        except requests.RequestException as exc:
            raise CategoryAIError("NETWORK_ERROR", api_call_count=1) from exc
        if response.status_code != 200:
            raise CategoryAIError("RATE_LIMIT" if response.status_code == 429 else f"HTTP_{response.status_code}", api_call_count=1)
        try:
            body = response.json()
            if body.get("status") != "completed":
                raise CategoryAIError("INCOMPLETE_RESPONSE", api_call_count=1)
            if body.get("model") != profile.model:
                raise CategoryAIError("RESPONSE_MODEL_MISMATCH", api_call_count=1)
            from modules.category_ai_core import _reject_duplicate_keys
            data = json.loads(_extract_output_text(body), object_pairs_hook=_reject_duplicate_keys)
            understood = data.pop("product_understood")
            if type(understood) is not bool or data["prompt_version"] != VERSION:
                raise ValueError("Invalid leaf contract")
            # Reuse the strict field/ID parser, while identifying the real V2 prompt in Prediction.
            data["prompt_version"] = PROMPT_VERSION
            parsed = parse_step_result(data, allowed_category_ids={n.category_id for n in request.candidates},
                usage=_parse_usage(body.get("usage")), served_service_tier=str(body.get("service_tier") or ""))
            return LeafResult(**{f.name: getattr(parsed, f.name) for f in fields(StepResult)}, product_understood=understood)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise CategoryAIError("SCHEMA_VIOLATION", api_call_count=1) from exc


def is_others(node):
    return node.category_name.strip().casefold() in {"others", "other"}


class LeafSearchEngine:
    """Every dedicated leaf in each selected root is checked before Others.

    A bounded related-root search that reaches its limit abstains; it cannot
    claim exhaustion. Results remain suggestions requiring human confirmation.
    """
    def __init__(self, provider, *, batch_size=80, max_roots=3):
        if type(batch_size) is not int or not 1 <= batch_size <= 80 or type(max_roots) is not int or not 1 <= max_roots <= 31:
            raise ValueError("Invalid search limits")
        self.provider, self.batch_size, self.max_roots = provider, batch_size, max_roots
        self.last_trace = []

    def predict(self, product, catalog, profile):
        started = perf_counter()
        if product.marketplace != catalog.marketplace:
            raise ValueError("Marketplace mismatch")
        self.last_trace = []
        usage, calls = TokenUsage(), 0
        chosen = None
        status, error, reason, confidence = "ABSTAIN", "", "No fitting category", None
        matches, fallback, visited = [], [], []

        def ask(stage, candidates):
            nonlocal usage, calls, reason, confidence
            result = self.provider.select(StepRequest(product, None, stage, tuple(candidates)), profile)
            calls += result.api_call_count
            usage = usage.plus(result.usage)
            if type(getattr(result, "product_understood", None)) is not bool:
                raise CategoryAIError("LEAF_UNDERSTANDING_MISSING")
            if result.decision not in {"SELECT", "ABSTAIN"} or (result.decision == "SELECT" and result.selected_category_id not in {n.category_id for n in candidates}):
                raise CategoryAIError("CANDIDATE_OUTSIDE_ALLOWLIST")
            self.last_trace.append({"stage": stage, "candidate_ids": [n.category_id for n in candidates],
                "decision": result.decision, "selected_id": result.selected_category_id,
                "product_understood": result.product_understood, "brief_explanation": result.short_reason[:600]})
            reason, confidence = result.short_reason, result.confidence
            return result

        def leaves(root):
            return [n for n in catalog.nodes if n.is_leaf and (n.category_id == root.category_id or n.category_path.startswith(root.category_path + " > "))]

        try:
            roots = list(catalog.children_of(None))
            result = ask("ROOT", roots)
            exhausted = False
            while result.decision == "SELECT" and result.product_understood:
                root = catalog.get(result.selected_category_id)
                visited.append(root.category_id)
                nodes = leaves(root)
                fallback.extend(n for n in nodes if is_others(n))
                specific = [n for n in nodes if not is_others(n)]
                for offset in range(0, len(specific), self.batch_size):
                    answer = ask("SPECIFIC_LEAVES:" + root.category_path, specific[offset:offset+self.batch_size])
                    if not answer.product_understood:
                        break
                    if answer.decision == "SELECT":
                        matches.append(catalog.get(answer.selected_category_id))
                else:
                    if matches:
                        final = ask("FINAL_SPECIFIC", matches)
                        if final.product_understood and final.decision == "SELECT":
                            chosen, status = catalog.get(final.selected_category_id), "COMPLETED"
                        break
                    remaining = [n for n in roots if n.category_id not in visited]
                    if not remaining:
                        exhausted = True
                        break
                    if len(visited) >= self.max_roots:
                        reason = "Related root search limit reached; exhaustion not established"
                        break
                    result = ask("ALTERNATIVE_ROOT", remaining)
                    if result.product_understood and result.decision == "ABSTAIN":
                        exhausted = True
                    continue
                break  # Unclear product prevents fallback.
            if chosen is None and exhausted and fallback:
                final = ask("OTHERS", fallback)
                if final.product_understood and final.decision == "SELECT":
                    chosen, status = catalog.get(final.selected_category_id), "COMPLETED"
        except CategoryAIError as exc:
            error, status = exc.code, "FAILED"
            calls += exc.api_call_count
            reason = error
        base = CategoryAIEngine(FakeCategoryAIProvider([make_fake_abstain()])).predict(product, catalog, profile)
        contract = {**profile.to_dict(), "prompt_version": VERSION, "prompt_sha256": PROMPT_HASH,
                    "traversal_version": VERSION, "batch_size": self.batch_size, "max_roots": self.max_roots}
        return replace(base, provider=self.provider.name, prompt_version=VERSION, traversal_version=VERSION,
            benchmark_request_profile=contract, benchmark_request_profile_hash=content_hash(contract),
            comparison_contract_hash=content_hash({k:v for k,v in contract.items() if k != "model"}),
            status=status, abstain=status != "COMPLETED", predicted_category_id=chosen.category_id if chosen else None,
            predicted_category_path=chosen.category_path if chosen else "", prediction_confidence=confidence,
            short_reason=reason, error_code=error, api_call_count=calls, input_tokens=usage.input_tokens,
            cached_tokens=usage.cached_tokens, cache_write_tokens=usage.cache_write_tokens,
            output_tokens=usage.output_tokens, traversal_steps=(), latency_seconds=perf_counter()-started).with_hash()
