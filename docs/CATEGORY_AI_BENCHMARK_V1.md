# Category AI Benchmark Ver1

## 目的と境界

この機能は、商品EvidenceからShopee Category Treeを階層探索する独立Benchmark Coreである。
現行Category Mapperの推薦を採点する機能ではなく、正式Category Mapper、AI Shadow、Safety、
Brand、Resolver、Expansion、Listing Toolの挙動を変更しない。AI predictionはCategory候補であり、
Safety判定、出品可否、Category確定を意味しない。

実装入口は `category_ai_benchmark_app.py`、純粋な判定Coreは
`modules/category_ai_core.py`、Responses API transportは
`modules/category_ai_openai.py`、CSV・Gold評価・料金は
`modules/category_ai_benchmark.py` に分離する。

## 固定Benchmark契約

- Prompt: `CATEGORY_AI_BENCHMARK_PROMPT_V1`
- Prompt SHA-256: `7fb5dfb95f3c9293b96acd1c50fbb382e12e4f715d0e77d0d7e93da3f587983d`
- Response schema: `CATEGORY_AI_BENCHMARK_RESPONSE_SCHEMA_V1`
- Traversal: `HIERARCHICAL_TRAVERSAL_V1`
- Request profile: `CATEGORY_AI_BENCHMARK_REQUEST_PROFILE_V1`
- Request profile config: `config/category_ai_benchmark_request_profiles.json`
- Price config: `config/category_ai_model_prices.json`

固定Prompt本文は `modules/category_ai_prompts.py` の1か所だけに置く。V1本文を変更せず、
将来の改善は新しいPrompt Versionとして追加する。

`benchmark_request_profile`には次を固定し、各Predictionへ全体とSHA-256を保存する。

- exact model ID
- `reasoning_effort`
- text `verbosity`
- `max_output_tokens`
- `service_tier`
- timeout
- providerとendpoint
- `store=false`
- stream、truncation、tool choice、parallel tool call
- Prompt、response schema、traversal、profileの各version

モデル比較ではexact model IDだけを変更できる。その他すべての条件から作る
`comparison_contract_hash`が一致しない結果は比較対象にしない。各モデルのprofile自体は
不変のversioned recordであり、比較途中に上書きしない。

Benchmark V1の比較対象は `gpt-5.6-terra` と `gpt-5.6-luna`、共通条件は
`reasoning_effort=low`、`text_verbosity=low`、`max_output_tokens=512`、
`service_tier=default`、timeout 30秒である。暗黙のmodel fallbackは行わない。

料金設定は2026-09-11時点のdefault service tierをversion管理する。料金は実usageから
再計算可能であり、算定額は請求額そのものとは断定しない。参照した公式仕様は
[GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra)、
[GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)、
[Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)である。

## 入力契約

Source CSV必須列:

- `case_id`
- `product_title`

任意列:

- `marketplace`
- `asin`
- `keepa_category`
- `keepa_brand`
- `resolver_title`

余分な列はAI入力に渡さない。APIのproduct部分は上記4 Evidence fieldだけを明示的に生成する。
Mapper推薦、status、canonical product type、Domain、Mapper confidence、過去の選択、Gold、
期待Category、評価結果を渡さない。

Catalog snapshot CSV必須列:

- `category_id`
- `parent_category_id`（rootは空）
- `category_name`
- `category_path`
- `is_leaf`

Marketplaceとcatalog versionはUIで明示する。CoreはPH固有IDを持たず、PH / SG / MY / THの
catalog差替えに対応する。重複ID、親欠損、cycle、leaf矛盾、path矛盾を拒否し、正規化した
catalog全体のSHA-256をPredictionへ保存する。

正式Gold CSVは最低限 `case_id`、`asin`、`expected_category_id`、
`expected_category_path`、`truth_status` を持つ。`CONFIRMED`は固定Catalog上の実在leaf IDと
一致するpathを必須とし、`ABSTAIN_REQUIRED`はID / pathを空欄必須とする。`UNCONFIRMED`と
未定義statusは正式Benchmarkで拒否する。Source / Goldのcase ID・ASINは全件一致し、双方の
重複を拒否する。

処理順はSource、全Prediction生成・個別hash固定、Prediction batch hash固定、Gold parse、
Evaluatorの順である。Gold object、expected Category、truth statusはCore、Provider、Prompt、
Traversal requestへ渡さない。

## Gold採点契約

`CONFIRMED`に対するexact `SELECT`は`CORRECT_SELECT`、別leafの`SELECT`は
`WRONG_CATEGORY`、`ABSTAIN`は`FALSE_ABSTAIN`とする。`ABSTAIN_REQUIRED`に対する
`ABSTAIN`だけを`CORRECT_ABSTAIN`とし、どのleafを`SELECT`しても候補・代替との近さに
かかわらず`OVERCONFIDENT_SELECT`とする。Provider / API / Traversal異常は`FAILED`であり、
ABSTAINと混同しない。

主要指標は全商品を分母とするend-to-end `overall_success_rate`である。併せて
`confirmed_exact_accuracy`、`abstain_accuracy`、`select_precision`、各誤り件数、token、
cost、API call、latencyをmodel別に集計する。FAILEDがある場合だけ、FAILEDを除外した
completed-decision success rateを参考値として併記し、主要指標の代替にはしない。

## 階層探索とstep記録

各商品を独立してrootから開始し、現在parentの直接childだけを候補として1回のResponses
requestへ渡す。`SELECT`した対象がnon-leafなら次のchildへ進み、leafなら完了する。
`ABSTAIN`または異常ならCategoryを確定しない。別商品のEvidenceや結果は共有しない。

各stepには次を保存する。

- step index
- parent category IDとpath
- 候補数
- decision
- selected category ID、name、path、leaf状態
- confidence
- reasonとproduct type summary
- step単位token usage、API call数、latency、応答service tier

最終 `prediction_confidence` は、`SELECT`した全stepのconfidenceの最小値とする。rootで
ABSTAINした場合は選択stepがないためnullとし、ABSTAIN step自身のconfidenceはstep記録に残す。
このconfidenceは100件Benchmarkで信頼性を検証する対象であり、当面Category確定、
自動承認、Safety判断の閾値には使用しない。

## Fake Provider合格と実AI精度の区別

Fake Providerは台本どおりの構造応答を返すだけで、自然言語の意味理解を行わない。

mock testで確認するもの:

- Prompt本文と許可fieldだけから作る入力
- root → child → leaf、leaf、ABSTAIN
- current candidates以外のID拒否
- 架空ID、JSON、schema、空応答、timeout、HTTP、rate limit相当のfail closed
- step trace、token、cost、profile、Prompt Version、prediction hashの保存
- PH / SG合成catalogで同じCoreが動くこと
- Gold非混入と、Prediction固定後の評価
- Streamlit画面の初期表示

mock testで確認しないもの:

- `product_title`を意味的に優先できたか
- `resolver_title`が実際の判断を上書きしなかったか
- Tabletをelectronicsへ誤分類しない精度
- Powderをmakeupへ誤分類しない精度
- main product / accessory / replacement / setの意味的識別精度
- confidenceの校正・信頼性

後者は実OpenAI APIによる3〜5商品smoke、35件、100件Benchmarkで初めて評価する。
Promptに安全制御が存在することと、モデルが意味的に正しく従うことを同一視しない。

## Fail closed

候補外ID、存在しないID、JSON/schema違反、refusal、不完全・空応答、model不一致、
timeout、network、HTTP、rate limit、usage不整合、catalog/traversal矛盾ではCategoryを
確定しない。既存Mapper結果へのfallbackは存在しない。UIはFAILEDを検知した時点で
後続商品の実行を停止する。

`OPENAI_API_KEY`はprocess environmentまたはproject直下の `.env` からだけ読む。
UI、CSV、DB、ログ、例外本文へcredentialを保存しない。raw OpenAI responseは保存せず、
検証済みstructured resultとusageだけをPredictionへ残す。

## UIと出力

起動:

```powershell
.\.venv\Scripts\python.exe -m streamlit run category_ai_benchmark_app.py
```

Marketplace、Source CSV、Catalog snapshot、catalog version、Model、件数、任意Goldを指定する。
結果画面は件数、ABSTAIN、API calls、推定cost、Prediction表、CSV downloadを表示する。

Prediction CSVには商品・model/provider・Prompt/catalog/profile・最終Category・ABSTAIN・
confidence・reason・usage・calls・latency・cost・price version・全step JSON・prediction hashを
保存する。Goldを指定した場合だけGold status、expected Category、model decision、採点outcomeを
後段で追加する。Prediction batch hashもGold読込前に固定する。

## Benchmark V1の完了判断

固定100商品でLuna / Terraの実API比較を完了した。Lunaはoverall 81%、CONFIRMED exact
79/92（85.87%）、Hobbies & Collections 0/10、実コストUS$0.12669125だった。Terraはoverall
82%、CONFIRMED exact 79/92（85.87%）、Hobbies & Collections 0/10、実コストUS$1.202226で、
精度差が小さい一方、Lunaの約9.5倍だった。

Minimum BetaのCategory候補提示には`gpt-5.6-luna`を採用する。Terraは不採用、Solは検証しない。
AIによるCategory自動確定は禁止し、Hobbies & Collectionsは既知弱点として必ず手動確認する。
Prompt V1、Traversal V1、Hobbies改善はこの完了タスクでは行わず、実運用でボトルネックになった
場合だけ別Versionとして検討する。追加のBenchmark実API実行、正式Category Mapper統合、push、PR、
mergeはこのタスクでは行わない。
