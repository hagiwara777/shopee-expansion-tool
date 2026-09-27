# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

ShopeeCatalogClient marketplace-neutral化は完了し、PR #92でformal mainへ統合済み。SG production Category source identityのdocs-only候補PR #95はGitHub Ownerの自己Approve review不能により未mergeで保留中。現在の単一作業は、PR #95とは別scopeのGitHub OwnerコメントEvidence対応をGovernanceへ導入し、Owner Acceptance後にformal mainへ統合すること。次にPR #95を新mainへ追従させ、technical gatesとOwner Acceptanceを再取得する。

## Required Decisions

- DEC-0072 / DEC-0073 — Governance正本、protected capability、通常開発とformal mergeの承認境界。
- DEC-0081 / DEC-0082 — SG offline成果、共通Catalog基盤とproduction source identityの工程境界。
- DEC-0084 / DEC-0085 / DEC-0086 — 共通Access Token Source、PH Bridge、既知freshness制約。
- DEC-0088 — Decisionの段階的読込とappend-only正本。
- DEC-0089 / DEC-0090 — PH/SG Catalog Client契約とformal main採用範囲。
- DEC-0091 — GitHub Owner自己review不能時のコメントEvidence、署名、短寿命binding。

## 正式成果と停止境界

PH Category MapperのCategory / Brand / Attribute既存運用は維持した。formal mainでSGに採用済みなのは、marketplaceを明示bindする共通Client、SG用shop/token命名、Google Sheet Source binding、fake requestによるoffline Category / Attribute / Brand contractまで。SG production source identityのread-only確認結果はPR #95の候補であり、未mergeのためformal main成果ではない。実catalog受入、SG Mapper live接続、SG Brand / SLS runtime、listing_ready、handoff、deploy、operation ACTIVE化は未受入。MY / THはINACTIVE / NOT_STARTEDのまま。

PR #92のaccepted headに対するCIではGovernance mandatory 6 gateがPASSし、offline全体は1,458 passed・1 conditional skip。GitHub Owner証跡をbindingしたformal-acceptance VerifierはCONTINUE。governance/state.jsonは開始formal mainから不変で、PHはACTIVE / ALLOWED、SGはINACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTED、`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDのまま。

## 次の単一作業・rollback

本Governance候補の次はPR #95の再bindingとformal acceptanceである。Governance PRもPR #95も現在はformal main merge前にOwner最終承認と全gateを要する。SG production catalog import / acceptanceはさらに別scope・新規タスクとし、実SG production API、credential操作、実商品・live確認を本Governance修正の承認から許可しない。今回の候補はDB migration、credential変更、State変更を伴わず通常revert可能。force pushとdirty resetは使わない。
