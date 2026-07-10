# Shopee Expansion Tool Ver1

ASINを1件入力し、Keepa APIから `brand + category` 基準の候補ASINを取得して、画面表示とCSVダウンロードを行うローカルWebアプリです。

KeepaのWeb画面操作、Amazonページ操作、Amazon/Keepaスクレイピングは行いません。

## Ver1でできること

- ASIN 1件を入力
- 検索モードを `strict / standard / broad / category_research` から選択
- 検索ページ数を `1ページ / 3ページ / 5ページ` から選択
- Keepa APIで起点ASINの商品情報を取得
- 起点ASINの `brand` と `categoryTree` を使って候補ASINを取得
- 結果を画面表示
- Guardrail Filter Ver1.1で `SAFE / REVIEW / BLOCK` を分類
- 出品候補CSV（SAFEのみ）と監査用CSV（SAFE / REVIEW / BLOCK 全件）をダウンロード
- 入力欄、検索モード、検索ページ数、検索ボタン、CSVダウンロードボタンを縦並びで表示
- 同じ検索条件の結果はSQLiteに7日間キャッシュ

## ASIN Resolver Tool Ver0.1

ASIN Resolver Tool Ver0.1は、Expansion Tool内に追加した独立補助機能です。

商品名リストから外部AIへ貼り付けるためのプロンプトを生成し、ChatGPTやGeminiなどの外部AIが返したCSVを手動で貼り付けて解析します。

Amazon.co.jp URLからASINを抽出し、Keepa APIでASINの実在確認を行います。確認結果は画面表示とCSVダウンロードに使えます。

ASIN Resolver Tool Ver0.1は、Expansion Toolへの自動投入は行いません。Shopee API連携、自動出品、Amazonページ操作、ブラウザ自動操作も行いません。AI APIやGemini APIをアプリ内部から自動呼び出しする機能ではありません。

## Guardrail Filter Ver1.1

Guardrail Filter Ver1.1は、Shopeeアカウント保護のための一次フィルターです。

売上最大化や利益最大化を目的にした機能ではありません。アカウント停止、警告、出品削除、ペナルティにつながりそうな商品や、人間確認が必要な商品を通常の出品候補CSVから分離するための機能です。

Keepa APIで取得済みの `product_title`、`brand`、`category` だけを使って、CSV辞書ベースで判定します。AI判定、Web検索、Shopee API連携、Keepa APIの追加呼び出しは行いません。

判定ステータスは以下の3種類です。

- `SAFE`: 現時点の辞書ルールに一致しなかった候補です。出品安全を保証する意味ではありません。
- `REVIEW`: 人間確認が必要な候補です。通常の出品候補CSVには含めません。
- `BLOCK`: アカウント保護のため通常の出品候補CSVから除外する候補です。

Guardrail辞書が存在しない、壊れている、必須列が不足している、不正値がある場合は、全件SAFEにはしません。画面にエラーを表示し、候補一覧とCSVダウンロードを停止します。

### Guardrail辞書

辞書CSVは `guardrails` フォルダにあります。

- `guardrails/prohibited_brands_sg.csv`
  - Shopee SG向け禁止・高リスクブランド辞書です。
  - `brand` フィールドへの exact match のみ許可しています。
  - `title` や `category`、`contains` が入っている場合はエラーになります。

- `guardrails/risk_keywords_sg.csv`
  - Shopee SG向け禁止語・要確認語辞書です。
  - `title / brand / category / all` に対して、`exact / contains` で判定します。

両CSVの列は以下に固定しています。

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

辞書CSVを編集した場合、Keepa APIの再取得は不要です。同じ検索結果でも、画面を再読み込みまたは再検索すれば最新辞書で再判定されます。

## 検索モード

- `strict`: brand + leaf category ID。初期値。精度重視です。
- `standard`: brand + parent category IDを優先します。parentが取れない場合はrootCategoryを使います。
- `broad`: brand only。候補数重視ですが、カテゴリ外商品が混ざる可能性があります。
- `category_research`: category only。同カテゴリ市場調査用です。

## Ver1で実装しないこと

- アプリ内部からのAI API / Gemini APIの自動呼び出し
- AI返答の自動取得
- ASIN Resolverの結果をExpansion Toolへ自動投入
- Shopee API連携
- 自動出品
- 自動削除
- 既存ASIN照合
- 削除済みASIN履歴
- AI危険判定、LLMによる商品分類
- Web検索、Shopee規約の自動取得
- Keepa APIの追加取得
- Keepa Web画面操作、Amazonページ操作、スクレイピング
- ブラウザ自動操作
- 画像解析、成分表解析、HSA DB連携
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

## 出力CSV

CSV列は以下に固定しています。

```text
seed_asin,candidate_asin,brand,category,product_title,source,token_estimate,fetched_at,duplicate_flag,note,guardrail_status,guardrail_risk_category,guardrail_matched_terms,guardrail_source,guardrail_note
```

取得できない項目は空欄になります。

Guardrail列の意味は以下です。

- `guardrail_status`: `SAFE / REVIEW / BLOCK` の判定結果
- `guardrail_risk_category`: 一致したリスク分類
- `guardrail_matched_terms`: 一致した辞書語
- `guardrail_source`: 一致した辞書ルールの情報源
- `guardrail_note`: 判定理由の補足

出力CSVは2種類です。

- 出品候補CSV: `SAFE` のみ。`REVIEW` と `BLOCK` は含めません。
- 監査用CSV: `SAFE / REVIEW / BLOCK` すべてを含めます。

## 注意

- 入力ASIN自身と候補内の重複ASINは除外します。
- 既出品ASIN照合と削除済みASIN履歴はVer1では未連携です。画面では `未適用（Ver1では未連携）` と表示します。
- 価格や利益の良否判定はVer1では行いません。
- Guardrailの `SAFE` は安全保証ではありません。現時点のSG辞書ルールに一致しなかったという意味です。
- `REVIEW` は通常出品フローから分離し、出品前に人間が確認してください。
- `BLOCK` は出品候補CSVから除外されます。
- 起点ASINから `brand` または `category` が取得できない場合は処理を止めます。
- Keepa API仕様またはライブラリ都合で詰まった場合も、Web操作やスクレイピングへは切り替えません。
