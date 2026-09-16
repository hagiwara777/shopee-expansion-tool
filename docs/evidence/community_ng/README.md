# Community NG evidence

## Source identity and storage

The owner supplied two CSV files on 2026-09-16. Their exact names, SHA-256 values, physical data-row counts, nonblank record counts, normalization counts, and raw storage policy are recorded in `guardrails/community_ng/source_manifest.csv`.

The files contain ASIN, brand or product-like list values and NG-reason text. A scan found no URL, email/poster identity, buyer ID, credential, token, or password marker. The raw files are still not committed: the normalized runtime assets and a hash-pinned manifest are sufficient, while the owner-provided originals remain repository-external evidence.

## Normalization results

ASIN source:

- 49 nonblank marketplace records became 46 unique marketplace + ASIN BLOCK rows.
- SG duplicate occurrences were consolidated: `B07ZNKLPGT` appeared on source rows 5, 6, and 11; `B09LQDNG7K` appeared on rows 7 and 13. The normalized row retains the first source row.
- Leading or trailing whitespace was removed. All 46 normalized ASINs satisfy the existing 10-character uppercase alphanumeric contract.
- The same ASIN remains independently recorded when it appears in different marketplaces.

Brand source:

- 55 marketplace-scoped records and 224 unknown-marketplace records were present.
- All 224 unknown-marketplace records are `UNSCOPED / DEFERRED`. They are retained only in the hash-pinned raw evidence and are not expanded to a marketplace runtime.
- `SUNTORYのサプリメント` on SG source row 9 is excluded from the brand asset. It does not create a SUNTORY-wide block.
- `Boseイヤホン、ヘッドホン全般` on PH source row 14 is normalized to brand exact `Bose`.
- `G=SHOCK` on SG source row 14 is grouped under brand key `g-shock` with exact aliases `G-SHOCK` and `G=SHOCK`.
- `グルマンディーズ` and `Gourmandise` share brand key `gourmandise` in each marketplace where both source forms occur.
- `ZOJIRUSHI ` is trimmed, `Shu  Uemura` is space-collapsed, and full-width `＆honey` is NFKC-normalized to `&honey`.
- `B08DHKD9T4` in the VN brand column is quarantined as ASIN-in-brand-field and is not added to either asset.
- Six duplicate groups in the unknown-marketplace column are reported in the manifest count but do not affect runtime data.
- The final asset contains 48 marketplace + brand-key concepts and 54 exact match rows.

## Runtime boundary

SG and PH load the common assets in addition to their non-community market dictionaries. Community matches always BLOCK, and existing stronger or source-specific evidence such as `own_penalty_case` or Shopee brand-list evidence remains in the audit output. Legacy `community_report` rows derived from the unknown-marketplace column are removed from the SG market dictionaries, and legacy PH community brand V2 rows are replaced by this common source.

MY, TH, TW, and VN are data-only in this change. Their product runtimes are not implemented.
