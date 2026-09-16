# Community NG Safety assets

This directory is the normalized, marketplace-scoped source of truth for owner-provided Community NG ASIN and brand blocks.

- `marketplace_asin_blocks.csv` stores marketplace + ASIN exact BLOCK rules.
- `marketplace_brand_blocks.csv` stores marketplace + normalized brand exact BLOCK rules. `brand_key` groups confirmed aliases; `match_value` is the actual exact-match value.
- `source_manifest.csv` pins each owner-provided source by original file name and SHA-256. Raw files remain owner-provided, repository-external evidence.

Runtime loading is currently limited to SG and PH. MY, TH, TW, and VN records are versioned now for future marketplace gates and must not affect SG or PH.

The raw NG-reason columns are intentionally excluded. They are evidence context, not runtime decision conditions. Unknown-marketplace rows are not promoted to any marketplace. A source change requires a new source ID and hash-pinned normalization review; do not overwrite an existing source identity.
