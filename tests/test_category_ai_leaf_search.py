"""Leaf-first search invariants, without external APIs."""
import json
from dataclasses import replace

import pytest

from modules.category_ai_core import CategoryCatalog, CategoryNode, ProductEvidence, TokenUsage, CategoryAIError
from modules.category_mapper_ai import load_luna_request_profile
from modules.category_ai_leaf_search import LeafSearchEngine, LeafResult, LeafSearchProvider, VERSION
from test_category_ai_openai import Session, Response, response_body


def result(selected=None, *, understood=True):
    return LeafResult("synthetic product", "SELECT" if selected is not None else "ABSTAIN", selected, .8,
                      "synthetic classification", product_understood=understood)


class Provider:
    name = "fake_leaf"
    def __init__(self, *outcomes):
        self.outcomes, self.requests = list(outcomes), []
    def select(self, request, profile):
        self.requests.append(request)
        value = self.outcomes.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def catalog():
    return CategoryCatalog("SG", "synthetic", (
        CategoryNode(10, None, "Audio", "Audio", False),
        CategoryNode(11, 10, "Mixers", "Audio > Mixers", True),
        CategoryNode(12, 10, "Microphones", "Audio > Microphones", True),
        CategoryNode(13, 10, "Others", "Audio > Others", True),
        CategoryNode(20, None, "Computers", "Computers", False),
        CategoryNode(21, 20, "Cases", "Computers > Cases", True),
        CategoryNode(22, 20, "Others", "Computers > Others", True),
    ))


def run(provider, **limits):
    engine = LeafSearchEngine(provider, **limits)
    prediction = engine.predict(ProductEvidence("SG", "case", "Synthetic item"), catalog(), load_luna_request_profile())
    return engine, prediction


def test_all_dedicated_batches_checked_before_others():
    p = Provider(result(10), result(), result(), result(), result(13))
    engine, prediction = run(p, batch_size=1)
    assert prediction.status == "COMPLETED" and prediction.predicted_category_id == 13
    assert [[n.category_id for n in r.candidates] for r in p.requests] == [[10,20],[11],[12],[20],[13]]
    assert [x["stage"] for x in engine.last_trace][-2:] == ["ALTERNATIVE_ROOT", "OTHERS"]
    assert prediction.prompt_version == VERSION and prediction.benchmark_request_profile["prompt_version"] == VERSION


def test_related_root_dedicated_match_wins_before_others():
    p = Provider(result(10), result(), result(20), result(21), result(21))
    engine, prediction = run(p)
    assert prediction.predicted_category_id == 21
    assert all(r.current_category_path != "OTHERS" for r in p.requests)
    assert prediction.predicted_category_path == "Computers > Cases"


def test_later_batch_can_beat_earlier_match():
    p = Provider(result(10), result(11), result(12), result(12))
    _, prediction = run(p, batch_size=1)
    assert prediction.predicted_category_id == 12
    assert [n.category_id for n in p.requests[-1].candidates] == [11,12]


@pytest.mark.parametrize("outcomes", [
    [result(10, understood=False)],
    [result(10), result(understood=False)],
    [result(10), result(), result(understood=False)],
])
def test_unclear_product_never_uses_others(outcomes):
    p = Provider(*outcomes)
    _, prediction = run(p)
    assert prediction.status == "ABSTAIN" and prediction.predicted_category_id is None
    assert all(r.current_category_path != "OTHERS" for r in p.requests)


def test_exhaustion_not_claimed_when_related_root_limit_hit():
    p = Provider(result(10), result())
    _, prediction = run(p, max_roots=1)
    assert prediction.status == "ABSTAIN" and "limit" in prediction.short_reason
    assert len(p.requests) == 2


def test_transport_failure_never_falls_back_to_others():
    p = Provider(result(10), CategoryAIError("TIMEOUT", api_call_count=1))
    _, prediction = run(p)
    assert prediction.status == "FAILED" and prediction.error_code == "TIMEOUT"
    assert prediction.api_call_count == 2 and len(p.requests) == 2


def test_unlisted_id_fails_closed():
    p = Provider(result(999))
    _, prediction = run(p)
    assert prediction.status == "FAILED" and prediction.predicted_category_id is None


def test_provider_uses_v2_schema_and_parses_usage_without_losing_type():
    data = {"prompt_version": VERSION, "product_type_summary":"synthetic", "decision":"SELECT",
            "selected_category_id":10, "confidence":.8, "short_reason":"synthetic", "product_understood":True}
    session = Session(Response(body=response_body(output_text=json.dumps(data), model="gpt-5.6-luna")))
    p = LeafSearchProvider("synthetic-key", session=session)
    from modules.category_ai_core import StepRequest
    answer = p.select(StepRequest(ProductEvidence("SG","case","Synthetic item"),None,"ROOT",catalog().children_of(None)),load_luna_request_profile())
    assert isinstance(answer.usage, TokenUsage) and answer.usage.input_tokens == 120
    schema = session.calls[0][1]["json"]["text"]["format"]["schema"]
    assert schema["properties"]["prompt_version"]["const"] == VERSION
    assert "product_understood" in schema["required"]


def test_versioned_v2_replay_connects_to_sg_suggestions_without_auto_confirm(tmp_path):
    from pathlib import Path
    from modules.sg_candidate_runtime import SGReplayBundle
    from modules.category_mapper_store import CategoryMapperStore
    from modules.category_mapper_sg import SGMapperRecommendation, generate_sg_ai_category_suggestions
    from scripts.sg_category_diagnostic import prepare
    base = Path(__file__).parent / "fixtures/browser_e2e/sg_candidate"
    source, tree = prepare(base / "prelisting_gate_eligible_sg_expansion.csv", base / "catalog.csv")
    engine = SGReplayBundle((base / "replay_leaf_v2.json").read_bytes()).category_engine()
    assert isinstance(engine, LeafSearchEngine)
    row = source.rows[0]
    item = SGMapperRecommendation("SG", "EXPANSION", row.source_asin, row.candidate_asin,
        row.product_title, row.keepa_brand, row.keepa_category, "", "GATE_ELIGIBLE")
    store = CategoryMapperStore(tmp_path / "isolated.sqlite3")
    store.replace_sg_category_catalog(tree)
    batch = generate_sg_ai_category_suggestions((item,), store=store, engine=engine, catalog=tree,
                                              profile=load_luna_request_profile())
    assert batch.suggestions[0].is_adoptable and batch.suggestions[0].predicted_category_id == 100869
    assert batch.suggestions[0].prediction.api_call_count == 0
    assert not item.category_is_confirmed and not item.listing_ready
