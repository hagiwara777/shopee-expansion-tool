# P5 実務受入の実施設計・承認票

本書は[共通受入計画](PH_SG_BETA_ACCEPTANCE_PLAN.md)A01〜A07を実施可能な単位へ分けた提案である。
完成条件は[C01〜C12](PRACTICAL_BETA_COMPLETION.md)、価格・評価は[F08 live](CANDIDATE_PRICE_RATING_FILTERS.md)を適用する。
DEC-0137〜0143を変更せず、P1〜P4・F1/F2のoffline成果を保護する。
本書の作成・採用は実行許可ではない。実対象・保存先・release・予算を固定した承認票へのOwner明示承認が必要。
タスクの進捗・承認待ち・実測Git状態はrepo外Task Context、実行証拠はGit外に置く。
最小接続のoffline実装契約は[P5_CONNECTION](P5_CONNECTION.md)、DEC-0144を参照する。
接続コードが存在しても、本書の提案予算・実対象・live実行を承認したことにはならない。

## 1. 対象を固定する作業票

以下の未確定欄がある間は実行承認票を確定しない。架空ASIN、過去shop、旧取得枠で代用しない。
商品本文・実CSV・画像・個別shop対応表はGitへ入れず、非公開作業票に記録する。

| 項目 | PH | SG | 固定方法 |
|---|---|---|---|
| 対象shop | Owner指定待ち | Owner指定待ち | 識別名と実shop IDを非公開票へ。認証のexpected shopと照合 |
| 対象Category | 実leaf ID/path未確定、最大2 leaf案 | 実leaf ID/path未確定、最大2 leaf案 | 商品用途を先に確認し各市場の公式catalogで確定。他市場IDを転用しない |
| A：Expansion | seed未指定、準備2商品案（許容1〜3） | seed未指定、準備2商品案（許容1〜3） | seed＋strict 1ページから安全に準備可能な候補を選定 |
| B：Resolver | 英字title/source_id・実ASIN未指定、準備2商品案（許容1〜3） | 同左 | 正当なShopee由来title→手動Resolver結果→Keepa JP確認。AをBと名付け直さない |
| 既出品照合標本 | 既存の正当な出品ASINがあれば別枠1件 | 同左 | 最新全ショップCSVとの一致確認専用。新規準備poolへ二重投入しない |
| 全ショップ資料 | 全shop数・CSV所在・取得時刻未確定 | 同左 | 当該市場の全shop、対象shopを含む。0件も実態の確認を要する |
| 操作者／確認担当 | Owner指定待ち | Owner指定待ち | 同一人兼務可。Category・Brand・画像疑義の判断者を明記 |

準備対象は標準8商品（PH 4＋SG 4）、許容4〜12商品。API取得商品数・CSV行数・一意ASIN数・
実出品数を別々に記録する。新規実出品の計画値は0。
同一ASIN再登場・同Category/Brandの別商品・未確認商品の保留を含める。
危険物・Battery・刃物本体・コンタクトレンズ本体等を実出品試験に使わない。
候補例は電源のない収納用品・一般文具等だが、安全認定やCategory指定ではない。
画像対象rootを見積のために改変せず、対象なら必要画像検査を省略しない。

実ASINごとの非公開票の必須列：
`market / shop_ref / group / seed_or_source_id / ASIN / identity_evidence_ref / selection_reason /
proposed_leaf / official_leaf / brand_option / image_root / image_count / safety_pending /
candidate_sha / product_text_sha / inventory_manifest_ref / operator / reviewer`。
Aの派生ASINは検索前には確定できないため、「承認seed・検索条件・最大50詳細」を先に固定し、
返却後の準備対象1〜3件を人間が確定する二段階とする。対象外商品へ後工程のAPIを広げない。
BのASINが未確定なら、Resolver候補作成までの操作と確認済みASINへの詳細取得を分ける。
候補発見の枠は実出品の許可ではない。

## 2. 入力資料と証拠

| 資料 | 必須条件・保存する根拠 |
|---|---|
| Candidate／商品自身のJP Fact | 固定15列、provider・domain=5・ASIN・取得時刻・項目別出所。seed/旧cacheの不明出所をOWN_PRODUCTにしない |
| 商品文章・成分Safety | 現行sidecar、Candidate最終bytes SHA・ASIN集合と対応。文章未取得は不明のまま。原資料を変造しない |
| 対象画像 | 既存selector、画像URL参照・SHA・取得結果・model/prompt・疑義/人間判断binding。対象外/NO_SIGNALへ不要な人間確認を追加しない |
| 全ショップ既出品CSV | 市場別全shop一覧と各CSVの実shop対応、取得日時・SHA・件数・確認者。Parent SKU/SKUで照合。部分資料は停止 |
| Category | 当該市場・shopの公式取得、全raw行対normalized件数、ID/parent/path/leaf・循環・重複検査。SLS表をcatalog代用しない |
| Brand | 人間採用leafごとのstrict raw検査、offset=0から正常終端、今回sessionの公式receipt。旧JSONの自己申告不可 |
| 属性・発送条件 | 公式attribute treeの未取得と取得済み0件を区別。Seller Centerの必須属性・発送条件は人間確認 |
| Safety資産 | formal releaseのGuardrail/Battery/SLS/SG本体除外/画像selector版とdigest、必要な公式資料のmarket・版・取得日・参照箇所 |

実証用rootは非公開票で固定し、`PH/<run>/`と`SG/<run>/`へ分ける。
`inputs`（原資料）、`evidence`（結果・画面）、`exports`（CSV/TXT）、`backups`を分離する。
証拠indexはA番号/C番号/F08、market、shop参照、release、session、群、ASIN参照、資料SHA、
操作時刻（UTC＋JST）、操作者・確認者、期待値/実値、PASS/FAIL/NOT_RUN/BLOCKED、未達理由を持つ。
認証header・署名付きURL・key付きquery・token・raw exception・個人情報を記録しない。
スクリーンショットの認証欄を避ける。画像本体/base64は既存契約どおりメモリ内だけで扱い、保存を自動追加しない。
変造資料・障害注入は合成fixture専用にし、実データDBや原CSVを編集しない。
Chrome用操作ファイルは`Documents/ShopeeE2E`配下のみ。取得出力はGit外に保持する。

## 3. Keepaの有限計画案

公式仕様読取日：2026-10-16。これは実API照合ではない。
[Product Request](https://keepa.com/api-docs/product.html)は基本1 token/商品、Product stats追加0、rating追加最大1。
[Finder](https://keepa.com/api-docs/product-finder.html)は10＋結果100 ASINごと1 token。50件ページを保守的に11で予約する。
Product statsと有料Finder Search Insightsを区別し、Finder stats、offers、buybox、stock、強制updateを使わない。
ratingは既存値を返すもので強制鮮度更新ではない。現在画面との差は時刻差を含め記録する。

| 呼出し目的（各市場） | 許容量 | 商品基本token | F1追加 | F2追加上限 | 合計上限 |
|---|---:|---:|---:|---:|---:|
| A seed基本取得 | 1 ASIN・1回 | 1 | 0 | 0 | 1 |
| A Finder strict | 1ページ・最大50候補 | — | — | — | 11 |
| A候補詳細 | 最大50 ASIN・1 batch想定 | 50 | 0 | 50 | 100 |
| B選択詳細 | 最大3 ASIN・1 batch想定 | 3 | 0 | 3 | 6 |
| session再開・操作者再実施時の対象Fact再取得 | 最大6 ASIN×2回 | 12 | 0 | 12 | 24 |
| 旧cacheの明示補完 | 承認対象最大6 ASIN×1回 | 6 | 0 | 6 | 12 |
| 合計 | 取得延べ最大72商品、Finder別 | 72 | 0 | 71 | **154** |

PH 154＋SG 154＝**308 tokens**の計画最大。提案ハード上限は各市場175、合計350 tokens。
残り42は自動retry・検索追加の許可にしない。50候補全件の旧cache補完は100 tokens/市場となり、
上表の12を置換すると合計484 tokensになり350に収まらない。この場合は送信前に再見積・再承認。
cache hitによる節約は実測後に記録し、別対象への無断転用をしない。
再開時に現在根拠の明示再搬送だけで成立する部分は追加取得せず、上表の予約を消費済みにしない。
7日cache判定を削除・偽装してfresh取得を作らない。F08鮮度再取得が既存UIでできない場合は接続不足として停止する。

requestsは**最大20/市場、合計40**を独立上限案とする。
上表の課金操作は7 HTTP calls/市場を想定（seed1/query1/details1/B1/再取得2/補完1）。
加えて3 session分の`/token`事前確認最大3回を計画し、通常計画は最大10 sends/市場。
SDK初期化・残高確認・batch分割・失敗を含む全sendを計上する。想定外sendは残枠があっても停止し計画を改訂する。
条件適用/解除/再描画は0 calls。F1/F2指定中のfallback禁止を利用し、初回取得は評価4.0以上を暫定案とする。
条件なしの確認は取得済み値で行い、診断fallback最大3検索を今回の標準計画へ含めない。
再起動後とA07は既存A/Bの反復処理を基本とし、Finderの新規再検索は含めない。

送信前に市場別と全体のrequest/token予約を永続化し、応答消費を別列へ追記する。
残高不明・必要量不足・上限不足・429・timeout・不正応答は停止。自動回復待ち/再送/自動購入は0。
失敗/不明応答の予約を返却せず、再起動でも残枠を復元しない。他用途の同一API key利用は受入中停止をOwnerと調整する。
`tokensConsumed`を応答envelopeから取得できる経路が必要。`tokensLeft`差分だけではrefill/他処理が混じるため実消費としない。
該当field欠損時はF08消費実測を未成立とし、値を推定生成しない。追加診断APIも別承認。
Keepa契約購入・更新・金銭課金は提案枠に含めず、必要なら別見積とする。

## 4. OpenAI・画像取得の有限計画案

既存modelを維持する。Category候補は`gpt-5.6-luna`、武器画像疑義は`gpt-5.6-terra`。
公式[料金](https://developers.openai.com/api/docs/pricing)と
[Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)／
[Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra)を2026-10-16に確認：
100万tokensあたり入力/出力はLuna $0.20/$1.20、Terra $2/$12。cache割引を見積に使わず入力に1.25倍を予約する。
[画像仕様](https://developers.openai.com/api/docs/guides/images-vision)の最大30,000 patches×1.2に基づき36,000 tokens/画像を保守的に予約する。

| 処理 | 対象・最大calls（両市場合計） | 1 call入力上限 | 出力上限 | 予約最大USD |
|---|---|---:|---:|---:|
| Category AI候補 | 準備対象最大12商品、24 calls（各市場12） | 32,768 tokens相当（JSON UTF-8 bytes＋8192の保守bound） | 512 | 0.2113536 |
| 必要な武器画像 | 最大2商品評価calls（各市場1）、各最大3画像、計6画像 | text部8,192 bytes＋8192＋3×36,000＝124,384 | 1,200 | 0.65072 |
| 合計 | 最大26 calls | 長文/外部toolsなし | — | **0.8620736** |

初回費用上限案は**合計$1.00**、市場ごと$0.50。Ownerが最終上限を決定する。
画像2 callsは対象商品数でなく評価回数上限。再起動後の再評価も数える。3画像×4 callsなら画像だけで$1.30144となり枠不足。
対象が増える・同じ画像の再検査が必要・探索call数不足なら、人間確認で検査を迂回せず停止して再見積する。
画像非対象の商品を中心に選ぶが、F08やSafety受入の未実施部分を対象外成功へ置換しない。
Category AIは候補であり限定AUTO_RULEの証明ではない。探索打切りは保留、恣意的なOthers確定は禁止。
`store=false`、標準tier、stream=false、toolsなし。1 callごとの実payloadと上限を送信前照合し、超過入力を黙って切り捨てない。
既存画像transportの再送経路も送信単位で予約し、今回は自動retryを無効にできた場合だけ使用する。
取得画像は最大6 HTTP GET（allowlistホスト、既存byte/pixel上限、redirectなし）、失敗で追加取得しない。
画像取得をOpenAI request件数へ混ぜない。実usage/予約額/実請求確認を別欄に記録する。
Resolverの外部AIはAPIに自動接続しない。Ownerが使うサービス・既存契約内の手動送信も実行承認票へ記載し、未確定なら停止する。

## 5. Shopee・認証の有限計画案

PH/SG各最大2 leaf、3 session（A開始、再起動後A再確認＋B追加、操作者反復）で見積もる。

| API（各市場） | 1 session上限 | 累積上限 |
|---|---:|---:|
| GET `/api/v2/product/get_category` | 1 request（全件） | 3 |
| GET `/api/v2/product/get_brand_list` | 2 leaf×10 pages、page_size=100 | 60 |
| GET `/api/v2/product/get_attribute_tree` | 2 leaf、個別1 requestずつの保守案 | 6 |
| 合計 | 23 | **69/市場、138/両市場** |

これはAPIサービスの公式rate limitではなく、Owner承認用の内部上限案。
BrandはP1の1取得最大10ページを維持する。旧SG隔離50ページ承認をP5へ流用しない。
10ページでも終端でなければcurrent receiptなし、対象leaf全商品の準備を停止する。
offset非前進/循環/同ページ反復/矛盾ID/name/区分/欠損/途中失敗/取得契約不一致も同様。
更新開始で旧根拠を先に失効し、失敗後に保存済みSUCCESSへ戻さない。
Categoryも正規化で捨てたraw行を黙認せず、全件・階層・ID・件数整合を検査する。
Brandが少ページで終了した余裕を対象Category拡大へ使わない。catalogや対象leafが変われば再計画する。

公開公式reference（[Category](https://open.shopee.com/documents/v2/v2.product.get_category?module=89&type=1)、
[Brand](https://open.shopee.com/documents/v2/v2.product.get_brand_list?module=89&type=1)、
[Attribute](https://open.shopee.com/documents/v2/v2.product.get_attribute_tree?module=89&type=1)）の本文は公開取得で確認できなかった。
現在の仕様・paging・shop権限・rate limitは、Ownerが閲覧可能な公式資料で実行前に確認する。
過去DEC/現clientのpage_size=100・10ページ契約は実装根拠であって最新外部仕様の確認済み宣言ではない。
部分取得や第三者SDKを公式完全取得の根拠へ昇格しない。

認証は既存Google Sheet Access Token Sourceの市場別Bridge Viewer読み取りを提案する。
expected shop照合、操作ごと最新token取得、Source失敗時silent fallback禁止、Mapper refresh禁止を維持する。
Bridge readはShopee requestと別集計で最大69/市場を提案。Google認証refresh等の必要通信も事前に列挙し、
credential作成/変更・Google側同期変更・権限付与は本計画のAPI承認に含めない。
既存Keepa key/OpenAI key/Partner設定/Service Accountは非公開参照だけを記録し、本文を表示・複製しない。

## 6. 保存先・releaseと最小接続差分

新規P2 root案はコード外の`%LOCALAPPDATA%/ShopeeExpansionTool/P5/<run-id>/`。
`PH/<shop-ref>/work.sqlite3`と`SG/<shop-ref>/work.sqlite3`を分離し、各市場の新規cache・API ledger・claimも別ファイルにする。
絶対path・既存rootとの非重複・リンク先・Owner/操作者の読み書き権限・容量を非公開票で固定する。
今回はP2 DB/cache/ledgerを作成しない。既存DBからの複製・移行・初期化・resetもしない。
初回作成は承認後の明示一回操作、既存ファイルなら停止。P2 schema/store IDとshop/市場を照合する。

backupは全writer停止後、SQLiteの整合的backupと履歴件数・予約件数・digestを記録する。
復旧は別の隔離コピーでintegrity/履歴/UNKNOWN lockを検証し、旧本体を上書きしない。
消費ledger/claimを古いbackupへ巻き戻して予算を復活させない。不明消費は全予約を保持してOwnerへ報告する。
UNKNOWN/PENDINGがあれば、外部結果照合と明示解決まで再投入しない。

実行端末は現在のWindows端末を候補とし、Ownerが固定する。
受入用は別port（候補8511、空き未確認）・別起動記録・固定releaseとし、8501/8502/8503やショートカットを変更しない。
起動契約は同じ`app_beta.py`＋明示P5設定＋市場別P2 path/shop、loopback限定、初期化/再描画通信0。
P5のscope表示引数はP5_CONNECTIONに記載する。live許可loaderは提供せず、P4引数をlive許可として流用しない。
新しい接続codeが必要なら、offline最小実装→tests/保護回帰→formal採用の別承認→受入用固定release設置の順とする。
現在のformal mainを指定するだけではlive接続が成立しない。

| 最小差分候補 | 現行根拠・不足 | 保護・受入条件 |
|---|---|---|
| 明示P5接続adapter | `practical_beta_ui.py`、`classification_workflow_ui.py`は模擬専用。P4 APIボタン停止 | P4既定/合成経路を維持し、承認されたmarket/shop/run/予算だけを注入。UIフラグ反転のみは禁止 |
| 現在の公式資料搬送 | `ClassificationWorkflow.acquire_brand`→P1 strict receiptは再利用可能 | default transportの真正なlive取得を使う。fake transportを公式扱いせず、JSONでreceiptを捏造しない |
| 両市場のAPI予約と実消費 | `keepa_bounded_transport`はsend上限。累積token/F08 envelope保存は不足 | PHにも同じsend前予約、token予約・actual、失敗消費維持。API keyをログへ出さない |
| 画像live根拠 | P4は模擬検査だけ。既存画像providerに再送経路あり | 既存selector・疑義判断を共用し、全sendを制限。模擬検査のsource変更で代用しない |
| 運用出力/予約 | P2/P4はoffline CSVと模擬予約。P1にはoperational検証契約あり | 現在根拠・出力前後再検証・永続commit・UNKNOWNを維持。live準備出力の許可を別にbind |
| 限定AUTO_RULE | 現adapterは個別運用permitを注入しない | rule/alias全体hash、market/shop/session/catalog、承認参照の完全一致。未承認ruleは拒否したまま |

この表は接続不足の設計記録。案Bのoffline開発範囲と停止境界はP5_CONNECTIONに固定し、
実行票の対象・予算・保存先・release・live操作の承認は別途求める。
HUMAN経路だけでC04全体をPASSとしない。AUTO_RULEの実商品適用が必要なら対象定義と個別承認を別に提示する。
rollbackは受入processのPID/開始時刻/portを照合してそのprocessだけ停止し、受入入口を使用停止する。
既存運用release・全DB・履歴・予約・消費記録を保持する。新接続に問題があれば通常revertで修正候補を作る。

## 7. A01〜A07とF08 liveの実施票

各行をPH/SG別に採点する。実資料は原本を保持し、失敗系の故意の破損は合成fixture側へ分離する。

| ID | 手順・観測点 | 合格条件／証拠 |
|---|---|---|
| A01 | 新sessionで市場/shop/release/保存先/残枠確認→A取得→upload確認→別操作でGate。Bはsource_id付きtitle/回答/選択から生成 | 両入口・15列・出所/SHAが一致、対象外市場へ通信なし。実画面記録と取得履歴 |
| A02 | 当該市場全ショップCSV＋Safety資料→Gate→重複/保留/除外確認 | 重複は出力対象外。Battery/SLS/SG本体・実同梱/画像疑義停止を分類・メモで解除しない。実例不足の停止系はoffline証拠と明示 |
| A03 | 現公式leaf→Brand別確認。Aの2件中1件だけ採用し他方保留→明示再確認で追加。Bを追加 | 任意部分集合だけ保存。無関係なB追加で同sessionの有効Aを消さず、現在poolが群を横断。AUTO_RULE適用分とHUMAN分を別採点 |
| A04 | A途中保存→終了/再起動→新session→現在資料再受付・公式取得→A再確認→B追加。市場切替→戻る | 履歴保持、旧ready/receipt自動復元なし、国/shop/ID隔離。同内容の再取得も旧確認復活なし。変更・削除・失敗の範囲別失効を比較 |
| A05 | ready集合を選びCSV/TXT出力。downloadだけの状態を確認。予約/UNKNOWN/再起動/明示解決は合成専用DBで再生。既存正当出品は実最新CSV照合 | 市場×Category×Brand、列/BOM/ASIN集合一致。5状態・UNKNOWN lock・保存前bytes返却禁止。実投入成功をしていない商品へSUCCESSを偽記録しない |
| A06 | PH/SGで同じ通常操作・管理/診断・停止/復旧入口を比較。認証切れ/保存失敗/部分取得/古い選択はmock | 通常操作が共通、国別理由明示、旧保存先/ledger不変。mockと認証済み実画面を別記 |
| A07 | 操作者が3つ目のsessionで同じA/Bを再受付・確認・保存・出力し、保留理由と復旧を説明 | 重大な手作業迂回/履歴紛失なし、両市場で完成分を取り出せる。Ownerの明示実務受入。新Finder検索はしない |
| F08 live | 実応答のASIN/domain/AMAZON index0/RATING index16/availability/取得・更新時刻を実画面・確認CSVへ照合 | 円と星の変換、条件一致/外/不明、15列Candidate/Safety SHA結合、各sendのtokensConsumedと予約突合。raw評価45→4.5。NEW/Buy Box/件数を代用しない |

F08ではA由来・B由来を各市場最低1件追跡し、取得時点の実値とUI/CSVの完全一致を確認する。
Amazon本体の価格と平均評価の現在表示はOwnerが同一ASINの実画面で時刻とともに確認する。
Keepa観測との時刻差/丸め/販売なし/評価欠損を分け、異なる値を同じだったと記録しない。
不一致が変換不良なら修正対象、観測時刻差なら鮮度制約、原因不明なら未達として提示する。
境界値・欠損の全パターンを実商品の危険な加工で作らず、F01〜F07 offline証拠で補完する。

実出品なしで確認できるもの：候補取得、Safety停止、Category/Brand、pool、失効、出力、既存出品CSV一致。
別承認を要するもの：新商品の外部ツール投入、実際のSUCCESS/エラー/UNKNOWN結果の人間確認、新規出品後のCSV照合。
既存商品の出品済み照合は新しい準備→投入→出品完了の証明ではない。
実出品なしのA05は「実準備/実照合＋mock状態遷移」とし、実投入部分をNOT_RUNで残す。
それで完成判断に十分かはOwnerが判断する。新規出品を自動的なMUSTにしない。

## 8. 停止・未達・完成判断

即停止：承認対象/binding不一致、secret露出、Safety停止の迂回、他市場/shop/保存先混入、
資料欠損・旧receipt復活、request/token/費用枠不足、予約保存失敗、DB不整合、UNKNOWN再投入、
模擬根拠の公式昇格、未承認AUTO_RULE、旧releaseや未採用codeによる実運用。
失敗後は出力を失効し、送信・保存の事実と未確定結果を保持する。自動retry/追加課金/再初期化で継続しない。

結果表は各市場・各条件ごとに次の列を埋める：
`ID / offline tests / mock AppTest / 実ブラウザ / live API / 実商品 / Owner受入 / evidence_ref / 残件`。

| 完成条件 | 主な受入 | 完了に必要な留意点 |
|---|---|---|
| C01 | A01/A03 | 同じ通常入口で全工程 |
| C02 | A01 | 両入口の本来の出所 |
| C03 | A02 | Safety・全shop・保留、既存停止保護 |
| C04 | A03/A04 | HUMANだけで限定自動確定まで完成としない |
| C05 | A03 | 任意部分集合と個別操作 |
| C06 | A03/A05 | 群横断・現在条件の出力 |
| C07 | A05 | 5状態と実/mockの区別 |
| C08 | A04/A05 | 保存・再開・失効・永続lock |
| C09 | A01/A06 | 市場共通操作 |
| C10 | A06 | 管理/診断整理と復旧到達 |
| C11 | A04/A06 | 市場/shop/資料/認証/保存隔離 |
| C12 | A07 | 実商品反復とOwner実務受入 |
| F08 live | F08 | 実値・時刻・実消費を独立照合 |

未達は重大リスク、影響条件、最小修正、概算工数、回避策と残る限界を一覧にする。
実装未監査部分の工数を確約しない。接続/予算/公式receipt/UNKNOWN不備は実行前blocker、
軽微な精度改善・Finder最適化はBeta後候補として区別する。
実務Beta完成・実運用開始はOwnerの最終判断。offline/過去受入だけからCodexが決定しない。

## 9. Ownerに提示する具体的操作の承認票

次の9項目を非公開の実対象・release・保存先と対応させて提示する。空欄があれば実行承認を求めず先に補完する。

1. **商品・件数**：PH/SG各A/B 1〜3商品、seed/title/source_id/選定ASIN/leaf/shop、全shop CSV一覧、担当者。
2. **API操作**：上表のKeepa JP取得、Shopee 3 GET、Bridge read、必要画像GET/OpenAIのみ。対象外endpointは0。
3. **上限**：Keepa20 requests/市場・175 tokens/市場・合計350、標準見積308。OpenAI各$0.50・合計$1案。Shopee69/市場。Owner確定値へ再計算。
4. **認証・保存**：既存秘密の参照利用のみ、新規市場別P2/cache/ledger/claim、権限・backup・復旧先の絶対pathを非公開票で固定。
5. **release・環境**：接続差分の採用済み固定release、専用起動設定/port/端末、offline保護回帰の証拠。旧設定への書込みなし。
6. **実出品**：初回0。必要になった場合だけASIN/shop/価格/属性/数量/具体操作/取消方法を別票で承認。
7. **停止・戻し方**：失敗時停止、予約消費維持、受入processだけ停止、DBとUNKNOWN lockを保存。枠reset禁止。
8. **受入手順**：A01〜A07/F08、3 session、証拠層と未実施の区分、C01〜C12の残件。
9. **承認する操作**：対象票の初回保存先作成・固定受入release設置・列挙read-only/有料API・実商品準備保存・実画面確認を個別に明示。AUTO_RULE適用、実出品、formal merge、通常運用開始は別境界。

承認の引用・日時・対象票digest・承認操作・上限・期限/終了条件をTask Contextに結合する。
実行前に未解決blockerが0、technical gatesが対象releaseに一致、Owner承認が現在対象に一致することを確認する。
承認待ちは`WAITING_APPROVAL`、Task Context lifecycleは`OPEN`。同じタスクで明示承認された操作だけ続ける。
