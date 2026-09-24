# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

Shopee共通Token Manager Minimum Betaのoffline実装とPH先行技術検証はDraft PR #86で完了し、現在はWAITING_APPROVALで停止している。formal mainの設計GateはPR #85 / DEC-0083で受入済み。PR #86は未mergeであり、Token ManagerのPH runtimeは初期OFFのまま、実credential・実token・Shopee production APIを使用していない。

共通Managerは代表shopとmarketplaceをbindingし、Access / Refresh Token同一generation、READY / IN_FLIGHT / BLOCKED、on-demand refresh、Git外fileへのatomic replace、Windows cross-process lock、protected DACLの設定・読戻し、不明結果のfail closedを実装した。PH Catalog Clientへだけ最小接続し、一時Access Token overrideを第一優先、明示ON時だけManagerを使用、OFFではlegacy credentialを維持する。Manager ON時の障害でlegacy tokenへ黙ってfallbackしない。SG / MY / THには同じManager実装をofflineでbindingできるが、各runtimeは有効化していない。

ローカルの全offline pytestは1436件PASS、PH / SG protected regressionは574件PASS。Governance V2は設定ValidateとPowerShell 5.1 / 7を含む6 mandatory local-validation gateがcommit-bound EvidenceでPASSし、CONTINUEを確認した。PR #86のGovernance、全offline、protected PH / SG、security checksは実装headでPASSした。git diff --checkはPASSし、変更差分に実secretは確認されていない。Shopee公式current Refresh Token文書は直接取得できずPRIMARY_SOURCE_UNVERIFIEDであり、DEC-0083記録済みcontract以外を推測で補完していない。

## 次の単一作業

Ownerの別承認後に同じCodexタスクでPH live validationを行う。実施前にPR #86の最新head・CIを再確認し、Shopee公式current contractの未確認を解消する。承認対象はactual PH Refresh Token登録、Git外credential file作成・変更、production refresh request、PH live Category / Brand / Attributeのread-only確認を個別に明示する。承認まではいずれも実行せず、formal mainへのmerge、deploy、SG / MY / TH runtime有効化も行わない。

SG production Category source identityは共通Token基盤、PH先行live検証、共通Catalog Clientの後に再開する。SG operationはINACTIVE / ALLOWED、listing_ready=false、SG export / handoff停止を維持する。

## 現在の工程境界

SG Category確定後も`listing_ready=false`を維持し、SG rowsをgroups CSV、listing TXT、handoffへ出力しない。SG Brand、SG SLS runtime、`listing_ready`、handoff、live Shopee / Keepa / OpenAI API、deploy、自動Category確定、自動出品は未受入であり、本工程の成果に含めない。

実SG production catalogのsource identity、実catalogでの実商品受入、SG live OpenAI API、AI意味精度、Evidence hashによる完全自動失効は未確認である。これらの不在を補う推測・自動化は行わず、catalog未取込・破損・現在catalog不一致はfail closedとする。SG operationを開始しない。

Token Managerのoffline実装候補はDraft PR #86で検証済みだが、formal mainの正式受入やlive認証の承認を意味しない。

## 再開・更新・rollback

再開時はGitでcurrent formal mainを確認し、DEC-0083、DEC-0082、DEC-0081、DEC-0080、DEC-0079、DEC-0078、`governance/state.json`、`guardrails/sls_market_categories/README.md`を確認する。SG SLS canonical / Master MatrixをCategory AI catalogとして使用しない。

PR #82の製品変更を戻す必要がある場合は、SG Mapper追加、共通AI adapterのmarketplace対応、PH-only export guard、UI接続、tests、関連docsを通常revertする。DB migrationはない。PH operation、PH catalog / mapping、SLS資産、Safety資産は維持する。今回の文書正本化だけを戻す場合は、そのdocs-only change setを通常revertする。
