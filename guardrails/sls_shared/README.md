# SLS shared safety assets

This directory contains fail-safe safety signals shared by SLS runtime markets.

## Battery review rules v0.1

battery_review_rules.csv is the single shared source for the PH and SG runtime
battery signal. A match means REVIEW, not a confirmed prohibition. It prevents
automatic listing preparation until a human has verified all applicable SLS
battery requirements:

1. permitted UN/PI classification;
2. Battery product pre-registration;
3. a valid SDS; and
4. the required parcel label.

The v0.1 runtime scope is PH and SG only. The asset does not start MY, TH, TW, or
VN product runtime. Market-specific rules remain independent and retain
precedence through BLOCK > REVIEW > SAFE.

The SLS Category Matrix is outside this asset. It is reserved for the separate
SLS Market Category Rules phase and must not be inferred or activated here.

The CSV is mandatory and fail-closed. Its column order and rule contract are
validated by modules/guardrails.py. Stable rule identifiers are carried at
the start of each note as SLS-BAT-NNN.