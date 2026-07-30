# ASIN Resolver Evidence Manifest v1

## Purpose

`evidence_manifest.json` is the machine-readable candidate ledger for one PH ASIN
Resolver batch. It records artifact metadata and relationships, never product titles,
Amazon URLs, ASIN values, or AI response bodies. Those values remain in immutable
artifact files inside the same batch package.

The runtime package is Git-excluded:

```text
outputs/asin_resolver_runs/<batch_id>/
```

Every manifest is UTF-8 JSON serialized with sorted keys and a final LF. Its SHA-256
is stored outside the JSON to avoid recursive self-reference:

```text
evidence_manifest.json
evidence_manifest.sha256
```

The sidecar format is `<sha256><two spaces>evidence_manifest.json<LF>`.

## Required manifest fields

```text
schema_version
batch_id
marketplace
module
formal_main_commit
resolver_version
batch_status
last_completed_checkpoint
resume_from_checkpoint
created_at
updated_at
source_map_artifact_id
artifacts
```

`formal_main_commit` is a mandatory 40-character lowercase/uppercase SHA supplied by
the caller for recording in the Manifest. Batch creation and resume obtain the
independent FORMAL Brief-approved SHA only from
`ASIN_RESOLVER_APPROVED_FORMAL_MAIN_COMMIT` and stop if it is missing, malformed, or
does not match. The application must not derive this value from `origin/main`, HEAD,
a Git fallback, or another UI input.

`batch_status` is one of `IN_PROGRESS`, `PAUSED`, `COMPLETED`, or `BLOCKED`.
Timestamps are ISO 8601 with an explicit timezone offset.

## Artifact records

Each record requires:

```text
artifact_id, batch_id, artifact_type, filename, sha256, producer,
acceptance_status, storage_alias, parent_artifact_ids, created_at, updated_at
```

`source_ids` is optional. `filename` must be a basename inside the package and
`storage_alias` must be the canonical relative form
`outputs/asin_resolver_runs/<batch_id>/<filename>`.

Allowed runtime `acceptance_status` vocabulary is exactly:

```text
RUNTIME_PRODUCED_PENDING_HUMAN_ACCEPTANCE
```

It means the system created the file but no human acceptance has been recorded.
An undefined status, blank producer, blank storage alias, invalid SHA, missing parent,
or a parent from another batch invalidates the package and stops resume without a write.

Supported `artifact_type` values are:

```text
source_input, source_map, initial_prompt, initial_ai_response,
initial_parse_export, initial_candidate_csv, retry_selection, retry_prompt,
retry_ai_response, retry_parse_export, retry_candidate_csv, resolver_export
```

`source_input` is saved first from the pasted text after deterministic UTF-8/LF
normalization. It is never regenerated from a source map or search title. `source_map`
must parent that saved input. The source map contains `upstream_source_id`,
`resolver_source_id`, `input_order`, `original_title`, and `initial_search_title` for
every input row. Legacy one-title-per-line input retains a blank upstream ID; no ID is
invented.

## Checkpoint graph

Each checkpoint changes only after its required artifact files are durable and recorded.
Only these transitions are legal:

```text
BATCH_CREATED -> SOURCE_MAP_SAVED -> INITIAL_PROMPT_SAVED
-> INITIAL_RESPONSE_SAVED -> INITIAL_PARSE_SAVED

INITIAL_PARSE_SAVED -> EXPORT_SAVED -> COMPLETED                 (no Retry)
INITIAL_PARSE_SAVED -> RETRY_PREPARED -> RETRY_PROMPT_SAVED
-> RETRY_RESPONSE_SAVED -> RETRY_PARSE_SAVED -> EXPORT_SAVED
-> COMPLETED                                                      (Retry)
```

Backward movement, checkpoint jumps, skipped required artifacts, Retry artifacts without
the Retry path, or any artifact/checkpoint change after `COMPLETED` are invalid. A
failed validation does not overwrite the manifest, sidecar, or suspect artifact.

## Legacy mode

The Resolver can still be used without an Evidence Batch for ordinary manual work. That
legacy/non-evidence mode has no Evidence Manifest, durable source map, resume guarantee,
or formal fixed-30 baseline status. It must never be reported as an evidence-backed
export or a completed formal batch.
