# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

PR #82はOwner Acceptance後、accepted head `c2f15648d189d2d885fe97bda96c3464fcf2fa48`を含むmerge commit `925e022810b0953df4b51ecfb976ce089e06892c`でformal mainへ統合済みである。前SG Category Mapper Minimum Beta正本化タスクは完了した。今回のdocs-only正本化では、Shopee Open Platformの認証・Catalog取得を市場ごとに複製せず、共通Token ManagerをPHで先行検証してから共通Catalog ClientとSG production確認へ進む順序を記録する。Token Manager、Catalog Client、SG live APIの実装は開始しない。

正式成果は、全行ELIGIBLEの正式SG Prelisting Gate CSVの受理、SG-only catalog replace前の全件validation、Category AI CoreのSG offline契約、`marketplace=SG`のProductEvidence、Fake Provider検証、商品単位の人間Category確認、ASIN単位の保存、保存済みCategoryの現在catalog ID / path / leaf再検証である。SG UIはlive OpenAI providerの生成・実行経路を持たず、検証済みcatalogからの手動leaf確認だけを提供する。

PH runtimeは`ACTIVE / ALLOWED`、SG operationは`INACTIVE / ALLOWED`を維持する。`ph.beta.operation`と`sg.safety.baseline`をprotected capabilityとして保護し、Battery、Community NG、own penalty、その他の既存BLOCK / REVIEWをCategory確認で解除しない。DB migration、Candidate 15列、Prelisting Gate公開contractは変更していない。

## 次の単一作業

Shopee共通Token Manager Minimum Betaの設計Gateを行う。認証はmarketplaceの代表となる認証済みshop単位、Category / Brand / Attribute catalogはmarketplace単位として扱う。Access Tokenのon-demand refresh、credential安全保存、refresh失敗時fail closed、PH既存手動Access Token fallback、PH既存経路保護を設計対象とする。正確なtoken TTL、refresh endpoint、request / response contractは、実装前に最新の一次資料または実API contractで確認する。

SG production Category source identityは中止せず、共通Token基盤、PH先行検証、共通Catalog Clientの後に再開する。SG operationは`INACTIVE / ALLOWED`、`listing_ready=false`、SG export / handoff停止を維持する。

## 現在の工程境界

SG Category確定後も`listing_ready=false`を維持し、SG rowsをgroups CSV、listing TXT、handoffへ出力しない。SG Brand、SG SLS runtime、`listing_ready`、handoff、live Shopee / Keepa / OpenAI API、deploy、自動Category確定、自動出品は未受入であり、本工程の成果に含めない。

実SG production catalogのsource identity、実catalogでの実商品受入、SG live OpenAI API、AI意味精度、Evidence hashによる完全自動失効は未確認である。これらの不在を補う推測・自動化は行わず、catalog未取込・破損・現在catalog不一致はfail closedとする。SG operationを開始しない。

この文書正本化がformal mainへ統合された後、このCodexタスクを閉じる。次工程は新規Codexタスクとし、Shopee共通Token Manager Minimum Beta設計Gateのscope・設計Gate・Owner承認を確認してから開始する。

## 再開・更新・rollback

再開時はGitでcurrent formal mainを確認し、DEC-0078、DEC-0079、DEC-0080、DEC-0081、DEC-0082、`governance/state.json`、`guardrails/sls_market_categories/README.md`を確認する。SG SLS canonical / Master MatrixをCategory AI catalogとして使用しない。

PR #82の製品変更を戻す必要がある場合は、SG Mapper追加、共通AI adapterのmarketplace対応、PH-only export guard、UI接続、tests、関連docsを通常revertする。DB migrationはない。PH operation、PH catalog / mapping、SLS資産、Safety資産は維持する。今回の文書正本化だけを戻す場合は、そのdocs-only change setを通常revertする。
