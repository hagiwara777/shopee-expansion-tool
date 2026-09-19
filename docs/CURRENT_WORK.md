# CURRENT WORK

本書は再開案内。長寿命の承認済み状態はgovernance/state.json、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

SG Category Mapper Minimum Betaの最小製品実装を、formal main `15e3ce242953bfa7592e0d89d790d85db8512f83`を基点とする専用branchで検証している。正式フローは、共通Safety → SG Safety → Prelisting Gate → SG Category Mapper（AI候補 → 商品単位の人間確認 → Category確定）→ STOPである。

入力は全行ELIGIBLEの正式SG Prelisting Gate CSVだけとする。出所確認済みSG Category catalogは全件validation後にSG分をreplaceし、古いSG IDをmergeで残さない。AIは既存Category AI Coreと固定Luna profileを候補提示だけに使い、confidenceにかかわらず自動確定しない。Category確定は現在のSG catalogにあるID・path一致・leafを再確認し、既存marketplace付きDBへASIN単位で保存する。保存済み結果も再表示時に現在catalogへ再検証する。

PH runtimeはACTIVE / ALLOWED、SG operationはINACTIVE / development ALLOWEDを維持する。`ph.beta.operation`と`sg.safety.baseline`をprotected capabilityとして保護し、Battery、Community NG、own penalty、その他既存BLOCK / REVIEWをCategory確認で解除しない。DB migration、Candidate 15列、Prelisting Gate公開contractは変更しない。

## 次の単一作業・停止条件

local mandatory technical gates、Draft PR、CI、Verifier、現在headにbindingしたOwner Acceptance Summaryまで完了して停止する。formal mainへのmergeには、そのexact headに対するOwner Acceptanceが必要である。

SG Categoryを人間確認しても`listing_ready=false`を維持し、SG rowsをgroups CSV、listing TXT、handoffへ出力しない。SG Brand、SG SLS runtime、`listing_ready`、handoff、live Shopee / Keepa / OpenAI API、deploy、自動Category確定、自動出品は未承認であり、本工程に含めない。

実SG production catalogのsource identityと内容は未確認であるため、今回のoffline実装とfixture検証だけで実運用を開始しない。SG catalog未取込・破損・現在catalog不一致はfail closedとする。

## 再開・更新・rollback

再開時はGitでcurrent formal mainを確認し、DEC-0078、DEC-0079、governance/state.json、SG Category Mapper Minimum Beta設計Gate結果、DEC-0077、`guardrails/sls_market_categories/README.md`を確認する。SG SLS canonical / Master MatrixをCategory AI catalogとして使用しない。

rollbackはSG Mapper追加、共通AI adapterのmarketplace対応、PH-only export guard、UI接続、tests、docsを通常revertする。DB migrationはない。既に保存されたSG rowsはoperation INACTIVEのまま利用されず、必要ならGit外local DBをバックアップ後にSG marketplace rowsだけ運用手順に従って除去する。PH operation、PH catalog / mapping、SLS資産、Safety資産は維持する。
