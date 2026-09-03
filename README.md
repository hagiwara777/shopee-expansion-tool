# Shopee Expansion Tool Ver1

ASINを1件入力し、Keepa APIから `brand + category` 基準の候補ASINを取得して、画面表示とCSVダウンロードを行うローカルWebアプリです。

KeepaのWeb画面操作、Amazonページ操作、Amazon/Keepaスクレイピングは行いません。

## Amazon data provider

通常・本番想定のAmazon data providerはKeepaです。`AMAZON_DATA_PROVIDER`が未設定または
`keepa`の場合は、従来どおり`KEEPA_API_KEY`とKeepa経路を利用します。未知のprovider値を
Keepaへ自動fallbackしません。

Beta開発・試験時だけ、プロジェクト直下のGit管理外`.env`で次を明示するとCanopy TEST経路を
利用できます。

```dotenv
AMAZON_DATA_PROVIDER=canopy_test
CANOPY_API_KEY=your-local-key
```

Canopy TESTはResolver 1回最大10 ASIN、Expansion 1回最大7 requests・最大5候補です。
retry、Keepaへのfallback、検索paginationの自動継続は行わず、結果をKeepa SQLite cacheへ
保存しません。Resolverの確認値は`CANOPY_VERIFIED`、Candidate CSVのsourceは
`asin_resolver_canopy_verified`となり、Keepaの`KEEPA_VERIFIED`と区別されます。
`PRELISTING_CANDIDATE_V1`の15列schemaは変わりません。通常UIにprovider選択欄はなく、
Canopy mode時だけ`Amazon data provider: Canopy TEST`と表示します。

## Ver1でできること

- ASIN 1件を入力
- 検索モードを `strict / standard / broad / category_research` から選択
- 検索ページ数を `1ページ / 3ページ / 5ページ` から選択
- Keepa APIで起点ASINの商品情報を取得
- 起点ASINの `brand` と `categoryTree` を使って候補ASINを取得
- 結果を画面表示
- 対象市場を選んだ出品前保安ゲートで、Guardrail・既出品照合などを確認
- 出品前保安ゲート用候補CSVをダウンロード

- 入力欄、検索モード、検索ページ数、検索ボタン、CSVダウンロードボタンを縦並びで表示
- 同じ検索条件の結果はSQLiteに7日間キャッシュ

## ASIN Resolver Tool Ver0.4.3

ASIN Resolver Tool Ver0.4.3は、Expansion Tool内に追加した独立補助機能です。

商品名リストから`R0001`形式のsource_id付きプロンプトを生成し、ChatGPTやGeminiなどの外部AIが返した結果を手動で貼り付けて解析します。元の商品名はそのまま保持し、AI用プロンプトに渡す検索用タイトルだけからShopeeの既知販売定型文を除去します。推奨形式はTSVで、標準的なCSV、Markdown表、箇条書き、Amazon.co.jp URLを含む通常テキストにも対応します。source_idがないVer0.2形式も扱えます。崩れたAI返答では、行頭source_idと次行以降のAmazon.co.jp URLまたは不明値を対応付ける最小フォールバックも行います。

Amazon.co.jp URLまたは明示されたASIN候補を抽出し、Keepa確認前に解析結果と件数をプレビューします。確認対象は表で手動選択でき、選択済みASINだけを重複排除してKeepa APIでAmazon.co.jp商品の実在確認を行います。確認後は、確認実行時に選択した行をsource_id付きCSVでダウンロードできます。プレビュー段階ではCSVを出力しません。

初回AI返答で既知のsource_idがすべて`UNKNOWN / NOT_CHECKED / AI returned unknown`となり、Amazon.co.jp URL・ASIN候補が1件もない商品は、再検索支援タブに1商品1行で表示できます。元の商品名と初回検索用タイトルは読み取り専用で保持し、再検索用タイトルだけを手動修正して、同じsource_id付きの再検索プロンプトを生成します。再検索のAI返答は既存の解析欄へ貼り付けます。再検索対象の生成・編集・プロンプト生成ではKeepa APIを呼ばず、再検索結果を初回結果やCSVへ自動統合しません。

ASIN Resolver Tool Ver0.4.3は商品名からAmazon商品をアプリ内部で検索する機能ではなく、外部AIの返答から候補を抽出する補助ツールです。CSVファイルのアップロード、Expansion Toolへの自動投入、Shopee API連携、自動出品、Amazonページ操作、ブラウザ自動操作、AI API・Gemini API・Web検索APIの自動呼び出しは行いません。Guardrail FilterもResolverからは呼び出しません。Evidence Batchを開始していないlegacy／非証跡モードでは、source_idや工程証拠を永続保存しません。

### Evidence Batch（PH基準実行用）

Evidence Batchは、PHのformalな基準実行で入力からResolver exportまでを追跡するための任意の耐久保存機能です。新規batch作成時には、Manifestに記録する40桁SHAを明示入力します。その値はFORMAL Briefで承認された環境変数`ASIN_RESOLVER_APPROVED_FORMAL_MAIN_COMMIT`の40桁SHAと一致しなければならず、環境変数が未設定・不正値の場合も作成しません。`origin/main`、現在HEAD、別のUI入力欄から承認値を自動採用しません。再開時も同じ環境変数とManifestを照合します。

batchを開始すると、貼り付け入力をUTF-8・LF改行で不変の`source_input`として保存し、`upstream_source_id<TAB>input_title`形式のTSVまたは従来の1行1商品入力から`R0001`形式のResolver source IDを作成します。upstream IDがない従来入力では、架空のupstream IDを補完しません。run packageはGit管理外の`outputs/asin_resolver_runs/<batch_id>/`に保存され、Evidence Manifest、sidecar SHA、source map、prompt、AI応答、解析結果、候補CSV、Resolver exportを親子関係とSHAで索引化します。

既存Manifestから再開する前に、schema、batch ID、artifact SHA、親artifact、source map、checkpointを検証します。SHA不一致、別batch混入、欠落、未対応schema、違法なcheckpoint遷移では既存packageを変更せず停止します。Retryなしは初回解析からexportへ進め、Retryありは選択・prompt・応答・解析の全工程を保存してからexportへ進めます。`COMPLETED`後の成果物追加やcheckpoint変更はできません。

Evidence Manifestは機械可読の成果物台帳であり、runtime artifactの受入状態は`RUNTIME_PRODUCED_PENDING_HUMAN_ACCEPTANCE`です。Excel実行記録は人間向けの補助記録であり、Manifestの代替ではありません。Evidence Batchは外部AI送信、Keepa呼び出し、商品同一性判定、検索条件を自動変更しません。legacy／非証跡モードはformalな固定30件基準実行には使用しないでください。

Direct Chat Assistは、生成済みの初回・再検索プロンプトをブラウザのクリップボードへコピーし、Amazon URL検索用のChatGPTプロジェクトを開くための手動操作補助です。`AMAZON_SEARCH_PROJECT_URL` をプロジェクト直下の `.env` に任意設定するとプロジェクト起動操作を利用できます。URLが未設定でもResolver本体は通常どおり利用でき、ChatGPTへの自動貼り付け・送信・回答取得は行いません。

## Shopee調査CSV取込 Ver0.1

「Shopee調査CSV取込」は、複数の競合調査CSVをResolverの通常入力とは独立して前処理する機能です。`Country=PH` と `Location=Japan` の完全一致行だけを対象にし、`shopee.ph` の商品URLを正規化して最新 `Search Date` を採用します。同じURLの旧行、対象市場外、URL不正、タイトル確認が必要な行はResolverへ送らず、追跡用Manifestと保留・除外CSVへ残します。

Resolverへ渡すTSVは UTF-8 BOM付きの `source_id<TAB>input_title` の2列だけです。Manifestには元のタイトル、クレンジング後タイトル、URL、出所、重複情報を保存します。この機能はAmazon検索、Keepa、OpenAI、Shopee API、Resolverの自動実行を行いません。

Ver0.4.2では、元の商品名を保持したまま検索用タイトルだけから `official store` と `shipped from japan` を追加除去します。

Ver0.4.3では、Keepa確認後に元Shopeeタイトル、Keepa商品タイトル、Keepaブランドを画面上で比較できます。既存Keepa応答を再利用するため追加API問い合わせはなく、CSVは従来の7列のままです。

## 出品前保安ゲート Phase 4A-2

出品前保安ゲートは、画面上でSGまたはPHを選択できます。Expansion ToolまたはASIN Resolver Toolで出力した候補CSVと、対象市場の各ショップの既出品CSVを入力し、Guardrail、既出品ASIN、入力内重複、起点ASIN自身、メタデータ不足を判定します。最終判定は `ELIGIBLE / REVIEW / EXCLUDE` とし、ELIGIBLE CSV、REVIEW CSV、全件の監査用CSVを出力します。利用者は対象市場、全ショップ数、Candidate CSV、全ショップ分の既出品CSVだけを入力します。アップロード順に内部証跡labelを自動生成し、実ショップ名は入力しません。全ショップ数とCSV数が一致しない場合は停止し、既出品ASINは全アップロードCSVを横断して照合します。

PH対応は、PH専用Guardrail辞書、入力契約、ローカルテストで確認済みです。実データを使ったPHの実画面・実業務受入と、出品支援ツール全体の完成判定はまだ完了していません。

ELIGIBLEはShopee規約上の安全を保証するものではなく、出力CSVは外部出品ツールへ直接投入する形式ではありません。入力が変わった場合は古い判定結果を破棄し、判定時に外部APIを追加で呼び出しません。

## Category Mapper

Category Mapperの「Shopee ACCESS_TOKEN（一時利用）」には、既存管理シートで更新済みのtokenを伏字で貼り付けられます。入力値はそのブラウザsessionのCategory / Brand / Attribute参照だけに使い、設定ファイルやローカルDBへ保存しません。空欄の場合は既存の認証設定を使用します。token更新、refresh、OAuthはCategory Mapperの責務に含みません。

## 出品前保安ゲートのGuardrail

Guardrailは候補生成の結果を直接出品候補にするための機能ではなく、出品前保安ゲートが
対象市場を選んで実行する市場別の確認の一部です。GateはGuardrailに加え、既出品ASIN、
入力内重複、起点ASIN自身、メタデータ不足も確認し、最終結果を `ELIGIBLE / REVIEW /
EXCLUDE` とします。

Guardrailは、候補生成時に取得済みの `product_title`、`brand`、`category`、任意の
Ingredient Safety Fact sidecarに含まれる `ingredients`、`activeIngredients`、
`specialIngredients`、およびProduct Text Safety Fact sidecarの承認済み商品文章だけを使う
CSV辞書ベースの確認です。AI判定、Web検索、Shopee API連携、Keepa APIの追加呼び出しは
行いません。

Guardrail内部のステータスは次の3種類です。これらはGateの最終結果ではありません。

- `SAFE`: 選択した市場の現時点の辞書ルールに一致しなかった候補です。出品安全を保証する意味ではありません。
- `REVIEW`: 人間確認が必要な候補です。
- `BLOCK`: アカウント保護のため出品準備へ進めない候補です。

辞書が存在しない、壊れている、必須列が不足している、不正値がある場合、Gateは判定を
停止します。全件をSAFEとして通すことはありません。

### Guardrail辞書

#### 再設計方針（実装前）

Guardrail禁止辞書は、全市場で共通する`COMMON_BLOCK`と、`PH_BLOCK`、`SG_BLOCK`、
`MY_BLOCK`等の市場別BLOCKに分離する方針です。選択市場の実効BLOCKは
`COMMON_BLOCK ∪ 選択市場BLOCK`とし、市場別BLOCKは追加禁止だけを担当します。
市場別ルールでCOMMON_BLOCKを解除する仕組みは作りません。

禁止辞書に一致した対象は必ずBLOCKとし、BLOCKからREVIEWへ降格しません。BLOCKは
Shopee上で理論上販売可能かではなく、当社として出品しないと確定した対象を意味します。
Shopeeが明確に販売禁止としている対象、輸出入・配送上当社運用で扱えない対象、現地
ライセンスが必須で当社が取得しない対象、および根拠資料により当社が今後出品しないと
確定した対象をBLOCK候補とします。

REVIEWはBLOCKと別管理し、具体的な追加確認・対応によって販売する可能性が残る対象だけに
限定します。根拠のない漠然とした危険性では追加せず、人が何を確認すれば通過またはBLOCKを
決められるかを明記します。必要な情報を現時点で保有しない場合は、無理にREVIEW辞書を
作りません。ELIGIBLEは現在のBLOCK／REVIEW条件に該当しなかったことだけを意味し、Shopeeの
販売承認、法令適合、知財安全性を保証しません。

この節は辞書再設計の正式方針です。現在のCSV、商品コード、Gate判定ロジックにはまだ
実装されていません。具体的な辞書項目は、根拠資料の実物照合後に別工程で設計します。

辞書CSVは `guardrails` フォルダにあります。Gateで選択した市場の辞書だけを使います。

- `guardrails/prohibited_brands_sg.csv`
  - Shopee SG向け禁止・高リスクブランド辞書です。
  - `brand` フィールドへの exact match のみ許可しています。
  - `title` や `category`、`contains` が入っている場合はエラーになります。

- `guardrails/risk_keywords_sg.csv`
  - Shopee SG向け禁止語・要確認語辞書です。
  - `title / brand / category / all` に対して、`exact / contains` で判定します。

- `guardrails/prohibited_brands_ph.csv`
  - Shopee PH向けブランド辞書です。現在は固定ヘッダーのみで、PHの有効ブランドルールはありません。

- `guardrails/risk_keywords_ph.csv`
  - Shopee PH向け禁止語・要確認語辞書です。

各辞書CSVの列は以下に固定しています。

```text
term,action,risk_category,match_field,match_type,source_type,note,enabled
```

重要なルール:

- `action` は `BLOCK` または `REVIEW` のみです。`SAFE` を辞書に書くとエラーになります。
- `enabled` は `TRUE` または `FALSE` のみです。空欄や別の値はエラーになります。
- `enabled=FALSE` の行は判定に使いません。
- 辞書CSVは UTF-8 または UTF-8 BOM で保存してください。
- 同梱辞書は網羅的な公式リストではありません。初期たたき台です。
- 辞書はユーザーが手動で拡張・更新する前提です。
- Shopeeの最新規約やブランド制限の最終確認はユーザー側で行ってください。

同じ候補CSVでも、Gateを再実行すればその時点の辞書で再判定します。

## 検索モード

- `strict`: brand + leaf category ID。初期値。精度重視です。
- `standard`: brand + parent category IDを優先します。parentが取れない場合はrootCategoryを使います。
- `broad`: brand only。候補数重視ですが、カテゴリ外商品が混ざる可能性があります。
- `category_research`: category only。同カテゴリ市場調査用です。

## Ver1で実装しないこと

- アプリ内部からのAI API / Gemini APIの自動呼び出し
- AI返答の自動取得
- ASIN Resolverの結果をExpansion Toolへ自動投入
- PH / MY / THの市場別出品判断・出品準備の受入（出品前保安ゲートはSG／PHを選択可能。PHの実データを使った業務受入は未完了）
- 外部出品ツール互換CSV
- Shopee API連携
- 自動出品
- 自動削除
- Expansion Tool単体での既存ASIN照合（出品前保安ゲートではアップロードした既出品CSVと照合済み）
- 履歴保存、SQLiteによる判定履歴（削除済みASIN履歴を含む）
- AIによる安全判定、LLMによる商品分類
- Web検索、Shopee規約の自動取得
- Keepa APIの追加取得
- Keepa Web画面操作、Amazonページ操作、スクレイピング
- 本番アプリのブラウザ自動操作（開発・回帰確認用のBrowser E2E Test Kitは別途あり）
- PH画像Safety Minimum Betaの範囲外の画像解析、成分表解析、HSA DB連携
- 商品画像・説明文編集
- fuzzy match
- 本格的な重複除去
- 優先順位スコアリング
- 価格分析、利益計算、在庫管理、分析、グラフ
- ログイン、DB管理画面、外部DB連携
- Chrome Remote DesktopやTailscaleなどのリモートアクセス機能

## Windowsでのセットアップ

PowerShellでこのフォルダを開き、以下を実行してください。

```powershell
cd shopee-expansion-tool
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
```

## APIキー設定

`config\.env.example` を参考に、プロジェクト直下に `.env` を作成してください。

```env
KEEPA_API_KEY=your_actual_keepa_api_key
```

ファイル名は必ず `.env` にしてください。`apikey.env` や `.env.txt` はアプリが読み込みません。

`.env`、`*.env`、`*.env.txt` は `.gitignore` に含めています。GitHubには含めないでください。

## 起動方法

```powershell
cd shopee-expansion-tool
.\.venv\Scripts\python.exe -m streamlit run app.py
```

ブラウザで表示された `localhost` のURLを開いて使います。

スマホからChrome Remote DesktopやTailscale経由で操作する可能性を考え、UIは縦並びにしています。ただし、Ver1ではリモートアクセス機能そのものは実装していません。

## 手動テスト手順

1. `.env` にKeepa APIキーを設定します。
2. `streamlit run app.py` で起動します。
3. ASINを1件入力します。
4. 最初は必ず検索ページ数 `1ページ` を選び、検索します。
5. brand、category、Product Finder totalResults、件数内訳、Guardrail件数、候補一覧、CSVダウンロードが表示されることを確認します。
6. 1ページが問題なければ、次に `3ページ`、最後に `5ページ` を確認します。

## Keepa APIトークン方針

- 最小プランの `20 tokens/min` を前提にしています。
- Product Finderは `perPage=50` で呼び出します。
- 商品検索は `1ページ = 50件` として扱い、最大 `5ページ = 250件` に制限しています。
- 推定消費トークンは、`入力ASIN商品情報 1 token + Product Finder検索ページ数 x 約11 tokens + 候補ASIN基本情報件数` で表示します。
- `offers`、`stock`、Buy Box詳細、seller情報、Best Sellers大量取得はVer1では使いません。
- トークン不足時はkeepaライブラリの `wait=True` により回復待ちします。アプリ画面にもその状態が分かるメッセージを表示します。
- Product Finderの通常条件がAPIエラーになった場合のみ、brandのみ、categoryのみの診断を行います。
- 検索結果0件はAPIエラーではなく、検索条件0件として画面に表示します。
- Product Finderが使えない場合は、既存SQLiteキャッシュ内の同一brand/category商品を代替候補として表示します。Amazon SP-API連携はVer1では実装していません。

## キャッシュ

- キャッシュファイルは `cache\keepa_cache.sqlite3` に作成されます。
- キャッシュキーにはASIN、検索ページ数、検索モード、domain、perPage、正規化brand、leaf/parent/root category ID、Product Finder query JSON hash、query_versionを含めます。
- 同じ検索条件の結果は7日間再利用します。
- キャッシュ利用時はKeepa APIを呼ばないため、トークンを消費しません。
- `cache/` と `*.sqlite3` は `.gitignore` に含めています。

## 自動テスト

Keepa APIを実際には呼ばず、モックでテストします。

```powershell
cd shopee-expansion-tool
.\.venv\Scripts\python.exe -m pytest
```

## Browser E2E Test Kit

合成fixtureを使い、外部APIを呼ばずにローカルで画面操作を検証する、開発・回帰確認用の手順です。Git管理する正本fixtureとChromeで選択する作業用コピーを分離し、起動、停止、入力準備、ダウンロード照合用のスクリプトを用意しています。詳細は [Browser E2E Test Kit手順](docs/testing/browser_e2e.md) を参照してください。

## Expansionの出品前保安ゲート用候補CSV

Expansion画面は候補を市場別に判断せず、出品前保安ゲートへ渡すための候補CSVを出力する。
このCSVは外部出品ツールへ直接渡さず、対象市場を選んだ出品前保安ゲートへ入力する。

CSV列は次の15列に固定している。

```text
schema_version,source_type,source_id,source_asin,candidate_asin,input_title,product_title,brand,category,amazon_url,source_status,source_verification,source,fetched_at,source_note
```

- `source_type` は `EXPANSION` または `RESOLVER` で、候補の入口を示す。出品先市場を示す列ではない。
- Resolverから渡すCSVには、`FOUND`かつ`KEEPA_VERIFIED`の候補だけを含める。
- Guardrailの `SAFE / REVIEW / BLOCK`、既出品照合、最終の `ELIGIBLE / REVIEW / EXCLUDE` は、この候補CSVの出力ではなく、対象市場を選んだ出品前保安ゲートで確認する。

GateはELIGIBLE CSV、REVIEW CSV、全件監査CSVを別途出力する。これらは外部出品ツールへの直接投入形式ではない。

### Ingredient Safety Fact sidecar

ExpansionとResolverは、固定15列の`PRELISTING_CANDIDATE_V1`を変更せず、対応する
`INGREDIENT_SAFETY_FACT_V1` sidecarを別CSVとして出力する。sidecarはCandidate CSVの最終bytesの
SHA-256と候補ASIN集合に結び付いており、Gateでは任意入力である。SHA、schema、ASIN集合、JSON cellが
一致しないsidecarは使用せず停止する。sidecarを指定しない場合は従来のCandidate V1だけで処理する。

PH Gateでは、取得済みの商品titleまたは成分Factに当社の正式BLOCK成分が確認された場合だけ、
Rule V2によりdeterministic BLOCKする。成分Factが`NOT_CAPTURED`または
`PROVIDER_UNSUPPORTED`であることは、成分不存在やSafety PASSを意味せず、その欠損だけでは
REVIEWまたはBLOCKにしない。PHのGABA ruleはアカウント保護のための当社運用上のBLOCKであり、
Shopee公式禁止物質であるという断定ではない。Keepaを本番標準、Canopyを明示設定時だけの
開発・試験専用providerとする方針は変わらない。

### Product Text Safety Fact sidecar

ExpansionとResolverは、Candidate CSVと同時に`PRODUCT_TEXT_SAFETY_FACT_V1` sidecarを出力する。
sidecarはCandidate最終bytesのSHA-256と候補ASIN集合に結び付けられ、`description`、`features`、
および既存provider応答に同名fieldがある場合だけ`shortDescription`、`safetyWarning`、
`itemHighlights`を保持する。追加のKeepa requestは行わない。

PHの通常Gate画面では、Candidate CSVに対応するProduct Text sidecarを必須入力とする。sidecarの
SHA、schema、ASIN集合、JSON cellが不正な場合は停止する。一方、Factの`NOT_CAPTURED`、
`NOT_AVAILABLE`、`PROVIDER_UNSUPPORTED`は文章未取得の状態であり、それ自体ではBLOCKまたは
REVIEWにしない。PHでは商品titleまたはProduct Textにliteral substring `hemp`があればBLOCKし、
`hemp-free`と`hempseed`も同じ境界に含む。CBD等の未承認aliasを推測追加せず、このRuleをSGへ
適用しない。既存Ingredient Safety sidecarとGABA matcherは変更しない。


### PH画像Safety Minimum Beta（DEC-0051 / DEC-0053 / DEC-0054）

PHでは候補CSV・既出品CSV・Product Text sidecarに加えて、Expansion / Resolverで候補と一緒に
ダウンロードした「PH画像確認ファイル」（JSON）を入力する。Candidateの固定15列は変更しない。

1. 「出品前チェックを実行」で既存Safetyと画像確認対象を確認する。対象商品の未実行、画像なし、
   処理失敗、疑義・判断不能は要確認となり、出品候補へ自動的に進めない。
2. 画像AIを利用する場合は、管理者がAPI利用設定を済ませ、画面の有料実行チェックを入れて
   「対象商品の画像AIを実行」を押す。通常の画面再描画・CSVダウンロードではAPIへ再送信しない。
3. 要確認の商品は「商品画像を開く」または別経路で十分な画像を確認し、判断根拠とともに
   「画像確認済み・準備継続」または「除外」を記録する。十分な画像を確認できなければ要確認を継続する。
   記録の取消も商品単位で行える。「画像確認記録をダウンロード」で結果を保存する。

原則対象は、おもちゃ `13299531`、ホビー `2277721051`、スポーツ＆アウトドア `14304371`、
DIY・工具・ガーデン `2016929051` とroot不明の商品。既存SafetyでBLOCK済みの商品、正常に識別した
その他root、Canopy test providerは未実行とする。未実行と「確認画像で疑義なし」は別表示とし、
どちらもSAFE保証や出品承認ではない。AI単独でBLOCKせず、人間の準備継続も画像以外のBLOCK / REVIEWを解除しない。

管理者設定は環境変数 `OPENAI_API_KEY` と `PH_IMAGE_SAFETY_API_ENABLED=1`。
既存のGit管理外 `.env` からも読み込める。設定・画面操作を伴わない自動API実行は行わない。
OpenAI Responses APIへ `gpt-5.6-terra`、`reasoning.effort=low`、`store=false`、Structured Outputsを指定する。
1商品最大3画像・原則1 requestとし、APIおよび各画像取得のtransient errorは各操作最大1 retry。
認証・契約・未対応設定等は画像AI開始前または判明時にGate全体をSTOPし、保存済み結果・出力も画面から除去する。
拒否・不完全応答・出力検証失敗は有効なAI結果なしの処理失敗として商品単位REVIEWへ送り、
AIが意味上の結果を返したようには扱わない。一部画像失敗は、残り画像のAI応答が疑義なしでも、
商品全体の画像確認結果を `INDETERMINATE`（判断不能）としてREVIEWを維持する。

既存Keepa商品応答の `categoryTree[0].catId`（treeなしでは `rootCategory`）と `imagesCSV` を保持する。
rootの不正値は画像Safety用には不明とし、整数へ丸めて対象外にしない。画像は元の順序で重複を除いた先頭3件。
既存cacheに画像情報がない場合は追加Keepa requestで補わず、対象商品を画像なしのREVIEWとする。
Amazon画像は許可した画像ホストから処理時だけ取得し、1画像5 MiB・2500万pixelまで、
JPEG / PNG / WEBP / 非アニメーションGIFを検証する。redirect、未対応形式、取得失敗は画像処理失敗となる。
画像bytesとbase64はメモリ内だけで使用し、画像本体・AI結果cacheは保存しない。`store=false`とAPI側の
データ保持契約は別であり、利用アカウントの設定は別途確認する。

専用sidecar `PH_IMAGE_SAFETY_V1` はCandidate最終bytesのSHA-256と完全一致ASIN集合に結び付く。
各行にroot・画像参照のFact、selector、実行状態、AI意味上の結果、使用画像のSHA-256・形式、
provider / model / prompt version・評価identity、人間判断とそのbindingを分けて記録する。
重複ASIN、schema・SHA・状態・人間判断bindingの不一致はGate STOP。同じ候補の確認記録は再読込できるが、
候補・画像Fact・評価を変えたときは古い人間判断を流用しない。画像AI再実行が必要な場合は元の画像確認ファイルから開始する。
JSONファイルは既存のCandidate / Ingredient / Product Text CSVと独立し、汎用sidecar frameworkは追加しない。
Gate CSVのheaderと既存status・reason codeは維持し、画像由来の理由だけを
`IMAGE_SAFETY_REVIEW` / `IMAGE_SAFETY_EXCLUDE` として既存reason_codes列へ追加する。

ローカル検証はsynthetic画像・mock HTTP・AppTestで行う。実API利用可否、画像取得品質、検出性能・実費、
実商品での人間受入は別確認であり、Gate P / PH Minimum BetaのHOLDを解除するものではない。

## 注意

- 入力ASIN自身と候補内の重複ASINは除外します。
- Expansion Tool単体では既出品ASIN照合と削除済みASIN履歴は未連携です。出品前保安ゲートでは、アップロードした既出品CSVとのASIN照合を行います。
- 価格や利益の良否判定はVer1では行いません。
- Expansion画面では出品可否を判定しません。SGを含む対象市場の出品可否は、出品前保安ゲートで対象市場を選んで確認してください。
- 起点ASINから `brand` または `category` が取得できない場合は処理を止めます。
- Keepa API仕様またはライブラリ都合で詰まった場合も、Web操作やスクレイピングへは切り替えません。
