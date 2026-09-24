# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

DEC-0084に基づくGoogle Sheet Access Token Source Minimum Betaの実装候補を作成した。共通SourceはPH / SG / MY / THを同一interfaceで扱い、BridgeのA:C列だけをread-onlyで取得する。marketplaceとローカルexpected shop_idを照合し、欠落・重複・不正行・取得障害ではfail closedとする。PH Catalog Clientの認証優先順位は一時override → 明示ONのGoogle Source → legacy token。Sourceは既定OFFであり、ON後の失敗でlegacyへ戻らない。Access Tokenはメモリ内で利用し、repr・例外・logに出さない。

隔離した依存環境でoffline全体テスト1,430件PASS、PH / SG protected regression 670件PASSを確認した。Google credential、Bridge実体、Google live read、Shopee live APIは未実行。PR #86のToken ManagerはDraft・runtime OFF・未merge候補として今回の差分から分離する。

PHはACTIVE / ALLOWED、SG operationはINACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTEDを維持する。`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDのまま保護する。SG Category確定後も`listing_ready=false`、SG export / handoff停止を維持する。`governance/state.json`は変更しない。

## 次の単一作業

実装候補はDraft PR #88で提示済み。次の単一作業は、別のオーナー承認を得てBridge / Google credentialを実準備し、PHでlive readを確認する工程である。この工程の開始までは`WAITING_APPROVAL`とし、offline結果からPH live成功を推定しない。PR checksとEvidenceの結果はGitHub上で現在のheadに対して確認する。

## 現在の工程境界

長期順序はGoogle Sheet Access Token Source → PH live確認 → marketplace-neutral ShopeeCatalogClient → SG production Category source identity → 後続SG工程。SG production Category調査は中止せず、共通認証とCatalog Clientの後に再開する。MY / TH runtimeを有効化しない。

実SG production Category catalogのsource identity、実catalogでの実商品受入、SG live OpenAI API、SG Brand、SG SLS runtime、listing_ready、handoff、deploy、自動Category確定、自動出品は未受入。既存Safety、SLS、Candidate 15列、Prelisting Gate契約、DB schemaは変更しない。

## 再開・更新・rollback

再開時はGitでformal mainとPR #86の状態を確認し、DEC-0084、DEC-0083、DEC-0082、`PROJECT_ROADMAP.md`、`governance/state.json`を読む。Bridgeへの書込み責務・credential設定・live Google / Shopee確認は各独立scopeで扱う。今回の実装候補は通常revertできる。PR #86と既定の製品runtimeには影響しない。
