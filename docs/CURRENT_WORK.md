# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

PR #92でShopeeCatalogClient marketplace-neutral化をformal mainへ統合済み。DEC-0089のPH/SG共通Client契約を正式成果として採用した（採用記録はDEC-0090）。現在はmerge後のdocs-only正本化候補を確認し、別のformal main mergeにはOwner最終承認を待つ。PR #92自体を未完了の実装候補として扱わない。

## Required Decisions

- DEC-0072 / DEC-0073 — Governance正本、protected capability、通常開発とformal mergeの承認境界。
- DEC-0081 / DEC-0082 — SG offline成果、共通Catalog基盤とproduction source identityの工程境界。
- DEC-0084 / DEC-0085 / DEC-0086 — 共通Access Token Source、PH Bridge、既知freshness制約。
- DEC-0088 — Decisionの段階的読込とappend-only正本。
- DEC-0089 / DEC-0090 — PH/SG Catalog Client契約とformal main採用範囲。

## 正式成果と停止境界

PH Category MapperのCategory / Brand / Attribute既存運用は維持した。SGで利用可能になったのは、marketplaceを明示bindする共通Client、SG用shop/token命名、Google Sheet Source binding、fake requestによるoffline Category / Attribute / Brand contractまで。SG production Catalog API・Category source identity・実catalog受入は未確認であり、SG Mapper live接続、SG Brand / SLS runtime、listing_ready、handoff、deploy、operation ACTIVE化は未受入。MY / TH Catalog Client runtimeはrequest前にfail closedし、両市場はINACTIVE / NOT_STARTEDのまま。

PR #92のaccepted headに対するCIではGovernance mandatory 6 gateがPASSし、offline全体は1,458 passed・1 conditional skip。GitHub Owner証跡をbindingしたformal-acceptance VerifierはCONTINUE。governance/state.jsonは開始formal mainから不変で、PHはACTIVE / ALLOWED、SGはINACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTED、`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDのまま。

## 次の単一作業・rollback

次工程は別scopeの「SG production Category catalog source identity確認」。実SG production API、credential操作、実商品・live確認は別Owner承認を得るまで開始しない。今回の採用差分はDB migration、credential変更、State変更を伴わず、通常のcode/docs revertで戻せる。force pushとdirty resetは使わない。docs-only正本化候補のformal main採用にも別のOwner最終承認を要する。
