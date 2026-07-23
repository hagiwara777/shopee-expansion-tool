# PH Category Mapper Ver0.2: AI Category Shadow Mode

## Boundary

The shadow mode is an evaluation-only path. It forms candidates from the local
PH Category DB, sends no more than twenty category ID/path pairs for one product
group to the provider, and accepts no more than three ranked candidates. It does
not change Ver0.1 recommendations, Category mappings, Brand decisions, output
CSV, TXT, or listing readiness.

Only representative titles (up to three), optional Resolver titles (up to three),
normalized group metadata, and candidate Category IDs/paths are sent. ASINs,
credentials, raw CSV content, database files, and raw API responses are never
sent or persisted.

## Persistence and evaluation

`ai_shadow_runs` stores aggregate execution data. `ai_shadow_predictions` stores
only structured candidate/ranking/evaluation fields, never raw AI output or
credentials. A cache key binds marketplace, non-ASIN group key, candidate ID set,
prompt version, provider/model, and a hash of the bounded prompt input.

Predictions are evaluated only when the selected Category has a verification
status of `USER_CONFIRMED`, `LISTING_TOOL_ACCEPTED`, or a future
`SHOPEE_CORRECTED`. This keeps suggested Categories and API presence out of
accuracy metrics.

## Future wrong-category feedback

Ver0.2 does not accept corrections. A future correction table can reference the
existing prediction's marketplace/group key and add source category,
corrected category, correction source, canonical product type, distinct ASIN
count, user-confirmed flag, and corrected timestamp. This leaves existing
Ver0.1 mappings and shadow-run records immutable while enabling evaluated
`SHOPEE_CORRECTED` labels.

## Ver0.2.1 measurement rules

The dashboard separates a local `NO_CANDIDATE` decision from an AI request.
`local_abstain_count` and `no_candidate_count` mean the local PH prefilter had
no safe candidate and therefore made **no** AI request. `ai_request_count`,
`ai_success_count`, `ai_failure_count`, and `ai_abstain_count` describe actual
provider attempts only. A cached result is not a current-run AI request.

An AI guard violation is counted only for a current, successfully validated
structured AI response. It compares the response's main-product, set,
accessory, and replacement-part flags to the input-derived guard. Local
abstention, cache use, invalid provider output, provider failure, and groups
without a confirmed label cannot create an AI guard violation.

For groups with an accepted confirmation label, the dashboard reports the
deterministic prefilter's candidate coverage and Top-1 accuracy separately from
the AI Top-1/Top-3 accuracy. The Top-1 lift uses only the common subset with a
valid AI response and a local candidate. Rank improvement counts the cases where
the confirmed Category moves higher than its deterministic local rank. Candidate
reduction is a descriptive total `(local candidates - AI ranked candidates) /
local candidates`; retaining a single candidate is not counted as a reduction
success.

Each run stores its provider/model, processed group count, actual request count,
and reported input/output/cached token totals. Cost remains `UNKNOWN` unless a
provider supplies an explicit cost value; the app never hard-codes token prices.
Raw prompts, raw responses, credentials, ASINs, and URLs are not stored.

Reference-quality comparison requires at least 10 independently confirmed
product groups and at least 5 of those groups with multiple local candidates.
Below either threshold, results are displayed as limited diagnostic data rather
than evidence that a model is ready for automatic Category selection.

## Re-evaluating stored predictions

Use **保存済み予測を現在の確認結果で再評価** only after a human has completed
the ordinary Category Mapper flow. This action makes no OpenAI request. It
stores an accepted group-specific truth label only for `USER_CONFIRMED` or
`LISTING_TOOL_ACCEPTED`, then compares that label with the stored ranked
candidate IDs. The original prediction, its candidates, model, prompt version,
and provider metadata are never changed.

Each derived evaluation records its timestamp and the Category ID/status used
as truth. Repeating the action with the same truth state is idempotent; a
changed accepted Category or status creates a distinct historical evaluation
state. `SUGGESTED`, API presence, and AI output are never used as truth.

## Avoiding confirmation bias

For independently useful evaluation data:

1. Load a mixed-product CSV.
2. Run AI Shadow prediction before Category confirmation.
3. Close the AI results.
4. Use the normal Category Mapper controls to let a person confirm Categories.
5. After confirmation, run the stored-prediction re-evaluation.
6. Compare the derived Top-1/Top-3 values with the human decisions.

Do not treat data as independent accuracy evidence when the person selected a
Category while viewing the AI candidates. Such data may remain a workflow
diagnostic, but it must not be generalized as AI accuracy. For an initial
benchmark, 10 confirmed groups with 5 multi-candidate groups are the minimum;
20–30 confirmed groups, 10 multi-candidate groups, and roughly 100–300 items
are preferred. Food, supplements, and medical categories may be excluded from
the initial benchmark, but a result excluding them must not be generalized as
overall-category accuracy.

## User acceptance procedure

1. Use Category Mapper exactly as in Ver0.1 to upload a PH eligible CSV and
   confirm Category/Brand decisions. Before and after an AI trial, its
   recommendations CSV, groups CSV, TXT, and ready count must remain unchanged.
2. Open the closed **AI Category推薦を試験する（出品結果には反映しません）**
   section at the bottom. Confirm the maximum group count and the notice that an
   AI API fee may occur. Do not enter or display an API key in the UI.
3. If local AI credentials are not configured, the displayed safe non-execution
   notice is the expected result. If they are configured, select **AI試験を実行**
   once; the mode is sequential (concurrency one), has no automatic retry, and
   limits each request to 30 seconds and the whole run to 180 seconds.
4. Review only the displayed top-three candidates, current confirmed Category,
   the separate local/AI request counts, prefilter and AI reference values,
   ABSTAIN state, short reason, elapsed time, and token count. Do not treat a
   recommendation as a Category decision. Confirming a Category continues to
   use the existing Ver0.1 controls.
