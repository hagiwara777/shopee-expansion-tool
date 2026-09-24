# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

Shopee共通Token Manager Minimum Betaの製品実装とPH先行offline検証をcodex/token-manager-minimum-betaで進行中。formal mainの設計Gate受入はPR #85 / DEC-0083で完了済み。Token Managerは代表shopのmarketplace binding、Access / Refresh Token同一世代、READY / IN_FLIGHT / BLOCKED、on-demand refresh、Git外fileへのatomic replace、Windows lockとACL確認、不明結果のfail closedを実装した。PH既存Catalog Clientへの接続は最小変更とし、一時Access Token overrideを第一優先、Managerは明示設定時だけON、OFFではlegacy credentialを維持する。

Shopee公式current Refresh Token文書は直接取得できずPRIMARY_SOURCE_UNVERIFIED。DEC-0083の記録済みcontract以外を推測で補完していない。actual credential file、実token、production refresh、PH live Category / Brand / Attribute、SG / MY / TH live APIは未使用。SG / MY / THには同じManager実装をofflineでbinding可能だが、runtimeはINACTIVE / NOT_STARTEDのままである。

ローカルではFake transport / clock / credentialとWindows一時directoryでToken Manager・PH Category / Brand / Attribute接続を検証した。全offline pytestは1436件、protected PH / SG専用回帰は574件がPASS。最後の小さな接続補強後の再検証、Governance V2証跡、Draft PR、CI、read-only reviewが残る。governance/state.json、Candidate 15列、Prelisting Gate、Safety / SLS、SG operation・export / handoffは変更していない。

## 次の単一作業

補強後のoffline / protected regressionとGovernance V2、diff・secret確認を完了し、scope内のlocal commit、push、Draft PR、CI/checks、read-only reviewへ進む。これらが完了したらWAITING_APPROVALで停止し、別Owner承認までactual PH Refresh Token登録、actual credential file作成・変更、production refresh、PH live Category / Brand / Attribute確認を行わない。formal mainへmergeしない。

SG production Category source identityは共通Token基盤、PH先行live検証、共通Catalog Clientの後に再開する。SG operationはINACTIVE / ALLOWED、listing_ready=false、SG export / handoff停止を維持する。

## 現在の工程境界

SG Category確定後も`listing_ready=false`を維持し、SG rowsをgroups CSV、listing TXT、handoffへ出力しない。SG Brand、SG SLS runtime、`listing_ready`、handoff、live Shopee / Keepa / OpenAI API、deploy、自動Category確定、自動出品は未受入であり、本工程の成果に含めない。

実SG production catalogのsource identity、実catalogでの実商品受入、SG live OpenAI API、AI意味精度、Evidence hashによる完全自動失効は未確認である。これらの不在を補う推測・自動化は行わず、catalog未取込・破損・現在catalog不一致はfail closedとする。SG operationを開始しない。

Token Managerのoffline実装候補はこの作業branchで検証中であり、formal mainの正式受入やlive認証の承認を意味しない。

## 再開・更新・rollback

再開時はGitでcurrent formal mainを確認し、DEC-0083、DEC-0082、DEC-0081、DEC-0080、DEC-0079、DEC-0078、`governance/state.json`、`guardrails/sls_market_categories/README.md`を確認する。SG SLS canonical / Master MatrixをCategory AI catalogとして使用しない。

PR #82の製品変更を戻す必要がある場合は、SG Mapper追加、共通AI adapterのmarketplace対応、PH-only export guard、UI接続、tests、関連docsを通常revertする。DB migrationはない。PH operation、PH catalog / mapping、SLS資産、Safety資産は維持する。今回の文書正本化だけを戻す場合は、そのdocs-only change setを通常revertする。
