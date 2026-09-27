# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

SG production Category catalog source identity確認は`SOURCE_IDENTITY_PASS`で完了し、DEC-0091に記録した。SG代表shopの正式認証contextでproduction Category endpointを1回read-only取得し、現行共通normalizationと階層の成立を確認した。次の単一作業は「SG production Category catalog import / acceptance」。

## Required Decisions

- DEC-0072 / DEC-0073 — Governance正本、protected capability、通常開発とformal mergeの承認境界。
- DEC-0081 / DEC-0082 — SG offline成果、共通Catalog基盤とproduction source identityの工程境界。
- DEC-0084 / DEC-0085 / DEC-0086 — 共通Access Token Source、PH Bridge、既知freshness制約。
- DEC-0088 — Decisionの段階的読込とappend-only正本。
- DEC-0089 / DEC-0090 — PH/SG Catalog Client契約とformal main採用範囲。
- DEC-0091 — SG production Category source identityのread-only確認結果、PASSの意味、未受入境界。

## 正式成果と停止境界

PH Category MapperのCategory / Brand / Attribute既存運用は維持した。PH/SG共通Clientのoffline契約に加え、SG代表shopとGoogle Sheet Access Token Sourceのbindingを確認し、Shopee production `/api/v2/product/get_category` の1回の成功応答から2,285 Category（root 31、leaf 1,962）を現行`get_categories()`で正規化できた。source identityのPASSは次工程のimport / acceptance検討に使える根拠に限る。SG production catalog import / DB replace、実catalog・実商品Category acceptance、SG Mapper live接続、Brand / Attribute runtime、SLS runtime、listing_ready、handoff、deploy、operation ACTIVE化、SG Minimum Beta完成は未受入。MY / TH Catalog Client runtimeはrequest前にfail closedし、両市場はINACTIVE / NOT_STARTEDのまま。

PR #92のaccepted headに対するCIではGovernance mandatory 6 gateがPASSし、offline全体は1,458 passed・1 conditional skip。GitHub Owner証跡をbindingしたformal-acceptance VerifierはCONTINUE。governance/state.jsonは開始formal mainから不変で、PHはACTIVE / ALLOWED、SGはINACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTED、`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDのまま。

## 次の単一作業・rollback

次工程は別scope・新規タスクの「SG production Category catalog import / acceptance」。source identity確認だけでimport、SG-only replace、Mapper live接続、実商品受入へ進めない。今回の正本化差分はdocs-onlyで、DB migration、credential変更、State変更を伴わず、通常のdocs revertで戻せる。production raw responseは保存していない。force pushとdirty resetは使わない。
