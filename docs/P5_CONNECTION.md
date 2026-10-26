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
許可をJSON・環境変数・checkboxから作るloaderはない。標準の`--p5-config`単独ではpermitを作らず停止する。
実原承認record、trusted operatorの実processへの登録、保存先設置・release反映は別承認後に結合する。
Python object/referenceは人間承認の暗号学的証明ではなく、trusted adapterの責務境界である。

### trusted processからの最小起動接続

`modules.p5_initializer.initialize_and_run()`は、承認済みtrusted processが保持する
既存`P5OwnerAuthority`、`WindowsP5Observer`、`P5ServiceCredentials`、`P5Checkpoint`と
原承認参照を受け、`P5Operator`を組成して`register_operator()`へ渡す。
同じinterpreterのStreamlit bootstrapで、固定した`app_beta.py`へ`--p5-config`を渡す。
登録は`configured_runtime()`より前であり、再描画script内からinitializerを呼ばない。
通常のStreamlit起動と`app_beta.py`は変更しない。import時の登録・CLI/env/JSONからの部品loaderはない。

承認済み呼出側の接続箇所は次の形とする。各objectは既存のtrusted確認で準備するもので、
この例は原承認sourceやcredentialを作成する手順ではない。

```python
from modules.p5_initializer import initialize_and_run

initialize_and_run(
    authority=reviewed_authority,
    observer=windows_observer,
    credentials=service_references,
    checkpoint=approved_checkpoint,
    approval_reference=original_approval_reference,
    scope_config=private_scope_path,
)
```

呼出側processの実OSコマンドラインにも`run <当該checkoutのapp_beta.py>`を残す。
例は`python <承認済みtrusted起動担当.py> run <app_beta.py>`の形であり、起動担当の
実コード・所在・原承認source・現在票・引数処理は別承認の実設置で固定する。
Pythonの`sys.argv`書換えではOS観測を代用できず、引数欠落・別entrypointは既存Windows検査で停止する。
新しいserverはobserverのportにloopback限定で起動し、Streamlitのscript実行対象は
`__main__.__file__ == app_beta.py`を維持する。子processへ登録を失う起動や別scriptへの実行先変更は行わない。
initializer自身もWindows観測のimport元・ロード済み関数／現ソース検査対象に含める。

起動接続はpermitを発行しない。原承認・現在票・実コード・保存identity等の照合と既存DB openは
従来の明示start後だけであり、secretはさらに承認済みservice操作時まで読まない。
初期描画・再描画・市場切替は追加送信・保存初期化を行わない。未設置先を自動作成しない。
既存operatorは原承認scopeとservice参照に結合されるため、他市場/shopの票を同じ許可で開始できない。
別対象に切り替えるために登録を差し替えず、対象ごとの承認済みprocessと分離した既存保存先／枠を使う。
標準`--p5-config`単独の未登録停止、実source不存在・不一致・期限切れ・撤回時の停止は維持する。

`tests/test_p5_initializer.py`は実`app_beta.py`のAppTestで合成接続・明示start・再描画と撤回を検証する。
server/socket、OS、承認と保存先は合成境界であり、実Windows起動やOwner原承認・実設置の成功証明ではない。
rollbackはP5利用停止と通常revertとし、既存checkpoint・予約・UNKNOWN・claim・履歴を保持する。

### production参照接続のoffline差分（DEC-0147）

`P5TrustedAdapter`は原承認検証interfaceが欠落・失敗した場合、安全な理由だけで停止する。
原承認recordを作るloader、APPROVED文字列からの許可生成、日常UIへのpermit発行は追加しない。
production組成では以下の実装部品も要求し、従来の任意callbackは合成検証に限る。

- `P5CodeIdentity`はimport元のcheckoutからGit root、origin、clean状態、実HEAD/treeと
  実行中`app_beta.py`、P5/runtime/transport/Catalog import元とロード済み関数/メソッドを現在ソースへ照合する。
  観測release・tree digest・entrypointを原承認に結合された観測と比較し、設定releaseの返却で代用しない。
  fetch・checkout・設置は行わない。同じOSユーザーによる任意Python改変の隔離保証ではない。
- `P5CredentialReference`はPH/SG、市場別shop、明示audit.env/Google file参照、Bridgeを固定する。
  非秘密参照のdigestも承認観測の`credential.binding_digest`へ含める。
  `P5CredentialResolver`をadapterに明示注入し、承認・開始検査の後、必要時だけ既存PH/SG readerを呼ぶ。
  読込後に実shopも照合し、legacy Access Tokenは破棄する。tokenは既存bounded Bridgeで後から解決する。
  ADC・既定path・環境探索へのfallbackは追加しない。このresolver自身の責務はShopee/Google参照に限定する。
  Keepaは下記のservice別接続だけを使い、OpenAI keyのproduction参照は未接続。空keyはclient生成前に停止する。
- BridgeはGoogle credential本文の読込前にもBridge/auth操作許可を検査する。
  Sheetsはscopeのsheet・A:C・ROWSだけとし、Bridge 1回につきOAuth物理sendは最大1回。
  追加send・redirect・timeout・認証後のparse失敗・Bridge token不一致は停止し、
  既存ledgerの予約と停止状態を保持する。Shopee/Bridge/authは従来どおり別計数とする。

実原承認source・端末/実process/port・保存先への設置と実credential参照の承認済みrecordは未結合。
下記のoffline部品をfixtureや自己申告で実設置成功へ昇格しない。
標準起動は引き続き実行不可。offline testsの合成authority・mock HTTPはproduction証明ではない。

### production組成の最小offline接続（DEC-0149）

- `p5_operator.P5OwnerAuthority`はtrusted operatorが原文と現在票を照合したtyped recordを受ける。
  Owner・原文・日時・対象scope・操作集合・有限配賦・期限・終了条件・撤回と票digestを固定し、
  元sourceと現在票を開始・操作・出力時に再取得して変更・欠落を拒否する。
  自己申告JSON／APPROVED文字列を原承認へ変換するloaderはない。独立human-origin証明ではない。
- `P5Operator`はこのauthority、`WindowsP5Observer`、service参照、checkpointを組成する。
  trusted process initializerが明示登録したobjectだけを既存app_beta入口で使用する。
  登録をJSON／CLI／環境変数／UIから行わず、実recordがない通常起動は停止する。
  `--p5-config`の初期表示ではpermitを作らず、明示start後だけ組成・検査・既存DB openを行う。
  同じscopeの再描画は既存runtimeとleaseを保持し、追加send・secret読込・DB作成を行わない。
- `p5_windows`は実PID・開始時刻・実行SID・実Python/entrypoint・listenerの所有PIDとloopbackを観測する。
  既存scopeはmachine/PID/開始時刻/portから実行対象を導く。新規設置のversion付きprofileは下記を使う。
  いずれも実process観測をclean release・tree・import元・ロード済みコードと結合する。
  storageは全祖先のreparse／SUBST、volume/file identity、保護先との非重複、hardlink、専用ACLと容量を検査する。
  実体不明は停止。constructor/importはOS観測・ACL変更・probeを行わない。
- `WindowsStorage.setup()`を既存P5Setupへ渡す。未作成先はvolume／祖先／非重複／容量だけを先に検査し、
  新規親を含む排他作成・専用ACL設定後、完全なidentity／ACL検査とprobeを要求する。
  installation rootは作成を承認された親範囲を含めて固定し、既存path・途中残骸は採用・再初期化しない。
  backup・隔離復旧も同じ作成前／作成後検査を使い、既存のmanifest・履歴・UNKNOWN照合を維持する。
- `P5ServiceCredentials`は使用serviceの非秘密参照digestを原承認観測へ結合する。
  Keepaは`P5KeepaReference`で明示した既存環境変数名だけを必要時に読む。既定名探索・他serviceへのfallbackはない。
  この環境変数はkeyの参照元であり実行承認ではない。keyの作成・読込やprocessへの配置は別承認とする。
  BridgeはGoogle file参照だけを返し、本文は既存bounded transportのbridge/auth検査後に読む。
  Shopeeは既存readerで実shopを照合しlegacy tokenを捨てる。cacheはservice別で、Keepa→Bridge／逆順でも分離する。
  未承認serviceはcache利用前にも拒否。OpenAI／Attributeの初回未使用境界を維持する。
- `P5Checkpoint`はoutput／session-end／承認済み資料更新を既存backupへ接続する。
  hook欠落・backup失敗はledgerの停止を保存し、運用bytesを返さない。予約・claim・UNKNOWN・履歴を削除しない。

合成HTTPと実SDKによるcold strict 1page=50のtraceはtoken→seed Product→query→候補Productの4send、
要求商品延べ51、最大予約0＋1＋11＋100＝112 token。cache再表示は0send、別clientも同じ有限ledgerを使う。
これは実消費の保証や最終承認予算ではない。Category／BrandとKeepa `/token`個別仕様の
PRIMARY_SOURCE_UNVERIFIEDを維持し、実source・今回query／leaf／全shop資料・参照・設置・実行承認をlive前に結合する。
Windows callbackの合成検証は実ACL／volume／probe／listenerの実証ではない。


### 新規P5設置と再起動の結合（DEC-0151）

- 新規設置templateの`store_id`は`None`で未結合を明示する。`P5Setup.install()`は
  他のscope項目を完全検証し、仮ID・既存store IDは作成前に拒否する。排他作成後の実store IDで
  通常のscope検証を行ってからcache／claim／ledgerを作る。未結合templateはruntime／ledgerへ渡せない。
- 新規scopeだけが`p5-profile-v1:`付きexecution targetを明示選択する。
  trusted installerは`p5_windows.plan_execution_target()`へ実operator SID、固定interpreter、
  固定releaseの`app_beta.py`絶対path、承認portを渡す。Host観測はmachine identityと現在SIDの
  読み取りに加え、現在PythonのOS実体pathだけを観測する。承認interpreter内から計画し、
  listener／App起動・store作成・credential／APIを必要としない。
- profileはmachine／SID／正規化したvenv入口・OSのPython実体・entrypoint path／portに結合する。
  Windowsのvenv入口とOS imageの差を混同せず、実観測で両方のpathを再照合する。
  PIDや開始時刻を永続scopeへ入れないため、同じscope／store／claim／ledgerを別processで再開できる。
  scopeの他の項目・digest方式、旧process target方式は変更せず、既存台帳を変換しない。
- 各startとsend／出力では従来の実PID、開始時刻、SID、実コード、listener所有とloopbackを検査する。
  実PID／開始時刻は観測全体とOwner reviewのdigestに残る。旧processのreviewを次processへ再利用できない。
  原Owner指示が認める再開でも、trusted operatorは現在process観測を原指示・現在票へ再結合する。
  scope／操作／予算／期限等が変わる場合は既存の別承認境界を適用し、設定から許可を生成しない。
- `plan_execution_target()`で作った値は設置前の実観測へ結合する。仮PID・fixture・架空Categoryで埋めない。
  既設の旧形式をprefixへ書換える、claim／ledger再初期化、予算復活、自動migrationは行わない。
  UNKNOWN、lease、履歴、選択と資料世代、backup／隔離復旧、Safety／PH・SG保護は従来どおり。
- 合成の別Python processによる再開テストとread-only Host観測は、実App／実設置／実APIの受入ではない。
  候補コードのformal採用・固定release反映・新規設置・実行はそれぞれの別承認境界に残る。

## 操作別preflight（DEC-0148）

`P5TrustedAdapter`は原承認の明示allowlistから必要資料を決め、同じ操作集合を
`P5ExecutionPermit.operations`へ固定する。開始・各操作・物理送信・保存・出力で再照合する。
未使用資料をverifiedへ変換せず、未確認値はそのまま承認観測へ結合する。

| 承認操作 | 必要な検査・関連操作 |
|---|---|
| `shopee.category` | Category公式本文・版・App/shop権限・全件/paging・request/response・rate limit。Shopee、Bridge、authの個別承認と正の有限枠 |
| `shopee.brand` | Category＋Brand公式資料、今回sessionのCategory取得binding・対象leaf、strict終端取得（最大10ページ）。Bridge/authを含む個別枠 |
| `keepa.token/product/query` | 必要な操作だけ承認。Product/queryにはtoken承認も必要。承認ASIN／strict検索条件・JP・認証・requests／商品数／tokensと残高を送信前検査 |
| `openai` | 現在価格のverified/reference/body digest、承認model・入力／出力bound・requests／USD。必要なkeyがなければclient生成前停止 |
| `image` | OpenAI承認とその価格・費用枠も必要。画像GETは独立枠、既存selector・画像Safetyを維持 |
| `p2.save` / `output` | Category＋Brand公式資料、現在の商品Fact・Safety・重複照合・分類・作業状態・保存／出力許可。出力にはP2保存の承認も必要。通信操作の許可は自動追加しない |
| `material.update` | Keepa Product/tokenとP2保存の承認。固定selection・更新journal・世代・同じ累積ledgerを検査 |
| `shopee.attribute` | productionではadapter／runtime／transport境界で拒否。synthetic検証だけに限定 |

未使用サービスのrequests／商品数／tokens／USD枠は0、対応操作はallowlist外とする。
Category限定でもBridge/authを0にして通すことはできない。余り枠は未承認操作を許可しない。
OpenAI未使用時は価格検証を要求せず、Keepa/OpenAIだけの操作はShopee/Googleのcredential本文を読まない。
Keepaは上記の明示service参照を実装済みだが、今回の実参照recordと利用承認は別に結合する。
OpenAI keyのproduction参照は未接続で、必要時は停止し、Shopee resolverへfallbackしない。
取得限定scopeでは起動・catalog更新時にP2再評価を書き込まず履歴を読むだけとし、保存・pool・出力の権限を迂回しない。
旧直接注入permitの3資料契約は互換維持するが、production Attribute送信は禁止する。

### leaf未確定時のCategory取得専用scope

DEC-0154。leafを知るための取得に、取得済みleafを先に要求しない。新規の`category_ids=()`は
Category全件取得だけに限定する。明示operationsは`shopee.category`・`bridge`・`auth`の3つだけ、
各物理send枠は1。Keepa・画像・OpenAIの全枠とmodel指定は0／空、Finder query・Resolver入力・
preparation_limitも空／0とする。既指定ASINのbindingは保つが商品取得の許可にはしない。
他の空scope、操作追加、legacyの全操作permitは拒否する。通常の商品準備scopeのleaf必須条件は維持する。

設置は従来の別承認・排他作成・ACL／probe・作成後の実store ID・claim／ledger検証を使う。
取得専用では商品探索と資料更新journalを初期化せず、設定だけではpermit・credential・通信を作らない。
原Owner承認、Category一次仕様／App・shop権限／rate等、実コード・起動観測・サービス別参照、
送信前予約、失敗／UNKNOWN停止とcheckpointの検査を省略しない。

専用画面は明示した1回の取得と検証済み一覧のleaf表示だけを扱い、商品探索・Brand・準備出力へ接続しない。
初期表示／再描画は0送信、予約後は再実行buttonを閉じる。合成応答は合成と表示し、公式根拠に昇格しない。
取得後もscopeのleaf追加・claim／ledgerの書換えによる商品準備への転用は不可。
後続の商品準備は用途・現在資料・完全scope・別承認を結合し、先行取得の予約／消費を累積上限へ含める。
新sessionの公式receiptや未使用枠として先行scopeを再利用せず、既存データ・予約・履歴を保持する。
コード採用・offline成立は、実設置・実API・実商品受入の許可／成功ではない。

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
実承認source・現在観測・Windows設置検査の実環境への結合は別に必要であり、
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
350 tokens、USD 1、Shopee 63 requests/市場は未承認の提案値。実行許可へ自動採用しない。

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
NOT_FETCHEDだけでは準備停止を追加しない。取得開始後のFAILEDは停止し、NOT_FETCHEDへ戻して通さない。
初回Betaの商品準備に自動属性取得を必須化せず、使用操作に必要な一次資料がPRIMARY_SOURCE_UNVERIFIEDならliveを停止する。現releaseのtrusted production組成は`shopee.attribute`操作を明示拒否し、
自己申告のverified値でも有効化しない。Category/Brandの公式根拠・P5運用許可・Safety停止も維持する。

P5出力はP1の現在Safety/重複/分類/公式BrandとSG正式運用gateを通す。
P2 `BetaWorkBench.output(operational=True)`はP1出力後、commit前、commit後のbytes返却前に
実運用許可も再確認する。保存前にbytesを返さず、返却直前の失効では保存済み投入予約を保持する。
downloadと外部投入を分け、UNKNOWNのlock・5状態は既存P2のまま扱う。
Expansion Toolで商品群を確認しASINを手動で既存出品ツールへ渡し、必須属性取得・属性値選択・一括API出品はそちらで行う。
`listing_ready=TRUE`は準備対象の表示で、外部ツールで無条件に一括出品してよい許可ではない。
同じCategory/Brandでも属性値一致・適用可否は保証しない。ユーザーが商品ごとに確認し、出品完了を別に記録する。
属性の自動推定・入力・DB保存、ツール間自動連携、出品ツール改修、実出品は提供しない。CSV列契約は維持する。
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
現行公式の全件取得・paging・権限・制限が確認済みとはしない。permit注入前に上表の承認操作が必要とする一次資料を確認する。
OpenAIの価格表は既存計算表を使う。paid送信は別途現在価格の確認参照を要求し、価格差があれば再見積り・最小修正する。
対象shop/ASIN/leaf、認証参照、専用保存先/権限/backup/復旧、観測release/実行対象、有限枠、
実API操作のOwner明示承認が揃うまでliveへ進まない。

実出品0件でも準備・再起動・追加・出力・既存正当出品CSV照合は検証できる。
投入成功等はfixtureと実際の結果を別記し、実行していない商品に実SUCCESSを記録しない。
A01〜A07、C01〜C12、F08 live、Owner受入を個別採点する。

rollbackはP5入口と対象processを停止し、必要なら通常revertで戻す。既存運用releaseを自動変更せず、
P2履歴・投入予約・消費ledger/claimを保持する。merge・設置・live・実務Beta完成は別のOwner判断とする。
