# CURRENT WORK

本書はformal mainで成立する状態と次工程の再開案内。長寿命の承認済み状態は
`governance/state.json`、branch / HEAD / PR / checksはGit / GitHub、
タスク固有状態はrepo外Task Context、実行結果はGit外Evidenceを参照する。

## 現在の正式状態と次の独立工程

PH・SGの共通初版は[実務Beta完成条件・差分監査](PRACTICAL_BETA_COMPLETION.md)で判断する（DEC-0137）。
共通入口だけでなく、両国の通常操作、限定自動確定、長期保存・準備pool・5状態、反復実商品受入を必要とする。
既存PH成果・SG Step 8の受入履歴は保護する。SG専用offline機能は両市場の実務完成を意味しない。
P1の[共通準備有効性・市場分離](PREPARATION_VALIDITY_P1.md)は、既存validatorを使う共通契約とPH／SGのoffline出力回帰を整備した（DEC-0139）。
根拠未搬送・旧確認フラグだけの通常出力は停止し、実商品証明を完成済みとしない。
P2の[共通長期保存・作業状態](PERSISTENCE_P2.md)は、市場／shop別の新規DB・履歴・準備pool・5状態・
永続投入予約をoffline backendとして整備した（DEC-0140）。再開時は過去判断を履歴として保持し、
新しいP1 sessionの現在根拠と明示確認なしに準備許可を復元しない。実運用DBを移行しない。
P3の[分類操作・現在根拠搬送](CLASSIFICATION_P3.md)は、共通HUMAN確認・限定offline AUTO_RULE・
revision付き任意部分集合をP1／P2へ接続した（DEC-0141）。通常アプリのMapperタブに新規保存先を明示し、
両市場のoffline接続を検証する。個別ruleの実運用許可は注入せず、模擬一覧を公式receiptへ昇格しない。
P4の[共通日常操作](PRACTICAL_UI_P4.md)は、新規P2保存先を明示した同じ統一アプリで、
確認待ち・分類・準備pool・offline CSV／TXT・5状態・永続予約と復旧・履歴を操作する（DEC-0142）。
既存PH／SG稼働経路を置き換えず、模擬資料の実運用昇格と未承認AUTO_RULE出力を拒否する。
[Amazon価格帯・平均評価](CANDIDATE_PRICE_RATING_FILTERS.md)のF1/F2は、両入口・両市場で同じ取得後判定と通常操作を使うoffline実装を整備した（DEC-0143）。
固定15列CandidateとSafety結合を保ち、旧cache・販売なし・不正値・期限切れを未確認として区別する。
条件変更だけではAPIを呼ばず、不足情報の補完は件数と追加token概算を示す別操作とする。
[P5最小接続](P5_CONNECTION.md)は、既存部品を使う専用runtime・送信前永続予約・
今回の公式資料搬送・P1/P2実運用出力契約をoffline接続として整備した（DEC-0144）。
設定から実行許可を生成せず、P4の模擬経路を実運用へ昇格しない。
P5の[二段階の探索・対象固定](P5_CONNECTION.md)は、承認済みFinder strict 1ページとResolver入力から
人間が明示した準備対象を同じscope・ledgerのままSafety／分類／P2保存へ渡すoffline接続とする（DEC-0145）。
選択・出所・同一性・累積予算を保存し、未選択・資料変更・Safety停止から分類確定／準備へ進めない。
旧formatの再開は固定資料の再搬送と現在根拠の再確認に限る。
[trusted組成・商品資料更新・D保存契約](P5_LIVE_DESIGN.md)の最小offline接続を整備した（DEC-0146）。
固定selection・ASIN・累積消費・履歴を保持し、更新開始の失効とledger/P2世代整合を要求する。
資料世代は新規設置時だけ導入し、旧scope digest・旧ledgerの資料変更停止を維持する。
T01〜T08はPH/SG合成検証で扱い、実原承認source・Windows実設置の成功へ昇格しない。
P5内の[production参照接続](P5_CONNECTION.md)は、実行中checkout/entrypointの観測、承認済み参照からの
Shopee credential遅延読込、実shop照合、Bridge/auth個別予約と追加OAuth送信拒否をoffline整備した（DEC-0147）。
原承認sourceの実record、実参照record、実設置との結合は別承認を要する。
P5の[production組成](P5_CONNECTION.md)は、trusted operatorによる原文／現在票の再照合、
Windowsのprocess／port／保存観測、Keepaの明示参照・service別遅延解決、app_betaの明示startと
既存checkpointをoffline部品として接続する（DEC-0149）。
設定だけではpermitを発行せず、未登録operator・未結合原承認では通常起動を停止する。
未作成先の事前検査とACL適用後の完全検査を分離し、hook／backup失敗では出力を止め予約・UNKNOWN・履歴を保持する。
実設置・実secret利用・実API成功の証明ではなく、OpenAI keyのproduction参照は未接続。
P5のtrusted process起動接続は、既存の型付き部品からoperatorを登録し、同processで
正規`app_beta.py`を起動する最小initializerを備える（[接続契約](P5_CONNECTION.md)）。
initializer自体の実コード検査を含め、未登録・原承認／票／対象不一致は停止する。
合成AppTestの成立を実原承認source・Windows実設置・live成功へ昇格しない。
Attribute自動取得を商品準備の必須前提にしない方針とし、NOT_FETCHEDだけでは追加停止しない。
FAILED停止・FETCHED空の未推定・Seller Center最終確認を維持し、production Attribute操作は拒否する。
この方針でPRIMARY_SOURCE_UNVERIFIED、P5運用許可、Category/Brand公式根拠・Safety停止を解除しない。
P5の[操作別preflight](P5_CONNECTION.md)は、承認allowlistに応じた必要一次資料・料金・有限枠をoffline検証する（DEC-0148）。
Category限定はCategory、Brand取得と保存／準備出力はCategory＋Brandの現在根拠を要求する。
未使用Attribute資料と未使用OpenAI価格を必須にせず、対応枠0・未承認操作の送信前拒否を維持する。
関連Shopee／Bridge／OAuth枠、原承認・実コード・保存identity・Safety・UNKNOWN停止は省略しない。
準備CSV／TXTのTRUEは外部一括出品の無条件許可ではない。ASINを手動で既存出品ツールへ渡し、
同Category／Brandでも商品ごとの属性値・適用可否はユーザーが確認する。属性自動入力・DB追加・ツール間自動連携は行わない。
取得限定scopeの起動・再描画は0送信・認証本文未読のまま。production Attributeはruntime／transportでも拒否する。
C04限定AUTO_RULE、F08 live、C12と実務Beta全体の完成はoffline成立へ読み替えない。
D採用は専用ACL・非重複・実設置検証・backupを条件とし、合成検査を実端末成功へ昇格しない。
次の単一作業は使用一次仕様と非公開実行票の未結合を揃え、trusted operator実登録・固定release・
保存範囲／ACL／容量／backupと停止方法を含む最小設置票を固定すること。
P5設置着手時は、Owner管理元の正式Trust Anchorを指定経路から再解決し、現行formal Governanceで新Task Contextに対するValidate／snapshot／fresh VerifyがCONTINUEすることを前提とする。
対象・一次資料・保存先・release・有限枠が固定され、設置と実行へのOwner別承認が成立するまで、
実API・実商品反復受入は開始しない。
Owner指定済みのshop・商品候補・既出品状況は非公開票で保持し、最新資料・SHA・今回scopeとの
実行Evidence結合を別に確認する。指定の回収を実行承認にせず、未結合をoffline実装の停止理由にしない。
F08の実AMAZON円・評価・tokensConsumed照合を含め、offline成功を実務Beta全体の完成としない。
[実商品受入・Owner判断資料](PH_SG_BETA_ACCEPTANCE_PLAN.md)は旧SG少量2商品群計画を維持する。
[P5実施設計・承認票](P5_ACCEPTANCE_EXECUTION_PLAN.md)でshop・商品・再取得予算・保存先・release・接続差分を固定する。
未指定の実対象や未成立のlive接続を推測で補わず、実行承認と実務Beta完成判断を分離する。
[Amazon価格帯・平均評価](CANDIDATE_PRICE_RATING_FILTERS.md)のF1/F2はOwner判断によりBeta前MUST。
P1〜P4とF1/F2のoffline成果を保護し、両市場の実商品・実画面・費用・公式Brand・再取得条件をP5で受け入れる。
live API、費用、認証・保存先設置、固定release変更、実出品は別承認。MY税務確認・関税計算はここで実装しない。

Home Appliances分類補助は保存済みファイルを入力する独立CLIとして扱う（DEC-0136）。
候補A／B／C・理由・根拠・不足情報・出所を専用BOM付きCSVへ出し、既存Safety Shadow V3と分離する。
[入力・使い方・限界](HOME_APPLIANCES_CLASSIFIER.md)を参照する。
既知研究商品の再評価は未知商品の分類精度を保証しない。
この補助ツールの次の独立工程は、未知商品による限定実務評価の必要性と対象を別scopeで判断すること。
Expansion／Gate／Mapper接続、正式な出品判断、他カテゴリ・GUI・DB・API拡張、稼働反映は含めない。
SG Betaの下記実務受入・環境反映工程を置き換えない。

SG初期Beta Ver1.0の追加機能は、[offline作業画面・保存契約](SG_INITIAL_BETA_V1.md)を参照する（DEC-0135）。
限定AUTO_RULE、項目別Fact出所、長期作業DB、確認待ち・5状態・一括出力をoffline専用入口で扱う。
この入口は模擬catalogを明示し、既存通常SG／PHの確認契約・API枠・DB・稼働releaseを置き換えない。
SG 100578の対象実商品自身のJP証明と公式Brandのlive完全性／更新条件は未受入のままP5へ引き継ぐ。
P1では未証明の資料を推測で通さず停止する契約を整備した。
具体的ruleの実運用適用、live API、保存先設置、release反映・実出品は別承認とする。
旧SG通常継続利用の少量実務受入はP5と整合させ、このoffline成果で完了扱いにしない。

SG通常継続利用はDEC-0134の有限Policy＋画面商品群受付を使う。
同じ統一アプリで全SG ELIGIBLEを読み、今回のCategory／Brand／必要Safety確認を満たした商品だけCSV／TXTへ出す。
新商品群・資料変更では過去確認とcheckboxを失効し、保存Categoryは再確認候補として使用する。
商品群ごとのCodex設定・新Grant・新DBは不要。旧限定方式と旧DB／ledger／claimは保持する。
通常継続API枠は送信前に永続計上し、Keepaも自動retryなしの有限送信枠で保護する。
[操作・設定・制約](SG_CONTINUOUS_OPERATION.md)を参照する。
固定release反映・新しい有限API枠／保存先・少量2商品群の実務受入は、共通P1〜P4を整えてP5で別承認を得る。
コード採用を8503反映・実API・実商品受入へ読み替えず、MY／THへ自動拡張しない。
以下の旧少量・offline成果は適用modeと受入履歴を区別して参照する。

正本化連鎖防止ルールを採用済み（DEC-0114）。Git管理文書の現在状態をmerge後にも正しい形で
同一PRへ含め、post-merge確認成功後はTask ContextをCLOSEDにして終了する。
詳細手順はRUNBOOK「Post-Merge Stability」を適用する。

SG Minimum Beta完成判定（Roadmap Step 8）は正式採用済みでCLOSED。
半自動完成線はDEC-0111 / DEC-0112、Step 8終了はDEC-0113を参照する。
Step 8受入時点では新規Beta MUST実装の残作業はなかった。後から確認したSG本体商品の停止漏れは
下記DEC-0129の独立した事故防止対応として扱い、Step 8の受入履歴を書き換えない。
Shared Battery v0.2はv0.1の11語に限定5表現を加えた16語でPH／SGの疑義をREVIEWへ止める（DEC-0133）。
商品文章の既存搬送・Guardrail・Gate・準備出力の再評価を共用し、BLOCKを降格させない。
検出はBattery搭載確定ではなく、未検出・Product Text欠落をBattery不存在の根拠にしない。
過去のPH／SG正式受入を無効化せず、稼働release更新は別承認とする。
Batteryの既知の後続確認は、少量実利用で増えたREVIEWの妥当性・手間の評価。
追加APIやBattery自動確定、無条件の人間解除へ自動拡張しない。

DEC-0116の固定PH基準は既存機能の回帰基準として保持し、新しい実務完成判断はDEC-0137を適用する。
共通moduleを改善し、市場別の判断材料とadapterを分離する。
旧限定modeのSG実運用（Roadmap Step 9）は専用の少量ベータ環境を対象とする（DEC-0127）。
SG ACTIVE化とPH形式の手動準備出力を採用し、固定release・専用保存先・承認枠で起動する。
端末の設置・最新API利用枠・実行確認はrepo外Task Context / Git外Evidenceを参照する。
PH / SGは[統一ベータ入口](BETA_APPLICATION.md)で対象国を切り替え、同じ4工程を使う（DEC-0128）。
共通入口は既存PHの保存先とSG専用DB / API枠を参照し、国別の確認・消費を混ぜない。
端末設置の状態はrepo外Task Context / Git外Evidenceを参照する。
SGのコンタクトレンズ本体・実同梱品と、一般台所用包丁本体・実同梱品の販売除外方針を採用する（DEC-0129）。
レンズは公式根拠による除外、包丁は現行Shopee条件との対応が未解決なため当社独自の暫定除外である。
SGの対象名称・指定済み商品文章から本体疑義を止め、明示した本体・実同梱の確認結果をGate EXCLUDEへ反映する。
確認記録は市場・ASIN・Candidate全15項目と商品文章・versionへ結び付け、保存・再開と再実行に用いる（DEC-0130）。
付属品確認は今回追加する疑義だけを解消し、既存BLOCK／REVIEWを維持する。
SGの準備CSV／TXT出力でも、古いELIGIBLE入力と商品文章変更による確認流用を停止する。
操作と既知制約は[SG本体確認](SG_BODY_SAFETY.md)を参照する。未検出の商品全体の安全保証ではない。
コード採用と稼働端末の固定release更新・実商品受入を区別し、端末設定・DB・API消費記録を自動変更しない。
Shadow V3は通常Gate判定後の任意の読取専用比較に限る（DEC-0131）。
一致する保存Factを現在のCandidate・市場・商品文章へ照合して分類候補と根拠を表示し、
Safety処分・SG本体確認・出力CSVは変更しない。[接続条件と制約](SAFETY_SHADOW_COMPARISON.md)を参照する。
Shadowの既知の後続確認は比較表示の実用性と比較不能事例の評価。Keepa保存・搬送改善やSafety処分変更へ自動移行しない。
統一ベータのExpansion→Gateは、既存4資料をsession内で一式引継ぎする（DEC-0132）。
全ショップ分の既出品CSV、PH画像Safety、SG本体確認と既存判定・出力を維持し、外部CSVの手動入力も残す。
同一Candidate・商品Factの確認は既存validatorで照合し、入力元・filenameだけでSG本体EXCLUDEを解除しない。
操作・失効・制約は[内部引継ぎ](EXPANSION_GATE_HANDOFF.md)を参照する。
入力簡素化の既知の後続確認は、少量実商品で搬送省力化の利用価値を評価すること。
稼働環境更新・実商品・API利用は別の明示承認を要し、Resolver／Mapper内部接続へ自動拡張しない。
未採用のShadow／Keepa／分類接続成果を、この方針の採用によって正式成果へ昇格しない。
MY／TW／THの市場runtime開始はPH・SG共通実務Beta受入後に別scopeで判断する。
過去の固定基準は[PH Beta市場展開](PH_BETA_MARKET_PARITY.md)、新しい完成基準・順序はDEC-0137の完成条件を参照する。

## 成立済み成果と保護境界

以下の旧隔離／offline入口と少量Grantの契約は、その方式の履歴・保護境界として保持する。
通常継続modeの確認再利用・受付・出力にはDEC-0134を適用し、旧方式の制限を重ねない。

- 通常PH画面内のPH / SG Category Mapperは共通の市場選択入口と確認手順を使用する（DEC-0115）。
  Category検索・採用の表記を揃え、PHのグループ確認とSGの商品単位確認を維持する。
  SGのAI候補・Brand確認結果保存・CSV / TXT出力は未提供として表示し、機能を有効化しない。
- PHはACTIVE / ALLOWED、SGはACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTED。
  `ph.beta.operation`と`sg.safety.baseline`はACCEPTED。
- SG production Category source確認、catalog import offline成果、6実商品の人間Category確認・
  保存・再利用・current ID / path / leaf再validationは正式採用済み（DEC-0093 / DEC-0098 / DEC-0103）。
  6件は同一brandの異なる用途の保護ケース標本であり、広い商品群の精度保証ではない。
- SG Brand / No Brandのoffline最小実装は正式採用済み（DEC-0104 / DEC-0105）。
  商品単位No Brand保存、strict完全取得、current再validationを維持する。
  No Brand tableは隔離acceptance DBへの明示初期化だけで、production schemaへ適用していない。
  共通Brand検索と隔離offlineのSG確認画面部品を用い、商品単位の明示選択・保存・current再検証を行う。
  SG strict BrandはAPIの表示名`No brand`と元名`NoBrand`を同じ区分として検証する（DEC-0121）。
  IDから区分を推定せず、実ID・名前を保存し、商品単位の人間確認と曖昧な名前の停止を維持する。
  隔離live Brand取得は対象Categoryを明示した承認枠で最大50ページまで指定できる（DEC-0122）。
  通常 / offlineの10ページ上限を維持し、同じ枠内の再取得・失敗もページ予算へ計上する。
  通常SG画面には接続せず、production API・DB初期化は画面部品から実行しない。
  明示注入したoffline client / engineで、CSV読込・Category人間採用・Brand取得・保存まで接続する。
  AI結果表示はPH / SG共通とし、候補だけで確定しない。通常経路のlive AI閉鎖を維持する。
  隔離画面は同じKeepa Category / Brandの商品をまとめて表示し、全商品の明示確認後に
  CategoryをASINごとに一括保存する。途中失敗は全件rollbackし、Brandは別に確認する。
  SG必須属性はoffline clientから明示取得してsession内へ保持し、通常DB schemaを変更しない。
  開発用確認状況CSVは出力直前に再検証し、全件listing_ready=FALSEとする。出品用CSV / TXTではない。
  説明FactはSG既存RuleとShared Batteryの自動判定へ渡し、既存BLOCK / REVIEWを解除しない。
  説明・画像が商品に合うかを全商品で人間確認する追加機能は削除する（DEC-0125）。
  Category / Brand / SLS ALLOW候補と対象商品の武器画像検査が成立した商品を開発用準備候補CSV / TXTへ出す。
  これらもlisting_ready=FALSEであり、通常環境の出口は開かない。PH画像AI処理と対象条件の挙動を維持する。
  CSV / TXTの組立はPHと共通化し、market・Category ID・Brand IDごとのグループとASIN一覧を出力する。
  SG必須属性の未取得と取得済み0件を区別し、PHの既存出力形式と準備完了条件を維持する。
  元CandidateとSHA結合済み説明・未評価画像sidecarを隔離画面で読込できる。
  SG eligible商品情報との一致を検証し、PH評価・人間判断を流用しない。資料変更・削除・失敗は再確認を要する。
  ファイル対応確認はアップロードの真正性やGate判定の暗号学的由来を証明しない。
  画像疑義確認は共通adapterでPHの画像取得・AI問い合わせを再利用し、隔離SG画面へoffline transportを
  明示注入した場合だけ商品単位に実行できる。PHの評価・人間判断はコピーしない。
  対象選択は共通module＋国別設定とし、PH / SGは現行PHの4 rootとroot不明を対象にする（DEC-0123）。
  その他rootは画像AI対象外・未実行で、人間の画像確認も要求しない。
  MY / THは同じ初期設定と共通selectorを準備し、実運用接続は後続工程とする。
  武器画像検査が完了・NO_SIGNALなら追加の人間判断を要求しない。疑義あり・判断不能だけ人間判断を行う。
  一部画像失敗は判断不能とし、再実行で古い武器画像の判断を失効させる。
  認証・契約等の全体失敗は準備候補を停止し、成功した明示再実行で現在の武器検査結果を使用する。
  隔離SG開発版の入口・起動script・合成確認資料を用意し、Category AI候補からBrand・属性・
  商品資料・画像の一括確認とCSV / TXT出力までを接続する（DEC-0117）。
  開発用画像対象は現在SAFE / SG eligibleのKeepa資料から国別root設定で選ぶ。
  新規隔離DBだけを初期化し、通常DB・credential・実API・通常の起動先を使用しない。
  再生資料の変更・削除・再初期化は確認と画面のチェックを破棄する。
  [確認手順](SG_LOCAL_REVIEW_GUIDE.md)を参照する。再生検証はSG live接続・正式出口採用の代替ではない。
  隔離V2候補探索では選択した大分類の専用末端全件をbatch比較し、該当なしなら関連する別分類も探索する。
  商品理解と探索完了が成立した場合だけ、適切な親pathを持つOthersを候補にする（DEC-0120）。
  探索上限・取得失敗・商品不明は保留または失敗とし、人間確認を自動生成しない。
  V1再生資料・PHの通常AI動作は維持し、V2は明示選択した隔離資料 / CLIだけで使用する。
  別の明示CLIで最大3商品の隔離実接続検証を行う部品を用意する（DEC-0118）。
  既存Access Token Sourceを再利用し、OpenAI予約上限1米ドルとSG / shop / 商品 / 隔離DB結合を維持する。
  別起動のSG開発画面は、承認済み枠を明示指定した場合だけread-only実接続へ接続できる（DEC-0124）。
  既存Bridgeから操作ごとに最新tokenを取得し、商品・shop・Category・取得上限・費用枠を維持する。
  消費記録を送信前に保存し、再起動でも復元する。同時起動・記録欠落・設定変更は停止する。
  再生modeを既定とし、初期化・再描画ではAPIを呼ばない。最新catalog取得失敗は準備候補を閉じる。
  商品ごとの準備確認・不足手順を表示し、正式出口を開かず開発用CSV / TXTを検証できる。
  SGベータ採用候補は別入口とPH形式の準備CSV / TXTを実装する（DEC-0126）。
  正式StateのSG ACTIVEを毎回確認し、専用環境だけで利用する（DEC-0127）。通常PH環境は変更しない。
  [準備出力](SG_BETA_RELEASE.md)と[MY / TH資料の準備状況](MY_TH_GUARDRAIL_READINESS.md)を参照する。
  通常画面は有効化せず、接続結果から人間確認を自動生成しない。実接続の結果と認証上の未解決事項は
  repo外Task Context / Git外Evidenceを参照する。部品実装は一連実用確認の完了を意味しない。
  SG自動同期はPHの既存処理を保つ追加ファイルと別SG Bridgeへ分離する設計とする（DEC-0119）。
  共通Sourceの全行検証によるPHへの影響を避け、SG expected shopを元表・Bridgeへ照合する。
  [反映手順](../integrations/google_apps_script/ph_access_token_bridge/SG_ACTIVATION.md)を参照する。
  local候補とGoogle側反映・同期受入は別であり、稼働結果はrepo外Task Contextを参照する。
- SG SLSのoffline最小runtimeは正式採用済み（DEC-0108 / DEC-0109）。
  SLS ALLOW候補はCategory条件の成立に限り、商品全体のSafety保証ではない。
- Owner Acceptance方式Bは正式採用済み（DEC-0106 / DEC-0107）。
  Ownerの技術値手動コピーは不要だが、現在対象への明示的最終承認とfresh Evidence・formal Verifyは必須。
  GitHubコメントは承認後のbinding搬送であり、人間のUI手入力を独立証明しない。

## 既知制約・停止条件

Step 8で採用した完成線は、少量商品ごとのSG Gate `ELIGIBLE`、
人間Category・Brand / No Brand確認、SLS `ALLOW`候補、Seller Center必須Attribute・
商品固有発送条件確認を経た手動出品である。未解決BLOCK / REVIEW / EXCLUDE / UNCHECKED /
UNAVAILABLE、Category / Brand未確認、Battery / 危険物 / 許認可等の未解決疑義があれば出品しない。
人間確認でSafety / Battery / SLS停止を解除しない。

旧`app.py`単独起動のSG出口と、既存SG Category確認objectの`listing_ready=false`を維持する。
専用SGベータの準備対象だけ、再validation後に`listing_ready=TRUE`の手動準備CSV / TXTを出す。
これはSeller Centerの出品完了・属性入力完了・商品全体の安全保証ではない。
Brand / No Brand・SLS live acceptanceとSeller Center E2Eは未実施。
production API / DB / schema、Bridge / credential変更、runtime切替、deploy、
専用環境の範囲を超える出口開放、自動確定・出品は別scope・別途明示承認を要する。
新しいAPI枠は具体的対象・取得数・費用の明示承認を要し、過去枠をリセットしない。
MY / THは画像対象設定・共通選択契約だけを準備する。市場runtime / Safety / 出品接続は未着手とする。未実施事項だけを新しいBeta MUSTへ昇格しない。

共通Catalog / Access Token Sourceの既存責務は維持する。Mapper側refreshは行わず、
Source明示ON時のsilent fallbackを許さない。Bridge全面書込み障害時の旧token無効化は保証しない。
SG Brand responseにmarketplace / Category echoがないため、server内部の別Category誤応答の独立検出は保証しない。

## Required Decisions

- DEC-0150 — Trust Anchorの明示解決、現在bindingを確認するfresh Verify、Owner Acceptanceのfresh限定。

- DEC-0149 — P5原承認再照合・Windows観測・Keepa service分離・明示start・checkpointのoffline組成と実設置／live境界。

- DEC-0148 — P5操作別の一次資料・料金・認証・有限枠、Attribute production禁止と手動属性確認の境界。

- DEC-0147 — P5 production参照接続のoffline差分、Attribute非必須方針とlive停止・原承認不足の維持。

- DEC-0146 — P5 trusted adapter・固定対象の商品資料世代更新・D新規保存、実装/設置/liveの別承認。

- DEC-0145 — P5探索前の有限条件と探索後の明示対象固定、Resolver同一性、同じledgerでの再開と資料変更停止。

- DEC-0144 — P5専用接続・有限予約・公式Category取得境界・P1/P2出力・HUMAN初回とlive別承認。

- DEC-0143 — F1/F2共通取得後判定・旧cacheの未確認・明示補完予算・15列／Safety結合・F08のoffline／live分離。

- DEC-0142 — P4共通画面・offline出力・5状態と予約復旧、取得世代・既存経路の保護。

- DEC-0141 — P3共通分類操作・通常根拠搬送・部分集合保存、限定AUTO_RULEの個別承認照合とP4境界。

- DEC-0140 — P2共通保存・市場／shop／schema分離、現在準備と投入進行の分離、永続予約とP3引継ぎ。

- DEC-0139 — P1共通検証、session失効、公式完全取得と通常根拠未搬送時停止、P2／P3引継ぎ。

- DEC-0138 — F1/F2のBeta前MUST、P1〜P4優先とP5前の完成、P1の境界。

- DEC-0137 — PH・SG共通の実務Beta完成条件、差分監査・最小順序、少量受入、価格／評価候補の採否境界。
- DEC-0136 — Home Appliances候補分類CLIの独立入力・出力、Fact出所、既知回帰と未知精度、後続接続の分離。

- DEC-0135 — SG初期Betaのoffline限定AUTO_RULE・Fact出所・長期保存・5状態、既存実務受入と実運用承認の分離。

- DEC-0134 — SG通常継続利用の有限承認、商品群受付・失効、既存保護、新旧方式と実務受入・rollback。

- DEC-0133 — Shared Battery v0.2の限定5表現、既存11語維持、汎用語非追加、REVIEWとSLSの責務分離。
- DEC-0132 — Expansion→Gateのsession内一式引継ぎ、既存検証共用、確認保持と失効、手動経路の維持。
- DEC-0131 — Shadow V3の任意の読取専用比較、商品Fact結合、不一致時の比較不能と既存Safety保護。
- DEC-0130 — SG本体確認記録のCandidate結合、既存Gate EXCLUDEと準備出力への最小接続。
- DEC-0129 — SGレンズの公式根拠による本体除外、一般台所用包丁の内部暫定除外、本体不明REVIEWと実装の受入境界。
- DEC-0044 / DEC-0052 — 確定禁止と具体的確認が可能なREVIEW、資料identityと現行性・Rule採用の分離。

- DEC-0128 — 1つのアプリ内でPH / SGを切り替え、既存の国別保存先・認証・API枠を維持。

- DEC-0127 — 採用済み固定コード・SG専用起動先・永続データとAPI枠で少量ベータを利用。

- DEC-0126 — SGベータ入口・手動出品準備出力の採用候補と正式採用前の閉鎖。

- DEC-0125 — 全商品の説明・画像の人間確認を削除し、画像用途を武器疑義へ限定。

- DEC-0124 — 明示承認枠と永続消費記録付きの隔離SG実接続画面・準備確認。

- DEC-0123 — 共通画像対象selectorと国別設定、PH / SG初期条件とMY / TH設計準備。

- DEC-0122 — Category指定・累積ページ上限付きの隔離Brand取得枠。
- DEC-0121 — SG APIのNo Brand表記差への対応とstrict検証・人間確認の維持。
- DEC-0120 — 専用末端全件比較・関連分類探索後の適切なOthers候補と隔離V2。
- DEC-0118 — 最大3商品・OpenAI上限1米ドルの隔離実接続と既存認証Source再利用。
- DEC-0119 — PH同期を維持する別SG Bridgeと、Google側反映の承認境界。
- DEC-0116 — 固定PH Beta基準のSG機能統一、共通module＋国別情報、後続MY / TH展開。
- DEC-0117 — SG隔離開発版の一連操作と、開発用画像対象・live採用の分離。
- DEC-0115 — PH / SGの共通操作入口と、SG未提供機能・起動環境調査の境界。
- DEC-0114 — 正本化連鎖防止、同一PRのmerge後安定性、Decision必要条件と終了責務。
- DEC-0111 / DEC-0112 / DEC-0113 — Step 8完成線・正式採用・CLOSED、Step 9別承認境界。
- DEC-0072 / DEC-0073 / DEC-0087 / DEC-0088 — Governance・formal承認・必須手順配置・Decision読込。
- DEC-0091 / DEC-0092 / DEC-0106 / DEC-0107 — Owner Evidence、freshness、限定移行と方式B。
- DEC-0071 / DEC-0075 / DEC-0076 / DEC-0077 — SG Safety・Shared Battery・SLS資産とPH runtime保護。
- DEC-0079 / DEC-0080 / DEC-0081 — SG商品単位Category確認、current再validation、live OpenAI閉鎖。
- DEC-0082 / DEC-0084 / DEC-0085 / DEC-0086 / DEC-0089 / DEC-0090 — 共通認証・Catalog責務と既知制約。
- DEC-0093 / DEC-0096 / DEC-0098 / DEC-0099 / DEC-0100 / DEC-0101 / DEC-0102 / DEC-0103 —
  source・import・実商品Category受入と過去STOPの置換範囲。
- DEC-0104 / DEC-0105 / DEC-0108 / DEC-0109 — Brand・SLS offline成果とlive・production別承認境界。
