# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

DEC-0084に基づくGoogle Sheet Access Token Source Minimum Betaはformal mainへ採用済み。DEC-0085に基づくPH Access Token Bridge自動同期の実装候補を作成し、PH live同期をOwnerが受入した。共通SourceはPH / SG / MY / THを同一interfaceで扱い、BridgeのA:C列だけをread-onlyで取得する。marketplaceとローカルexpected shop_idを照合し、欠落・重複・不正行・取得障害ではfail closedとする。PH Catalog Clientの認証優先順位は一時override → 明示ONのGoogle Source → legacy token。Source設定は未設定または`0`でOFF、`1`でON、その他はfail closedとし、一時overrideを最優先にする。ON後の失敗でlegacyへ戻らない。Access Tokenはメモリ内で利用し、repr・例外・logに出さない。

関連test 82件、offline全体1,445件、protected PH / SG 574件がPASSした。2026-09-25、専用Bridgeをmarketplace / shop_id / access_tokenの3列とPH行だけで準備し、Google read-only用credentialをGit外で確認した。検証プロセス内だけでSourceを明示ONにし、BridgeからPH Access Tokenを1回read-only取得してローカルexpected shop_idとのbindingを確認した。取得TokenによるPH live Catalog read-only確認はCategory 2,301件、Brand先頭ページ1件、Attribute 11件でPASSした。Token・credential本文は記録せず、製品runtime状態は変更していない。PR #86のToken ManagerはDraft・runtime OFF・未merge候補として今回の差分から分離する。

PHはACTIVE / ALLOWED、SG operationはINACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTEDを維持する。`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDのまま保護する。SG Category確定後も`listing_ready=false`、SG export / handoff停止を維持する。`governance/state.json`は変更しない。

## PH Bridge live受入

DEC-0085のPH Bridge同期Scriptを専用Google Apps Scriptプロジェクトへ設置し、元管理表とBridgeのIDをScript Propertiesに設定した。OwnerのGoogle権限承認後、syncPhAccessTokenの手動実行は「実行完了」。5分間隔の時間主導トリガーは1件登録され、2026-09-25 21:32と21:33の自動実行はともに「完了」、トリガー一覧のエラー率は0%。最新の自動実行後、元表のPHは1行、BridgeのPHは1行でshop_id bindingとAccess Token本文の一致を、本文を表示せず確認した。既存GoogleSheetAccessTokenSourceの同期後live読取は、Owner提示のGit外Service Account JSONをプロセス内だけで用いてread-onlyでPASS。PHの期待shop_id bindingと非空Access Token取得を確認し、credentialとtoken本文は表示・記録していない。OwnerはこのPH Minimum Betaのlive結果と全面書込み失敗時の既知制約を受入済み。全面書込み失敗時の旧token消去は保証できない既知制約を維持する。

## 次の単一作業

Draft PRのCI / mandatory technical gatesとOwner Acceptance Summaryを現在のheadへbindして確認する。formal mainへのmergeはOwnerの最終承認までWAITING_APPROVALとし、deployは行わない。

## 現在の工程境界

長期順序はGoogle Sheet Access Token Source → PH live確認 → marketplace-neutral ShopeeCatalogClient → SG production Category source identity → 後続SG工程。SG production Category調査は中止せず、共通認証とCatalog Clientの後に再開する。MY / TH runtimeを有効化しない。

実SG production Category catalogのsource identity、実catalogでの実商品受入、SG live OpenAI API、SG Brand、SG SLS runtime、listing_ready、handoff、deploy、自動Category確定、自動出品は未受入。既存Safety、SLS、Candidate 15列、Prelisting Gate契約、DB schemaは変更しない。

## 再開・更新・rollback

再開時はGitでformal mainとPR #86の状態を確認し、DEC-0084、DEC-0083、DEC-0082、`PROJECT_ROADMAP.md`、`governance/state.json`を読む。Bridgeへの書込み責務・credential設定・live Google / Shopee確認は各独立scopeで扱う。今回の実装候補は通常revertできる。PR #86と既定の製品runtimeには影響しない。
