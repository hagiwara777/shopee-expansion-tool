# P5 実務受入の実施設計・承認票

本書は[共通受入計画](PH_SG_BETA_ACCEPTANCE_PLAN.md)A01〜A07を実施可能な単位へ分けた提案である。
完成条件は[C01〜C12](PRACTICAL_BETA_COMPLETION.md)、価格・評価は[F08 live](CANDIDATE_PRICE_RATING_FILTERS.md)を適用する。
DEC-0137〜0143を変更せず、P1〜P4・F1/F2のoffline成果を保護する。
本書の作成・採用は実行許可ではない。実対象・保存先・release・予算を固定した承認票へのOwner明示承認が必要。
タスクの進捗・承認待ち・実測Git状態はrepo外Task Context、実行証拠はGit外に置く。
最小接続のoffline実装契約は[P5_CONNECTION](P5_CONNECTION.md)、DEC-0144を参照する。
接続コードが存在しても、本書の提案予算・実対象・live実行を承認したことにはならない。
trusted adapter・資料世代更新・D保存先の設計契約は[P5 live設計](P5_LIVE_DESIGN.md)／DEC-0146を参照する。

## 1. 対象を固定する作業票

以下の未確定欄がある間は実行承認票を確定しない。架空ASIN、過去shop、旧取得枠で代用しない。
商品本文・実CSV・画像・個別shop対応表はGitへ入れず、非公開作業票に記録する。

| 項目 | PH | SG | 固定方法 |
|---|---|---|---|
| 対象shop | Owner指定済み／実行Evidence未結合 | Owner指定済み／実行Evidence未結合 | 原指示の実IDは非公開票へ回収。認証のexpected shop・今回scopeとの照合は未実施 |
| 対象Category | 実leaf ID/path未確定、最大2 leaf案 | 実leaf ID/path未確定、最大2 leaf案 | 商品用途を先に確認し各市場の公式catalogで確定。他市場IDを転用しない |
| A：Expansion | seed指定済み／現在Fact・query未結合 | 同左 | 一般文具（電池なし）のOwner指定。strict 1ページからの準備対象ASINはまだ未選択 |
| B：Resolver | 1商品URL・title指定済み／同一性・Amazon ASIN未結合 | 同左 | 原文・出所・source_id案を非公開票で保持。案のIDをP5形式へ暗黙変換せず、実行前に対応を固定 |
| 既出品照合標本 | 0件とOwner確認済み。正例はNOT_RUN | 既存の正当な出品ASINがあれば別枠1件 | 最新全ショップCSVとの一致確認専用。架空の正例や新規準備poolへの二重投入を作らない |
| 全ショップ資料 | 1shop・0件はOwner確認済み／最新0件資料・日時・SHA未結合 | 1shop・提供CSV全件包含はOwner確認済み／現物・日時・SHA未結合 | 事業上の指定を再質問せず、今回の実行資料と実shopを照合。PHもshop数0・CSV不要にしない |
| 操作者／確認担当 | Owner指定済み／今回票への結合待ち | 同左 | 過去の原指定を回収し、今回の対象・実行Evidenceへ結合する。Category・Brand・画像疑義の判断者を再指定させない |

一般計画は標準8商品（PH 4＋SG 4）、許容4〜12商品。指定URL各1件へ具体化した初回案は
A2＋B1の各市場3商品・合計6商品であり、件数・枠は非公開票で再計算して別承認する。
API取得商品数・CSV行数・一意ASIN数・
実出品数を別々に記録する。新規実出品の計画値は0。
同一ASIN再登場・同Category/Brandの別商品・未確認商品の保留を含める。
危険物・Battery・刃物本体・コンタクトレンズ本体等を実出品試験に使わない。
初回ジャンルはOwner指定の一般文具（電池なし）。この指定をSafety認定・画像対象外・公式Category確定としない。
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

実証用rootは非公開票で固定し、`<root>/<run>/PH/<shop>/`と`<root>/<run>/SG/<shop>/`へ分ける。
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

2026-10-25の公開一次資料確認では、[Making Requests](https://keepa.com/api-docs/request-basics.html)の
共通応答仕様で`tokensConsumed`が当該requestの消費量、`tokensLeft`が残高であることを確認した。
ただし個別`/token`操作の現在仕様・無課金性・request/response全体は未確認であり、
この共通仕様だけで`keepa.token`のprimary sourceをverifiedにしない。実APIや契約残高は照会していない。

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
| GET `/api/v2/product/get_attribute_tree` | production禁止・allowlist外 | 0 |
| 合計 | 21 | **63/市場、126/両市場** |

これはAPIサービスの公式rate limitではなく、Owner承認用の内部上限案。
BrandはP1の1取得最大10ページを維持する。旧SG隔離50ページ承認をP5へ流用しない。
10ページでも終端でなければcurrent receiptなし、対象leaf全商品の準備を停止する。
offset非前進/循環/同ページ反復/矛盾ID/name/区分/欠損/途中失敗/取得契約不一致も同様。
更新開始で旧根拠を先に失効し、失敗後に保存済みSUCCESSへ戻さない。
Categoryも正規化で捨てたraw行を黙認せず、全件・階層・ID・件数整合を検査する。
Brandが少ページで終了した余裕を対象Category拡大へ使わない。catalogや対象leafが変われば再計画する。

公開公式reference（[Category](https://open.shopee.com/documents/v2/v2.product.get_category?module=89&type=1)、
[Brand](https://open.shopee.com/documents/v2/v2.product.get_brand_list?module=89&type=1)、
[Attribute](https://open.shopee.com/documents/v2/v2.product.get_attribute_tree?module=89&type=1)）は、2026-10-25時点の公開取得では本文未確認だった（Category / Brandの再確認もHTTP 403）。
2026-10-28には公開browserでCategory reference・関連guide・429のFAQ本文を確認した（5.1節）。
Brand / Attributeの現行本文、当該App/shopの個別権限、数値の呼出制限はこの確認に含めない。
使用操作の現在仕様・paging・shop権限・rate limitは、閲覧可能な公式資料と今回票を実行前に照合する。
DEC-0148により[P5操作別preflight](P5_CONNECTION.md)を適用する。未使用Attribute仕様は要求せずproduction操作は禁止する。
未使用OpenAIはallowlist外・requests/USD=0とし料金検証を要求しない。必要な画像検査は別に維持し、
使用するShopee/Bridge/OAuthの個別枠を0にしない。上表は複数操作を含む提案であり、承認操作ごとに再見積りする。
過去DEC/現clientのpage_size=100・10ページ契約は実装根拠であって最新外部仕様の確認済み宣言ではない。
部分取得や第三者SDKを公式完全取得の根拠へ昇格しない。

2026-10-27のOwner明示判断（DEC-0155）により、Shopee Support Center等への公式問い合わせは実施せず、
同じ問い合わせの再承認依頼も行わない。公式回答待ちを開発工程・Beta完成条件へ組み込まない。
公式公開資料・Developer Console・既存資料を優先し、許可済みの参照範囲で必要な一次資料を確認する。
問い合わせを使わず既存安全条件を満たす方法を検討し、問い合わせ不実施をHOLD解除条件にも新しいBeta blockerにもしない。
PRIMARY_SOURCE_UNVERIFIEDとPH Category実API HOLDは維持する。一次資料を確認できなければ影響する実API操作と
その依存工程を停止し、独立したoffline開発・検証は継続できる。未確認情報を確認済みにはしない。
これは実API試験の永久禁止ではない。別の方法で必要な一次資料・権限・有限枠等の既存条件を満たせれば、
実API試験の具体票について改めてOwner判断を求められる。既存承認境界・mandatory gates・PH/SG protected capability、
Safety・予算・credential保護・公式一次資料の確認要件を緩和しない。

認証は既存Google Sheet Access Token Sourceの市場別Bridge Viewer読み取りを提案する。
expected shop照合、操作ごと最新token取得、Source失敗時silent fallback禁止、Mapper refresh禁止を維持する。
Bridge readはShopee requestと別集計で最大63/市場を提案。Google認証refresh等の必要通信も事前に列挙し、
credential作成/変更・Google側同期変更・権限付与は本計画のAPI承認に含めない。
既存Keepa key/OpenAI key/Partner設定/Service Accountは非公開参照だけを記録し、本文を表示・複製しない。

### 5.1 Category単発試験の事前条件と実測

leaf取得が必要な場合は、DEC-0148 / DEC-0154の取得専用scopeを使い、必要な事前条件を揃えた後、
別承認したCategory単発試験を商品準備・P5実務受入より先に行う。接続は既存P5経路とし、
commerce-api-coreへの移行・全面修正や、未使用Brand / Attribute / Keepa / OpenAIの受入を先行条件にしない。
本節は9・10節の既存非公開票へ適用する操作別の具体化であり、新しい票・認可engine・live例外を作らない。

| 段階 | 既存票で固定・記録する内容 | 扱い |
|---|---|---|
| 送信前 | 対象市場・App/shopと根拠、原Owner承認・操作集合・期限/初回停止等の終了、固定release/実行対象、承認済み参照、保存identity/backupと停止方法 | 実値・原文・所在は非公開票。実設置・参照利用・API操作の許可を相互推定しない。作成後store IDは実作成後に結合し仮値を使わない |
| 一次資料の事前照合 | Category本文・資料版/取得日/body digest、当該App/shopの権限根拠、request/response・全件/paging・rate limitの根拠と確認範囲 | 原則は事前確認。個別権限の実効性だけはDEC-0157のPH既指定1shop・型付き原承認を使う場合に限り未確認を残せる。一般的な対応App種別・内部枠1を個別権限や公式rate limitの根拠にしない |
| 操作と上限 | `shopee.category` / `bridge` / `auth`だけをallowlistとし各物理send枠1。CategoryはGET・production host・language=en。leaf空集合、商品探索なし、他サービス枠0 | 枠は上限であり必ず3送信する指示ではない。実token・署名・認証付きURLを票や結果へ保存しない。初期表示/再描画は通信0・secret本文未読を維持 |
| 試験で実測 | 当該shopの認証・Bridge照合とCategory取得の実成否、実応答のraw/normalized件数・ID/parent/name/leaf/path整合、送信数と送信前予約・結果。DEC-0157では個別API権限の実効性もこの成否で確認 | 実接続の成功を事前条件へ戻さない。事前の公式仕様・対象/認証参照・shop照合は維持し、合成応答・過去成功・一般権限資料を今回の実成功にしない |
| 試験終了後 | 一覧と結果を保全し、後続商品票で用途・leaf・現在資料・完全scopeを固定する | 先行scopeを書き換えず、先行予約/消費を累積上限へ含める。別承認前はBrand・商品準備・出力へ進めない |

送信前の依存項目に空欄/UNVERIFIEDがあれば、原則10節どおりBLOCKEDとして実APIの最終承認を求めない。
唯一の例外は、[P5接続契約のPH個別権限単発確認](P5_CONNECTION.md#ph既指定1shopの個別app権限を単発試験で確認する契約)
を満たす個別App権限の実効性欄だけである（DEC-0157）。`verified=False`と権限`UNVERIFIED`を保持し、
仕様だけを別に確認済みとして結合する。既存の指定参照・shop・credential参照、単一allocationと累積上限を
原Owner承認へ結合し、Category／Bridge／auth各1・他0・再送0を要求する。通常scopeやSGへ転用しない。
これは当該adapter停止理由の限定変更であり、Global StateのHOLD/HARD_STOP・既存Safety・protected gate、
実設置・秘密参照利用・実API・main採用の別承認を変更しない。本書の採用だけではPH Category実API HOLDを解除しない。
当該shopでの実認証・取得成功は試験結果で確認するため、これ自体を事前に証明する試験の追加は要求しない。
公式問い合わせはDEC-0155どおり実施せず、閲覧可能な公式資料・Developer Console・既存資料の根拠を使う。

#### 保管済みCategory一次資料の照合範囲

2026-10-28のoffline読取では、次の保存PDFを本文・該当ページ画像・ファイルSHA-256で照合した。
資料identityはこの記録、実ファイルの所在/参照・照合者/日時と今回scopeへの結合は非公開票で保持する。
ローカル配置やファイル名だけで真正性・現在性・実行許可を判定せず、自動探索・credential読込を追加しない。

- 資料: `v2.product.get_category.pdf`（7ページ）。[公式元URL](https://open.shopee.com/documents/v2/v2.product.get_category?module=89&type=1)。
- 資料上の印刷日時: 2026-10-24 07:22。公式APIの改訂日や現在も変更がないことの証明とは区別する。
- ファイルSHA-256: `594cadda9de3f1f9bd0dd20847462f2ebe294005c8109c5ddc7f361abeac20e7`。

| 参照箇所 | 読取で確認した内容 | 今回の実行前に残る照合 |
|---|---|---|
| p.1–2 | GET path/production host、partner_id/timestamp/access_token/shop_id/sign、署名の入力とHMAC-SHA256、language（PH/SGはen） | 現在使用する仕様・署名実装・対象市場との一致。印刷済み本文だけで現在性をverifiedにしない |
| p.3 | `response.category_list`、ID/parent・名称・`has_children`、error/message/warning/request_id | 実応答と全raw行の検査・leaf/path整合は試験結果。記載のない独立したmarket/shop echoを仮定しない |
| p.2–3 | 掲載された要求/応答にページ指定・継続fieldはない | 現行の全件/paging契約の根拠との照合。field不掲載だけで全件保証を確定しない |
| p.6 | API Permissionsに一般的な対応App種別が掲載される | 今回の個別App/shopの権限・有効な認可との結合。一般一覧を個別権限の証明にしない |
| p.1–7 | この保存資料では数値rate limitの記載を確認できない | 閲覧可能な公式制限根拠の照合。未確認の数値や「1回だから制限なし」を補わない |

この部分照合だけで`primary_sources.category.verified=True`にしない。DEC-0157でも権限未確認のまま
仕様確認を分離し、それ以外の必要項目不足はPRIMARY_SOURCE_UNVERIFIEDで停止する。
PH Category実API HOLDは別承認・正式検証まで維持し、実資料の未結合と試験未実施を区別する。
PDF本文・token・個別shop情報はGitへ複製しない。未使用Brand資料は本単発試験の必須資料に追加しない。

#### 公開公式本文による追加照合

2026-10-28に、認証を行わず公開browserで次の本文を読取確認した。業務APIの試行ではない。
取得本文・URL・観測日時・digestはGit外Evidenceへ保持し、APIの改訂日と閲覧日を区別する。

| 公式資料 | 確認できた根拠 | 確認できない範囲 |
|---|---|---|
| [Category reference](https://open.shopee.com/documents/v2/v2.product.get_category?module=89&type=1) | GET / production host、署名・共通parameter、PH/SGのlanguage=en、要求にページ指定なし、`category_list`のID/parent/name/`has_children` | 対応App種別の一般一覧は個別App/shopの権限を証明しない。実認証・実応答は未実施 |
| [商品作成前の準備guide](https://open.shopee.com/developer-guide/209)（表示更新日2025-09-19） | 当該shopで利用可能な全Categoryを返す。市場・販売者種別等で一覧が異なる。parent=0がroot、`has_children=false`がleafで、作成/更新にはleafを使う | 仕様の全件契約を確認したもので、今回取得のraw行・件数・階層整合の実測ではない |
| [API呼出guide](https://open.shopee.com/developer-guide/16)（表示更新日2025-11-21） | Shop APIには認可されたshopの共通parameter・署名を使う | 当該Appの個別API権限・現在tokenの有効性は証明しない |
| [Debugging FAQのHTTP 429項目](https://open.shopee.com/faq?categoryId=2054)（表示更新日時2025-05-16 11:58） | 制限到達時は429。頻度を下げ、頻繁な再試行を避ける。継続的な負荷で呼出しを制限され得る | 数値閾値は掲載を確認できない。内部枠1を公式上限・無制限の証明にしない |

全件/pagingと429時の挙動の根拠は上記の範囲で確認済みとし、個別権限・数値閾値の未確認と混同しない。
数値非掲載を新しい独立gateにはせず、制限根拠の確認範囲と不明値を記録する。未確認値をverifiedへ補完しない。
DEC-0157の限定欄以外の必要項目が未結合ならPRIMARY_SOURCE_UNVERIFIEDで停止する。PH Category実API HOLDの別境界も維持する。

#### 単発試験の結果と合否

結果は10節の既存結果欄へ、対象scope・market/shop参照・release・session・時刻・資料参照と結合して記録する。

| 結果 | 記録・判断 |
|---|---|
| NOT_RUN / BLOCKED | 試験未実施、または事前条件が未成立。試験成功へ置換しない。送信0だけで参照読込・予約・部分作成も0だったと推定しない |
| PASS（Category単発のみ） | 現在承認された経路でBridgeのmarket/shop照合とCategory取得が成功。HTTP/application応答・全raw行・件数・重複/欠損/循環・親子/leaf/pathが現行validatorに適合し、leaf一覧を取得。Category実送信1、Bridge実送信1、Google auth実送信0または1、他API0、全送信が事前予約と対応し結果が保存される |
| FAIL / 結果不明 | auth/Bridge失敗、HTTP/application error、timeout、parse/階層不整合、枠/保存/checkpoint障害等では停止・予約/UNKNOWN/履歴保全。自動再送・診断API・枠resetを行わず、受信済み部分を成功へ昇格しない |

失敗・429・timeoutを意図的に発生させる追加live試験は含めず、異常系はofflineで検証する。
単発PASSは当該scopeの接続/取得確認に限る。サービスの数値rate limit、他市場/shop、Brand完全性、
商品Safety・準備許可、F08/C04/C12・P5全体の実務受入を証明しない。

## 6. 保存先・releaseと最小接続差分

新規P2 rootはD固定ドライブ上のコード外`P5_DATA_ROOT`を第一候補とする。
正確な絶対pathは非公開票へ記録し、`P5Scope.root`にはrun-idを含めない。
配置は`<root>/<run-id>/<market>/<shop>/`とし、C上の既存Git/worktree/.venv/DB/outputsを移動しない。
`PH/<shop-ref>/work.sqlite3`と`SG/<shop-ref>/work.sqlite3`を分離し、各市場の新規cache・API ledger・claimも別ファイルにする。
絶対path・volume identity・既存rootとの非重複・リンク先・Owner/操作者の読み書き権限・容量を非公開票で固定する。
Dは固定NTFSだが親の広いACLをそのまま継承しない。専用ACL・probe・排他初期化・backup/復旧・
容量停止の具体契約はP5_LIVE_DESIGNに従う。今回は候補rootも作成しない。
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
| 明示P5接続adapter | typed authority・operator・同process initializerをoffline実装済み。実原承認sourceと起動担当の実登録は未結合。P4は模擬専用 | 承認実施票と実コード/市場/shop/run/保存/予算を照合し注入。UIフラグ反転や設定だけの許可は禁止 |
| 現在の公式資料搬送 | strict receipt、default transport、各Shopee物理page前Bridge再取得と有限Bridge/auth予約をoffline接続済み。公開Category仕様の照合範囲は5.1節、liveは未実施 | 使用操作の現行一次仕様・実参照を照合。個別権限はDEC-0157の限定経路だけ試験で確認し、fake/保存JSONを公式扱いしない |
| 両市場のAPI予約と実消費 | P5Ledger/P5KeepaBudgetのtoken予約・actual/UNKNOWN・送信前永続化は既に実装済み | 重複実装せず、trusted組成と明示再取得も同じledgerへ計上。F08 live実測は未実施 |
| 選択後の商品資料更新 | 新規formatでjournal・P2先行失効・世代/revision照合・明示fresh取得をoffline接続。旧formatは資料変更停止 | 元selectionとscopeを保つ。旧run自動移行なし。半端な世代やUNKNOWNでは出力・再送を拒否 |
| 画像live根拠 | P4は模擬検査だけ。既存画像providerに再送経路あり | 既存selector・疑義判断を共用し、全sendを制限。模擬検査のsource変更で代用しない |
| 運用出力/予約 | P5からP1/P2 operational出力・commit前/bytes前の世代/許可再検査・checkpointをoffline接続済み。実原承認は未結合 | 現在対象への許可とbackup容量計画を実設置票で固定し、永続commit・UNKNOWNを維持。準備出力と外部投入・出品は別承認 |
| 限定AUTO_RULE | 現adapterは個別運用permitを注入しない | rule/alias全体hash、market/shop/session/catalog、承認参照の完全一致。未承認ruleは拒否したまま |

この表は実装済み部品と実環境への未結合を区別する。案Bのoffline開発範囲と停止境界はP5_CONNECTIONに固定し、
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

次の9項目を非公開の実対象・release・保存先と対応させて提示する。今回許可を求める操作の依存項目に
空欄があれば先に補完する。API0等の先行準備では未使用操作の未結合を後工程の停止条件として残せる。
実store IDは排他作成後に結合し、仮値を入れない。11節のstorage-only準備と完全scopeの設置を区別する。
[RUNBOOK「承認集約・自律継続ルール v1」](RUNBOOK_CHATGPT_CODEX.md#承認集約自律継続ルール-v1)を適用し、
実行可能なoffline事前確認を終えて提示する。一般ルールで本書の再送禁止・UNKNOWN停止を緩和しない。

1. **商品・件数**：PH/SG各A/B 1〜3商品、seed/title/source_id/選定ASIN/leaf/shop、全shop CSV一覧、担当者。
2. **API操作**：上表のKeepa JP取得、Shopee Category/Brand GET（Attributeは0）、Bridge read、必要画像GET/OpenAIのみ。対象外endpointは0。
3. **上限**：Keepa20 requests/市場・175 tokens/市場・合計350、標準見積308。OpenAI各$0.50・合計$1案。Shopee63/市場。Owner確定値へ再計算。
4. **認証・保存**：既存秘密の参照利用のみ、新規市場別P2/cache/ledger/claim、権限・backup・復旧先の絶対pathを非公開票で固定。
5. **release・環境**：接続差分の採用済み固定release、専用起動設定/port/端末、offline保護回帰の証拠。旧設定への書込みなし。
6. **実出品**：初回0。必要になった場合だけASIN/shop/価格/属性/数量/具体操作/取消方法を別票で承認。
7. **停止・戻し方**：失敗時停止、予約消費維持、受入processだけ停止、DBとUNKNOWN lockを保存。枠reset禁止。
   再試行なしを明記し、期限・初回停止等の許可終了条件を固定。HTTP0でも鍵参照・予約・部分作成を確認し、結果不明と区別する。
8. **受入手順**：A01〜A07/F08、3 session、証拠層と未実施の区分、C01〜C12の残件。
9. **承認する操作**：対象票の初回保存先作成・固定受入release設置・列挙read-only/有料API・実商品準備保存・実画面確認を個別に明示。AUTO_RULE適用、実出品、formal merge、通常運用開始は別境界。

承認の引用・日時・対象票digest・承認操作・上限・期限/終了条件をTask Contextに結合する。
実行前に未解決blockerが0、technical gatesが対象releaseに一致、Owner承認が現在対象に一致することを確認する。
承認待ちは`WAITING_APPROVAL`、Task Context lifecycleは`OPEN`。同じタスクで明示承認された操作だけ続ける。
同じ目的・リスク境界の許可済み工程は逐次再質問せず進める。技術障害では独立した原因調査・修正・offline検証を継続する。
別操作・失効・CLOSED後は旧許可を転用しない。新承認でも停止済みledgerのreset・再初期化は許可しない。

## 10. 初回実行票の固定欄と再利用審査

この節は非公開実施票の必須schemaとする。値・一次資料の所在・確認者・確認日時・SHAを
各欄へ対応させ、今回要求する操作の依存欄に空欄/UNVERIFIEDが残る票は原則`BLOCKED`として最終実行承認を求めない。
例外は5.1節／DEC-0157のPH既指定1shop・Category単発試験の個別App権限欄だけとし、未確認を明記して型付き原承認へ結合する。
技術方式はP5_LIVE_DESIGNに固定し、Ownerへhash計算や実装方式の選択を求めない。
以下の状態を分離する：`Owner指定済み／実行Evidence未結合`、`実行Evidence照合済み`、
`実行未承認／承認済み`。原指示確認はlive許可や現在商品の証明ではない。
個別shop ID・ASIN・URL・商品本文・実CSV・承認原文はGitへ入れず、非公開票で参照と状態を保持する。

| 欄 | 必須の具体値と一致検査 |
|---|---|
| 票identity | 票ID/version/digest、目的、Owner承認原文/日時、許可操作と工程列、期限/timezone・初回停止等の終了条件、操作者・確認者 |
| 市場/shop | PH/SG各初回1shopの実ID・識別名、全shop一覧と各CSV参照。Owner一覧・資料shop対応・expected shopを三者照合 |
| A探索 | 各市場seed ASIN、用途、strict query全体、page=0/perPage、詳細最大数、準備上限、選択担当。探索承認と取得後選択を別記 |
| B入力 | 各市場source_id/元title/originと手動Resolverサービス、候補ASIN、詳細取得対象確認、取得後の同一性根拠・確認者 |
| 固定選択 | 探索後の選択ASIN集合・selection/batch digest、同一性、候補/文章/sidecar SHA、更新可能な同じASIN部分集合。追加・差替え不可 |
| 公式資料 | 当該市場/shop Category全件・leaf ID/path、Brand strict終端/ID/name/区分、Seller Centerまたは既存出品ツールでの商品別属性確認担当。承認操作の一次本文・版・権限・形式一致が必要 |
| 全shop CSV | 実際に全shopであるOwner確認、各CSVの取得日時/市場/shop/SHA/行数、正当な0件資料、既存出品照合ASINを準備対象と区別 |
| API/費用 | 操作別回数・payload上限・物理send・tokens/USD・両市場合計、既予約/消費・追加上限、計画した再取得回数、再試行なし、現在公式単価参照、実測方法、失敗消費保持 |
| release | 最小差分を正式採用した固定full commit/実ソースdigest、端末/実entrypoint/port、technical gates。PR #135の採用だけではlive adapter未提供 |
| 保存 | Dの正確なroot/run/市場/shop path、volume identity/非重複/専用ACL/probe、作成後のstore ID/schema、cache/ledger/claim、backup/復旧path、容量計画 |
| 操作境界 | 設置、既存credential参照利用、列挙API、商品準備保存/出力、再起動反復を別チェック。外部投入0・実出品0・AUTO_RULE0 |
| 結果 | A01〜A07/F08/C01〜C12を市場別にoffline/mock/実画面/live/実商品/Owner受入へ分離し、未達/NOT_RUN/停止理由を保持 |

提案枠を以下にまとめる。これは現在価格の確認済み見積・承認済み枠ではない。

| 制約 | PH | SG | 合計/固定条件 |
|---|---:|---:|---|
| 準備商品 | A/B各1〜3 | A/B各1〜3 | 4〜12。seed/詳細取得数と別 |
| Keepa requests | 20 | 20 | 40、token照会/失敗/再取得も物理送信として計数 |
| Keepa tokens | 175 | 175 | 350。従来計画154/市場、308合計を実対象へ再計算 |
| Keepa要求商品延べ数 | 最大72案 | 最大72案 | 144。Finderは別枠1ページ/市場、最大50返却 |
| Shopee requests | 63 | 63 | 126。Category3＋Brand60、Attribute0/市場、1取得10page維持 |
| Bridge read | 63 | 63 | 126。各Shopee物理操作前。別診断読取を自動追加しない |
| Google auth物理send | 最大63案 | 最大63案 | 126。Bridge1回あたり最大1 auth sendの内部案。ライブラリ隠れretryをofflineで拒否できなければ実行停止 |
| OpenAI calls/USD | 13 / 0.50 | 13 / 0.50 | 26 / 1.00。Category12＋画像1/市場、現在model/単価再検証が必要 |
| 画像GET | 3 | 3 | 6。既存selector、1画像検査call最大3枚、再検査も枠消費 |
| 新規出品/外部投入 | 0 | 0 | 0。実SUCCESSを合成結果から作らない |

上限はoperationごとの権限と併用する。余り枠で対象/endpoint/leaf/ページを増やさない。
3 session・再取得/旧cache補完を含む詳細計画は3〜5節を基準にし、
画像再検査が必要なら1call/市場で不足し得るため、迂回せず再見積・別承認する。

過去指定の再利用は「同じだったと思う」では行わない。Owner原指示参照、正本Decision/承認票、
一次商品資料/実CSVのASIN・市場・shop・用途・source_id、今回scopeの一致を行ごとに検査する。
旧SGの最大3商品/$1/50page枠、6商品Category受入、旧100578資料を初回P5の指定や現行性証明へ流用しない。
Owner原指示を直接確認できた指定は`MISSING`に戻さず、最新資料未照合なら
`Owner指定済み／実行Evidence未結合`とする。提供済みとの原指示はあるが現物を特定できないCSVも同様とする。
直接確認できない値は`UNVERIFIED`、未指定値/参照不明は`MISSING`とし、既指定値を再選定させず残る参照だけを確認する。
過去P5 Contextの設計承認・offline採用は今回の実行承認ではない。

即停止は、Governance HOLD/HARD_STOP、票/実コード/scope/shop/credential/保存不一致、一次仕様未確認、
DEC-0157の限定記録のない個別権限未確認、
対象/資料/selection世代不一致、Safety停止、公式部分取得、有限枠不足/不明消費、保存/backup/容量検査失敗、
未完了更新intent、PENDING/UNKNOWN投入lock、未承認AUTO_RULE、secret露出である。
対応は対象process停止・現在出力失効・予約/履歴保持とし、retry・枠reset・資料の推測補完で継続しない。
承認票version/対象/上限/主要リスク/releaseが変われば現在対象への承認を取り直す。


## 11. 実行前の合成一連リハーサル

`tests/test_p5_acceptance_rehearsal.py`をPH/SGそれぞれで実行し、部品単独試験に加えて
固定A/B選択の台帳を原承認再照合付きoperatorで再開し、現在資料→HUMAN確認→P2保存→運用形式出力→checkpointの連鎖を検証する。
探索と対象固定の準備は既存SDK・合成HTTP・offline permitを使い、trusted許可による探索送信の検査は既存adapter/transport試験で補う。
合成原承認・OS観測・商品・HTTP・credential解決を使用し、実秘密・実API・実商品を使用しない。
合成経路のTRUEは出力契約を試す値であり、実商品の準備許可ではない。

| 合成シナリオ | 一連試験の確認範囲 | 対応する実受入の残件 |
|---|---|---|
| 3 sessionのA/B反復 | Aの2件中1件を確認、他方保留。新sessionでは旧pool/receiptを復元せず、現在資料と再確認後にBを追加。固定選択・消費予約・履歴を保持し、完成分だけ出力。各出力前と終了時に整合backupを作る | A03/A04/A05/A07の実画面・実資料・実操作者による反復とOwner受入 |
| 原承認の撤回 | 準備後の撤回で出力を拒否。追加送信・消費・履歴変更を起こさず、現在poolを失効 | 実原承認sourceと撤回検出の結合 |
| UNKNOWN後の再開 | 合成投入結果UNKNOWNとlockを再起動後も保持し、現在資料を再確認しても二重予約・出力を拒否 | 実投入は初回0。実際の外部結果照合は対象操作への別承認がある場合だけ |

この試験のBridge読取とcredential解決は合成seamであり、物理Bridge/OAuth予約・secret遅延読込の
証拠は既存transport/service試験で別に確認する。Windows/code観測も合成で、実端末のACL・
volume・probe・listener検査、Streamlit実ブラウザ、画像/API品質、F08実消費、C04/C12を証明しない。
試験のバックアップ容量値は合成fixture用で、実設置の容量承認へ転用しない。

次の単一作業は10節の非公開票に、使用操作の一次仕様と現在の実行資料を結合し、最小設置票を固定すること。
既存の最小設置票、I1/API0調査、固定Python/配布物manifestを読取照合し、使用releaseとの差分と残件だけを更新する。
storage-onlyの親/root・ACL/probe準備と`P5Setup.install()`を混同せず、取得専用または完全商品scopeの
[契約](P5_CONNECTION.md#leaf未確定時のcategory取得専用scope)を満たす。仮store ID・仮leafで通さない。
API0票では使用しないAPI・credential・商品scopeの未結合を後工程の停止条件として保持し、先行準備をlive開始の許可にしない。
既指定のshop/seed/Resolver入力/既出品状況は再選定せず、次の未結合だけを埋める。

1. 使用するCategory/Brand/Keepa token等の一次本文・版・権限・payload/応答・pagingを照合する。未使用操作は要求しない。
2. 全shop実CSVの参照・取得時刻・SHA、商品同一性、操作者/確認者、再取得回数と有限枠を固定する。
3. trusted起動担当の実コード・原承認source・現在票の読取契約と、固定release/entrypoint/port/新規root/ACL/probe/backup容量・復旧先を票へ結合する。
4. DEC-0157の個別App権限欄以外で、今回要求する操作の依存欄に空欄やUNVERIFIEDが残る票はBLOCKEDを維持する。補完後に9節の具体操作について設置と実行の承認を求める。

Owner指定、offline検証、formal採用、実設置、live実行、実務受入を別々に記録し、
このリハーサルの成立だけで後段を完了扱いにしない。
