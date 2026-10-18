# P5最小接続のoffline開発

DEC-0144。既存P1/P2/P3/P4とSGの有限枠を再利用する案Bの接続契約。
本書のコード・synthetic testsは実API成功、実商品受入、C12や実務Beta完成を証明しない。
実施対象・取得量・費用は[P5実施設計・承認票](P5_ACCEPTANCE_EXECUTION_PLAN.md)で別に固定する。
trusted組成のoffline境界、固定selectionの商品資料世代更新、新規保存先の検査契約は
[P5 live設計](P5_LIVE_DESIGN.md)／DEC-0146を参照する。旧formatの停止を解除しない。
Owner指定情報と今回の実行Evidence・実行承認は区別し、具体値と原指示は非公開票に保持する。

## 入口と許可

`app_beta.py --p5-config <scope-json>`は各市場の`P5Scope`だけを読み、接続準備を表示する。
通常起動・P4起動・既存ショートカットの意味は維持する。Scopeにrun、市場、shop、credential参照、
release/実行対象、専用root/P2 store ID、商品/leaf/Finder query、各有限枠を結合する。
配置は`<root>/<run>/<market>/<shop>/`の`work.sqlite3`、`keepa.sqlite3`、`ledger.json`、`claim.json`。
Keepaの商品取得枠は再取得を含む要求商品数であり、準備商品数・出品数ではない。

設定だけで実行は許可しない。`P5Runtime`の明示startには、別承認されたtrusted integrationから
完全scopeに一致する`P5ExecutionPermit`と、release/実行対象の観測関数を注入する必要がある。
許可をJSON・環境変数・checkboxから作るloaderはない。標準の`--p5-config`入口はpermitを作らず停止する。
今回、そのlive許可注入・実credential参照の解決・保存先設置・release反映は行わない。
Python object/referenceは人間承認の暗号学的証明ではなく、trusted adapterの責務境界である。

## 探索と対象固定の二段階（offline接続）

DEC-0145。`preparation_limit > 0`の明示scopeでは、`asins`は探索前の承認商品（Expansion seed等）のまま変更しない。
strict Finder query全体・1ページの最大返却件数（最大50）と、両入口を合わせた最大準備商品数を先に固定する。
Resolverは`resolver_inputs`のJSON文字列へ`source_id`・元の`input_title`・商品出所`origin`を固定する。
これらも元のscope digest・permit・claim・累積予算へ結合する。複数Finder計画・自動fallbackは許可しない。
既存の固定ASIN scope（limit=0）のdigestとledger形式を維持し、新方式へ自動移行しない。

Finder送信予約にqueryを結合し、成功応答のASIN集合を同じledgerのchecksum・atomic replace内へ保存する。
上限超過・重複・欠損応答は停止し予約を維持する。別client・再起動でも同じqueryを再送できない。
詳細取得は承認seed・そのFinder返却候補・人間が明示した承認Resolver入力の候補だけに制限する。
Resolverの詳細取得対象確認と、取得後の型番・仕様・同梱を比較する同一性確認は別操作。
`FOUND / KEEPA_VERIFIED`だけでは同一性を認定せず、UNKNOWN・MISMATCHから準備対象を作らない。

両入口で作業者・根拠付きの明示選択を一度固定し、その商品だけから固定15列CandidateとSafety sidecarを一式再生成する。
選択、元のproducer資料、Resolver出所と同一性状態は同じledgerに保存する。フィルター変更や別batch化で
同じ探索／source_idの対象を追加・差替えできない。未選択・資料不一致はP5の保存・分類・出力境界でも拒否する。
Safety／全ショップ照合の現在結果が停止ならCategory／Brand人間確定も停止する。既存validator・辞書を変更しない。

統一アプリの「準備対象を固定してSafetyへ引き継ぐ」の後、全ショップCSVを確認してSafetyを別操作で実行し、
「今回の商品根拠を確認待ちへ保存」から既存P3/P2へ渡す。保存済み商品群は分類画面から追加APIなしで再搬送できる。
市場切替・再起動では選択と予算・P2履歴を保持するが、現在の全ショップ資料・分類資料と人間確認を再要求する。
模擬receiptとoffline CSVのFALSE／PH_SG_P1_OFFLINEを維持し、運用CSVへ昇格しない。

停止条件：既存scopeのASINや上限の書換え、claim／ledger欠落、固定対象の差替えは自動修復しない。
旧formatで選択後の商品Fact・Candidateが変わった場合は停止し、固定資料の再搬送までとする。
P5選択への同一ASIN複数行入力も停止する。通常Resolverの元行保持・既存Gate境界の一意化は変更しない。
新規設置の更新対応formatではP5_LIVE_DESIGNのjournal/P2照合を通して同じ固定対象の資料だけを更新する。
その場合も旧selection・予算・履歴を消さず、固定ASIN集合を維持する。新scope／新ledgerによる枠復活は禁止。
実承認source・現在観測・Windows設置検査のproduction接続は別に必要であり、
本方式はF08 live、実商品受入、実務Beta完成を意味しない。

起動・初期表示・再描画・F1/F2条件変更では通信しない。P5は既存Amazon factoryへfallbackせず、
専用clientを明示取得操作へ注入する。P4合成商品・mock catalog loader・画像replayと旧診断入口を使わない。
Category AIの予算付きproviderは接続部品として分離し、初回の日常操作はHUMAN中心とする。

## 到達可能な通信

| 経路 | P5の制御 |
|---|---|
| Keepa Product/Finder/token | bounded transportの送信前hook。JP、承認ASINまたは承認Finderの取得候補、strict 1ページ最大50件、query全体一致。offers/update/buybox等を拒否。requests・要求商品数・最大tokenを個別予約 |
| Shopee Category/Brand/Attribute | `ShopeeCatalogClient`のP5 policy hook。市場/shop/production host/endpoint/leaf/パラメータを照合。redirect・自動retryなし。strict Brandの今回取得最大10ページを維持 |
| OpenAI Category/画像 | Responses endpointだけ。既存`OpenAIValidationBudget.ceiling`を再利用しmodel・入力上限・出力・画像数・requests・最大費用を送信前予約。初回上限は最大USD 1の既存計算契約内 |
| Google Bridge | 専用sheetとA:Cだけ。既存Access Token Sourceの市場/shop/行検証を再利用。Sheets host、timeout、物理requestsを制限 |
| Google認証更新 | 明示したservice account/authorized user file参照のみ。external account/外部コマンド/impersonationを読込前に拒否。ADC/metadata fallbackなし。注入したRequestからoauth2 token endpointだけへ送信。retry先も同じ有限枠を通し、失敗後の再送を拒否 |
| 画像GET | 既存Amazon画像host allowlist、redirectなし、有限件数、timeout、streamのサイズ/時間制限。既存画像validator・pixel上限も維持。途中失敗は予約を保持 |

Google/画像の通信件数をKeepa tokenやOpenAI費用と合算しない。PH/SGの承認上限は別scopeへ分配し、
両scopeの合計がOwnerの全体上限以内であることを実行承認票で確認する。
350 tokens、USD 1、Shopee 69 requests/市場は未承認の提案値。実行許可へ自動採用しない。

SGのOS process lease、checksum、fsync＋atomic replace、保存失敗後の停止を再利用する。
同じscopeの二重openを拒否し、ledger/claim/storeの欠落・不一致を自動修復しない。
最大予約は成功時も返金しない。実測は別欄へ保存し、失敗/再起動/残token補充で承認枠を戻さない。
Keepaは`tokensConsumed`を成功・エラー応答から記録する。欠損・不正・見積超過・timeoutはUNKNOWNとし、
予約を保持して停止する。未完了予約を残した再起動は停止し、自動retry・新ledgerによる復旧はしない。
復旧は保存済み記録と外部実測を照合して別途判断する。旧DB/ledgerを削除・resetしない。

## Category・Brand・Attributeと出力

P5 Categoryは不正raw行を読み飛ばさず、ID/parent/name/leaf/重複/矛盾を拒否する。
既存階層validatorに加え、承認されたP5 clientからの取得と今回session/catalog bindingをメモリに保持する。
単なるreference文字列や`supply_catalog()`だけではP5実運用出力を許可しない。
fake HTTP clientはOFFLINE_MOCKのままで、公式Category/Brandへ昇格しない。
Category更新開始で旧receipt・Brand・Attributeを失効する。再起動後にreceiptを復元しない。

Attributeは既存`get_attribute_trees()`を使い、NOT_FETCHED/FAILED/FETCHED、対象leaf、session、取得世代、
treeと件数を画面へ渡す。空treeを必須属性0件と推定しない。属性自動入力やDB移行は追加しない。
Seller Centerの必須属性・販売可否・発送条件は人間の最終確認として残る。

P5出力はP1の現在Safety/重複/分類/公式BrandとSG正式運用gateを通す。
P2 `BetaWorkBench.output(operational=True)`はP1出力後、commit前、commit後のbytes返却前に
実運用許可も再確認する。保存前にbytesを返さず、返却直前の失効では保存済み投入予約を保持する。
downloadと外部投入を分け、UNKNOWNのlock・5状態は既存P2のまま扱う。
P4既定のFALSE/PH_SG_P1_OFFLINEは変わらない。

P5は初回HUMANに限定し、個別AUTO_RULE permitを注入しない。
HUMANで検索・候補・分類/Brand確認・保存・再確認は検証できるが、C04限定自動確定の実務成立は未達。
C04をBeta後へ移したり、HUMANだけで全体PASSにしない。
対象画像には今回P5経路の取得bindingも要求し、P4画像replayや他sessionの検査を流用しない。
対象外には新しい画像人間確認を要求せず、Battery/SLS/Gate/SG本体等の停止は維持する。

## 検証とlive前の停止境界

主な追加検証は`test_p5_runtime.py`、`test_p5_output.py`、`test_p5_ui.py`。
P1/P2/P3/P4、F1/F2、Catalog、Keepa、画像、PH/SG protected回帰とmandatory CIを併用する。
default HTTP関数をmockする正常出力testsは契約のsimulationであり、公式/live証拠ではない。
実行結果・Git/PR/head・Owner判断はGit外Evidence/Task Context/GitHubに置く。

Shopee現行公式API仕様はPRIMARY_SOURCE_UNVERIFIED。現行clientとfixtureの契約を実装しただけで、
現行公式の全件取得・paging・権限・制限が確認済みとはしない。permit注入前に3 endpointの一次資料を確認する。
OpenAIの価格表は既存計算表を使う。paid送信は別途現在価格の確認参照を要求し、価格差があれば再見積り・最小修正する。
対象shop/ASIN/leaf、認証参照、専用保存先/権限/backup/復旧、観測release/実行対象、有限枠、
実API操作のOwner明示承認が揃うまでliveへ進まない。

実出品0件でも準備・再起動・追加・出力・既存正当出品CSV照合は検証できる。
投入成功等はfixtureと実際の結果を別記し、実行していない商品に実SUCCESSを記録しない。
A01〜A07、C01〜C12、F08 live、Owner受入を個別採点する。

rollbackはP5入口と対象processを停止し、必要なら通常revertで戻す。既存運用releaseを自動変更せず、
P2履歴・投入予約・消費ledger/claimを保持する。merge・設置・live・実務Beta完成は別のOwner判断とする。
