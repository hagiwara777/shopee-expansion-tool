# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

PR #85でDEC-0083のToken Manager設計はformal mainへ統合済み。既存在庫管理ツールとPR #86のToken Managerが同じOpen Platform App・shop・Refresh Token系列を共有することが判明したため、今回のdocs-only作業でDEC-0084を追加し、Mapper共通のGoogle Sheet Access Token Source Minimum Betaを現行方針とする。DEC-0083は履歴として保持する。PR #86はDraft、runtime OFF、未merge候補のまま保持し、今回の差分へ混ぜない。

PHはACTIVE / ALLOWED、SG operationはINACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTEDを維持する。`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDのまま保護する。SG Category確定後も`listing_ready=false`、SG export / handoff停止を維持する。`governance/state.json`は変更しない。

## 次の単一作業

DEC-0084に基づき、PH / SG / MY / TH共通のGoogle Sheet Access Token Source Minimum Betaを最小実装し、offlineで検証する。専用Bridge Spreadsheetの最小contractは`marketplace`、`shop_id`、`access_token`。元注文管理表は直接API共有せず、BridgeからRefresh TokenとPartner Keyを読まない。取得したshop_idとローカルexpected shop_idの一致、明示ON後のfail closed、override → Google source → legacyの優先順位を検証する。

今回の正本化では実装、Google credential・Bridge作成、Google live read、Shopee live API、PR #86 merge、deployを行わない。次の実装タスクでもlive確認は独立した承認境界とし、offline結果からPH live成功を推定しない。

## 現在の工程境界

長期順序はGoogle Sheet Access Token Source → PH live確認 → marketplace-neutral ShopeeCatalogClient → SG production Category source identity → 後続SG工程。SG production Category調査は中止せず、共通認証とCatalog Clientの後に再開する。MY / TH runtimeを有効化しない。

実SG production Category catalogのsource identity、実catalogでの実商品受入、SG live OpenAI API、SG Brand、SG SLS runtime、listing_ready、handoff、deploy、自動Category確定、自動出品は未受入。既存Safety、SLS、Candidate 15列、Prelisting Gate契約、DB schemaは変更しない。

## 再開・更新・rollback

再開時はGitでformal mainとPR #86の状態を確認し、DEC-0084、DEC-0083、DEC-0082、`PROJECT_ROADMAP.md`、`governance/state.json`を読む。Bridgeへの書込み責務・credential設定・live Google / Shopee確認は各独立scopeで扱う。今回のdocs-only差分は通常revertできる。PR #86と製品runtimeには影響しない。
