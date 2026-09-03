"""Synthetic-only DEC-0051/53/54 contract, selector, binding and gate tests."""
from collections import UserDict
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from modules.ph_image_safety import (
    ImageSafetyError,
    MODEL,
    TARGET_ROOTS,
    apply_image_safety,
    capture_keepa_image_fact,
    create_image_sidecar,
    image_fact_from_product,
    image_sidecar_bytes,
    image_result_status,
    normalize_root,
    parse_image_sidecar,
    prepare_image_safety,
    record_human_decision,
    run_image_safety,
    select_images,
)
from modules.prelisting_candidate_csv import (
    PrelistingCandidateRow,
    parse_prelisting_candidate_csv,
    rows_to_prelisting_candidate_csv,
)
from modules.prelisting_gate import evaluate_prelisting_gate
from modules.prelisting_gate_csv import (
    build_prelisting_gate_exports,
    PRELISTING_GATE_RESULT_COLUMNS,
)
from modules.listing_inventory_parser import ListingInventoryFileResult


def candidate(asin="B000000001", **kwargs):
    values = dict(
        schema_version="PRELISTING_CANDIDATE_V1",
        source_type="EXPANSION",
        source_id="",
        source_asin="B000000009",
        candidate_asin=asin,
        input_title="",
        product_title="ordinary storage box",
        brand="Synthetic brand",
        category="Synthetic category",
        amazon_url="",
        source_status="",
        source_verification="",
        source="keepa_product_finder_strict",
        fetched_at="",
        source_note="",
    )
    values.update(kwargs)
    return PrelistingCandidateRow(**values)


def fact(asin="B000000001", root=13299531, images=("one.jpg",), provider="keepa"):
    result = capture_keepa_image_fact(
        {"imagesCSV": ",".join(images)}, candidate_asin=asin, root_category_id=root
    )
    if provider == "canopy_test":
        return image_fact_from_product(None, candidate_asin=asin, provider=provider)
    return result


def setup_case(candidates=None, facts=None):
    candidates = tuple(candidates or (candidate(),))
    content = rows_to_prelisting_candidate_csv(candidates)
    parsed = parse_prelisting_candidate_csv(content, filename="candidate.csv")
    if facts is None:
        facts = [fact(c.candidate_asin) for c in candidates]
    sources = [
        {"candidate_asin": f["candidate_asin"], "ph_image_safety_fact": f}
        for f in facts
    ]
    encoded = create_image_sidecar(content, parsed.rows, sources)
    sidecar = parse_image_sidecar(encoded, candidate_content=content, candidates=parsed)
    inventory = ListingInventoryFileResult(
        marketplace="PH",
        shop_label="shop",
        source_file="inventory_PH.csv",
        header_row_number=5,
        data_row_count=0,
        unique_asin_count=0,
        evidence_records=(),
    )
    base = evaluate_prelisting_gate(
        parsed, [inventory], marketplace="PH", expected_shop_count=1
    )
    return content, parsed, base, sidecar


class FakeAnalyzer:
    def __init__(self, status="NO_SIGNAL", *, partial=False, failure=False):
        self.calls = []
        self.preflights = 0
        self.status, self.partial, self.failure = status, partial, failure

    def preflight(self):
        self.preflights += 1

    def analyze(self, urls, *, capture_error):
        self.calls.append(urls)
        if self.failure:
            raise ImageSafetyError("synthetic global outage")
        return {
            "system_status": "PARTIAL" if self.partial else "COMPLETED",
            "ai_status": self.status,
            "note": "synthetic inspection",
            "attempts": 1,
            "images": [
                {"url": u, "status": "LOADED", "sha256": "a" * 64, "mime": "image/jpeg"}
                if not self.partial or index == 0
                else {"url": u, "status": "ERROR", "sha256": "", "mime": ""}
                for index, u in enumerate(urls)
            ],
        }


@pytest.mark.parametrize("root", sorted(TARGET_ROOTS))
def test_four_roots_are_targets(root):
    assert select_images(fact(root=root), "SAFE") == "TARGET_ROOT"


@pytest.mark.parametrize(
    "root", [None, "", "invalid", 0, -1, True, 1.2, {}, [], "1.2", "nan", "1e4"]
)
def test_invalid_root_is_unknown_and_selected(root):
    assert normalize_root(root) is None
    assert select_images(fact(root=root), "SAFE") == "ROOT_UNKNOWN"


@pytest.mark.parametrize("root", [3828871, 52374051, 999, "999"])
def test_other_known_root_is_not_selected(root):
    assert select_images(fact(root=root), "SAFE") == "OTHER_ROOT"


@pytest.mark.parametrize("root", [None, 13299531, 999])
def test_existing_block_always_wins(root):
    assert select_images(fact(root=root), "BLOCK") == "EXISTING_BLOCK"


def test_image_capture_uses_three_unique_source_order_references_only():
    result = capture_keepa_image_fact(
        {
            "imagesCSV": "one.jpg,two.png,one.jpg,three.webp,four.jpg",
            "image": "ignored",
        },
        candidate_asin="B000000001",
        root_category_id="13299531",
    )
    assert [u.rsplit("/", 1)[1] for u in result["image_urls"]] == [
        "one.jpg",
        "two.png",
        "three.webp",
    ]
    assert result["root_category_id"] == 13299531
    assert not result["capture_error"]
    bad = capture_keepa_image_fact(
        {"imagesCSV": "one.jpg,../bad.jpg"},
        candidate_asin="B000000001",
        root_category_id=None,
    )
    assert bad["capture_error"]


@pytest.mark.parametrize("as_object", [False, True])
@pytest.mark.parametrize(
    "entry, expected",
    [
        ({"l": "large.jpg", "m": "medium.jpg"}, "large.jpg"),
        ({"m": "medium.jpg"}, "medium.jpg"),
        ({"l": "", "m": "medium.jpg"}, "medium.jpg"),
        ({"l": None, "m": "medium.jpg"}, "medium.jpg"),
        (UserDict({"l": "large.jpg"}), "large.jpg"),
    ],
)
def test_images_prefer_large_and_fall_back_only_for_empty_or_missing_large(
    as_object, entry, expected
):
    product = {"images": [entry], "imagesCSV": "legacy.jpg"}
    if as_object:
        product = SimpleNamespace(**product)
    result = capture_keepa_image_fact(
        product, candidate_asin="B000000001", root_category_id="13299531"
    )
    assert result["image_urls"] == ["https://m.media-amazon.com/images/I/" + expected]
    assert not result["capture_error"]
    assert result["root_category_id"] == 13299531


def test_images_preserve_order_deduplicate_and_cap_without_mixing_legacy():
    result = capture_keepa_image_fact(
        {
            "images": [
                {"l": "one.jpg"}, {"m": "two.png"}, {"l": "one.jpg"},
                {"l": "three.webp"}, {"l": "four.jpg"},
            ],
            "imagesCSV": "legacy.jpg",
        },
        candidate_asin="B000000001", root_category_id=None,
    )
    assert [u.rsplit("/", 1)[1] for u in result["image_urls"]] == [
        "one.jpg", "two.png", "three.webp"
    ]
    assert not result["capture_error"]


@pytest.mark.parametrize("images", [None, {}, "one.jpg", False, 1, ({"l": "one.jpg"},)])
def test_malformed_images_never_fall_back_to_legacy(images):
    result = capture_keepa_image_fact(
        {"images": images, "imagesCSV": "legacy.jpg"},
        candidate_asin="B000000001", root_category_id=None,
    )
    assert result["image_urls"] == []
    assert result["capture_error"]


def test_empty_images_list_is_unavailable_without_legacy_fallback():
    result = capture_keepa_image_fact(
        {"images": [], "imagesCSV": "legacy.jpg"},
        candidate_asin="B000000001", root_category_id=None,
    )
    assert result["image_urls"] == []
    assert not result["capture_error"]


@pytest.mark.parametrize("entry", [None, "one.jpg", [], 1, SimpleNamespace(l="one.jpg"), {}])
def test_malformed_image_entry_marks_error_and_keeps_only_valid_entries(entry):
    result = capture_keepa_image_fact(
        {"images": [{"l": "one.jpg"}, entry, {"m": "two.png"}]},
        candidate_asin="B000000001", root_category_id=None,
    )
    assert [u.rsplit("/", 1)[1] for u in result["image_urls"]] == ["one.jpg", "two.png"]
    assert result["capture_error"]


@pytest.mark.parametrize(
    "filename",
    [123, False, [], {}, " ", " one.jpg", "one.jpg\n", "../one.jpg",
     "https://example.com/one.jpg", "one%2Ejpg", "one.svg", "one.jpg?x=1"],
)
def test_invalid_large_filename_is_not_repaired_or_replaced_by_medium(filename):
    result = capture_keepa_image_fact(
        {"images": [{"l": filename, "m": "medium.jpg"}], "imagesCSV": "legacy.jpg"},
        candidate_asin="B000000001", root_category_id=None,
    )
    assert result["image_urls"] == []
    assert result["capture_error"]


@pytest.mark.parametrize("filename", [None, "", False, "../bad.jpg"])
def test_missing_large_with_invalid_medium_marks_capture_error(filename):
    result = capture_keepa_image_fact(
        {"images": [{"m": filename}]},
        candidate_asin="B000000001", root_category_id=None,
    )
    assert result["image_urls"] == []
    assert result["capture_error"]


def test_malformed_entry_after_three_images_still_marks_capture_error():
    result = capture_keepa_image_fact(
        {"images": [{"l": "one.jpg"}, {"l": "two.jpg"}, {"l": "three.jpg"}, None]},
        candidate_asin="B000000001", root_category_id=None,
    )
    assert len(result["image_urls"]) == 3
    assert result["capture_error"]


@pytest.mark.parametrize("as_object", [False, True])
def test_absent_images_keeps_legacy_csv_order_and_limit(as_object):
    product = {"imagesCSV": " one.jpg,two.jpg,one.jpg,three.jpg,four.jpg"}
    if as_object:
        product = SimpleNamespace(**product)
    result = capture_keepa_image_fact(
        product, candidate_asin="B000000001", root_category_id=13299531
    )
    assert [u.rsplit("/", 1)[1] for u in result["image_urls"]] == [
        "one.jpg", "two.jpg", "three.jpg"
    ]
    assert not result["capture_error"]


@pytest.mark.parametrize(
    "root, expected",
    [(13299531, "TARGET_ROOT"), (2277721051, "TARGET_ROOT"),
     (14304371, "TARGET_ROOT"), (2016929051, "TARGET_ROOT"),
     (None, "ROOT_UNKNOWN"), ("bad", "ROOT_UNKNOWN"), (999, "OTHER_ROOT")],
)
def test_current_images_preserve_root_selector_and_existing_block(root, expected):
    result = capture_keepa_image_fact(
        {"images": [{"l": "one.jpg"}]},
        candidate_asin="B000000001", root_category_id=root,
    )
    assert result["root_category_id"] == normalize_root(root)
    assert select_images(result, "SAFE") == expected
    assert select_images(result, "REVIEW") == expected
    assert select_images(result, "BLOCK") == "EXISTING_BLOCK"


def test_old_keepa_cache_preserves_root_without_fetching_and_has_no_images():
    result = image_fact_from_product(
        {"root_category_id": 13299531}, candidate_asin="B000000001"
    )
    assert result["root_category_id"] == 13299531
    assert result["image_urls"] == []


def test_candidate_bytes_and_columns_are_unchanged_and_sidecar_roundtrips():
    content, parsed, base, sidecar = setup_case()
    assert len(content.decode("utf-8-sig").splitlines()[0].split(",")) == 15
    assert rows_to_prelisting_candidate_csv(parsed.rows) == content
    assert (
        parse_image_sidecar(
            image_sidecar_bytes(sidecar), candidate_content=content, candidates=parsed
        )
        == sidecar
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s.update(schema_version="wrong"),
        lambda s: s.update(candidate_sha256="0" * 64),
        lambda s: s["rows"].append(deepcopy(s["rows"][0])),
        lambda s: s["rows"][0]["fact"].update(candidate_asin="B000000002"),
        lambda s: s["rows"][0]["fact"].update(
            image_urls=["http://127.0.0.1/secret.jpg"]
        ),
        lambda s: s["rows"][0]["fact"].update(root_category_id=True),
        lambda s: s["rows"][0].update(human={"decision": "ALLOW_PREPARATION"}),
    ],
)
def test_invalid_sidecar_stops(mutation):
    content, parsed, _, sidecar = setup_case()
    mutation(sidecar)
    with pytest.raises(ImageSafetyError):
        parse_image_sidecar(
            image_sidecar_bytes(sidecar), candidate_content=content, candidates=parsed
        )


def test_duplicate_json_keys_and_candidate_bytes_mismatch_stop():
    content, parsed, _, sidecar = setup_case()
    with pytest.raises(ImageSafetyError):
        parse_image_sidecar(
            b'{"rows":[],"rows":[]}', candidate_content=content, candidates=parsed
        )
    with pytest.raises(ImageSafetyError):
        parse_image_sidecar(
            image_sidecar_bytes(sidecar),
            candidate_content=content + b"\n",
            candidates=parsed,
        )


def test_duplicate_candidate_asins_stop():
    with pytest.raises(ImageSafetyError):
        setup_case([candidate(), candidate()])


@pytest.mark.parametrize("status", ["NO_SIGNAL", "REVIEW", "INDETERMINATE"])
def test_ai_semantic_results_and_roundtrip_are_bound(status):
    content, parsed, base, sidecar = setup_case()
    analyzer = FakeAnalyzer(status)
    done = run_image_safety(base, sidecar, content, analyzer=analyzer)
    result = apply_image_safety(base, done, content)
    assert result.rows[0].guardrail_status == base.rows[0].guardrail_status == "SAFE"
    assert result.rows[0].final_eligibility == (
        "ELIGIBLE" if status == "NO_SIGNAL" else "REVIEW"
    )
    assert done["rows"][0]["evaluation"]["model"] == MODEL
    assert done["rows"][0]["evaluation"]["ai_status"] == status
    assert (
        parse_image_sidecar(
            image_sidecar_bytes(done), candidate_content=content, candidates=parsed
        )
        == done
    )
    assert len(analyzer.calls) == 1
    run_image_safety(base, done, content, analyzer=analyzer)
    assert (
        len(analyzer.calls) == 1
    )  # Re-render/reusing this bound evaluation is not a new request.
    assert sidecar["rows"][0]["evaluation"] is None


def test_partial_images_never_become_no_signal_gate_pass():
    content, _, base, sidecar = setup_case(facts=[fact(images=("one.jpg", "two.jpg"))])
    done = run_image_safety(base, sidecar, content, analyzer=FakeAnalyzer(partial=True))
    assert done["rows"][0]["evaluation"]["ai_status"] == "NO_SIGNAL"
    assert image_result_status(done["rows"][0]["evaluation"]) == "INDETERMINATE"
    assert apply_image_safety(base, done, content).review_count == 1


@pytest.mark.parametrize(
    "root,images,expected",
    [(13299531, (), "UNAVAILABLE"), (13299531, ("one.jpg",), "NOT_RUN")],
)
def test_target_unavailable_or_pending_is_review(root, images, expected):
    content, _, base, sidecar = setup_case(facts=[fact(root=root, images=images)])
    prepared = prepare_image_safety(base, sidecar, content)
    assert prepared["rows"][0]["evaluation"]["system_status"] == expected
    assert prepared["rows"][0]["evaluation"]["ai_status"] is None
    assert apply_image_safety(base, prepared, content).review_count == 1


def test_no_images_and_skips_never_call_analyzer():
    candidates = [
        candidate("B000000001"),
        candidate("B000000002"),
        candidate("B000000003", product_title="kitchen knife"),
        candidate(
            "B000000004", source="canopy_test", source_verification="CANOPY_VERIFIED"
        ),
    ]
    facts = [
        fact("B000000001", images=()),
        fact("B000000002", root=999),
        fact("B000000003"),
        fact("B000000004", provider="canopy_test"),
    ]
    content, _, base, sidecar = setup_case(candidates, facts)
    analyzer = FakeAnalyzer()
    done = run_image_safety(base, sidecar, content, analyzer=analyzer)
    assert analyzer.preflights == 0 and analyzer.calls == []
    assert [r["evaluation"]["selector"] for r in done["rows"]] == [
        "TARGET_ROOT",
        "OTHER_ROOT",
        "EXISTING_BLOCK",
        "PROVIDER_UNSUPPORTED",
    ]
    assert all(r["evaluation"]["ai_status"] is None for r in done["rows"])
    result = apply_image_safety(base, done, content)
    assert [r.final_eligibility for r in result.rows] == [
        "REVIEW",
        "ELIGIBLE",
        "EXCLUDE",
        "ELIGIBLE",
    ]


def test_global_failure_discards_partial_batch_and_never_mutates_input():
    content, _, base, sidecar = setup_case()
    before = deepcopy(sidecar)
    with pytest.raises(ImageSafetyError):
        run_image_safety(base, sidecar, content, analyzer=FakeAnalyzer(failure=True))
    assert sidecar == before


@pytest.mark.parametrize("base_kind", ["eligible", "review", "exclude"])
def test_human_allow_only_removes_image_review(base_kind):
    kwargs = (
        {"brand": ""}
        if base_kind == "review"
        else ({"source_asin": "B000000001"} if base_kind == "exclude" else {})
    )
    content, parsed, base, sidecar = setup_case(
        [candidate(**kwargs)], [fact(images=())]
    )
    done = record_human_decision(
        base,
        sidecar,
        content,
        asin="B000000001",
        decision="ALLOW_PREPARATION",
        reviewed_images=True,
        note="別経路の十分な画像を確認",
    )
    final = apply_image_safety(base, done, content)
    assert final.rows[0] == base.rows[0]
    assert (
        parse_image_sidecar(
            image_sidecar_bytes(done), candidate_content=content, candidates=parsed
        )
        == done
    )


def test_human_exclude_is_not_ai_block_and_exports_reason_without_new_columns():
    content, _, base, sidecar = setup_case()
    done = record_human_decision(
        base,
        sidecar,
        content,
        asin="B000000001",
        decision="EXCLUDE",
        reviewed_images=False,
        note="確認できないため除外",
    )
    final = apply_image_safety(base, done, content)
    assert final.rows[0].final_eligibility == "EXCLUDE"
    assert final.rows[0].guardrail_status == "SAFE"
    bundle = build_prelisting_gate_exports(final)
    assert bundle.audit_csv.decode("utf-8-sig").splitlines()[0].split(",") == list(
        PRELISTING_GATE_RESULT_COLUMNS
    )
    assert b"IMAGE_SAFETY_EXCLUDE" in bundle.audit_csv
    assert bundle.eligible_csv is None


@pytest.mark.parametrize(
    "decision,reviewed,note",
    [
        ("BLOCK", True, "x"),
        ("ALLOW_PREPARATION", False, "x"),
        ("ALLOW_PREPARATION", True, ""),
    ],
)
def test_invalid_human_decision_rejected(decision, reviewed, note):
    content, _, base, sidecar = setup_case()
    with pytest.raises(ImageSafetyError):
        record_human_decision(
            base,
            sidecar,
            content,
            asin="B000000001",
            decision=decision,
            reviewed_images=reviewed,
            note=note,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("ai_status", "BLOCK"),
        ("system_status", "SAFE"),
        ("selector", "OTHER_ROOT"),
        ("model", "gpt-5.6-luna"),
        ("attempts", 3),
        ("note", "changed"),
    ],
)
def test_invalid_or_modified_evaluation_stops(field, value):
    content, parsed, base, sidecar = setup_case()
    done = run_image_safety(base, sidecar, content, analyzer=FakeAnalyzer())
    done["rows"][0]["evaluation"][field] = value
    with pytest.raises(ImageSafetyError):
        parse_image_sidecar(
            image_sidecar_bytes(done), candidate_content=content, candidates=parsed
        )


def test_changed_images_or_human_binding_or_guardrail_invalidates_decision():
    content, parsed, base, sidecar = setup_case()
    done = record_human_decision(
        base,
        sidecar,
        content,
        asin="B000000001",
        decision="ALLOW_PREPARATION",
        reviewed_images=True,
        note="確認済み",
    )
    for field, value in [
        ("evaluation_id", "0" * 64),
        ("candidate_asin", "B000000002"),
        ("note", "modified"),
    ]:
        changed = deepcopy(done)
        changed["rows"][0]["human"][field] = value
        with pytest.raises(ImageSafetyError):
            parse_image_sidecar(
                image_sidecar_bytes(changed),
                candidate_content=content,
                candidates=parsed,
            )
    changed = deepcopy(done)
    changed["rows"][0]["fact"]["image_urls"] = [
        "https://m.media-amazon.com/images/I/other.jpg"
    ]
    with pytest.raises(ImageSafetyError):
        parse_image_sidecar(
            image_sidecar_bytes(changed), candidate_content=content, candidates=parsed
        )
    new_base = replace(base, rows=(replace(base.rows[0], guardrail_status="BLOCK"),))
    with pytest.raises(ImageSafetyError):
        apply_image_safety(new_base, done, content)
