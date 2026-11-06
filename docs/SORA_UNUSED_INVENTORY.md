# Soraの未使用候補・テスト棚卸し

2026-11-07の読取調査。**削除対象の提案であり、削除の承認・実施記録ではない。**
本調査の変更はこの文書だけとし、製品コード、テストの選別、判定辞書、CI、設置版を変更しない。

## 結論

- 正式版の通常入口は `app.py:2008` → `render_sora_app()`。旧 `render_application()` はこの経路から呼ばれない。
- ただし旧画面のimportが `app.py` の先頭に残っており、画面を開かなくてもCategory Mapper等を読み込む。まずこの依存を外す工程が必要で、ファイルを先に削除できない。
- Resolver・Keepa・家電分類・画像関連は、名前だけで一括削除できない。ASINの整形・確認結果の搬送、家電の停止判定、保護テスト等が同じファイルを利用している。
- 旧機能専用1,203ケースは既に通常CIから除外済み。削除しても、そのケースの実行時間は減らない。
- 大きな短縮候補は旧画面・P5等の混在テスト。ただし共通の安全確認が含まれるため、同じ確認を小さな回帰テストへ移してから旧部分だけを削除する。

## 1. 調べた版・方法・限界

|対象|読取結果|
|---|---|
|正式repository|`hagiwara777/shopee-expansion-tool`|
|実際の「Sora起動.cmd」の設置先|独立cloneの `main`、`13eeb811bcbee06dfadf4fa7a9649e1bc97ee38b`、変更なし|
|cmdの起動内容|その正式版フォルダへ移動し、既存Pythonで `streamlit run app.py`、ポート8510。別のベータ起動scriptを経由しない|
|調査基準の採用済みmain|`47576e885afb48eb2d0bad7bbe7a1ba2b6b6dd9b`（#167取り込み）|
|mainの商品・テストtree|`a05acd57e12cc7200369d8444eac4f8c6c68e588`。#167の成功CI対象 `d9919e0e026892b2d05ee78b282c597f3a7ebfdf` とtree一致|
|設置版との製品コード差|`app.py` と他の製品moduleは同一。`modules/sora_ui.py` の入口だけに差があり、設置版はResolverも選択可能、mainはASIN貼付／FROMAX CSVの2択|

設置版をmainへ更新したとは扱わない。**Resolverの画面・CSV取込は、実際の設置版ではまだ利用可能**である。
以下で「通常呼出しなし」とするResolver部分は、mainの2つの入口を基準にする。
設置版での利用差がある行は個別に記す。mainでコード保全を定めたDEC-0172も維持する。

Git管理のPython 248ファイル（`modules/` 104、`test_*.py` 123、その他21）、
`scripts/` 28ファイル、Google Apps Script 2ファイルとJavaScriptテスト2ファイルを確認した。
PythonはASTのimport・関数参照、呼出元の逆引き、条件分岐を確認した。
通常操作、import時、旧画面だけの遅延importを区別した。動的なprocess観測を使うP5も検索した。
正式版の起動・停止・画面操作、実API、認証ファイル・鍵・Anchorの読込は行っていない。
インストール済み環境でのテスト**収集のみ**を行い、実行結果の時間は同じtreeの既存CIから集計した。

これは静的調査であり、実プロセスの網羅的な呼出しトレースではない。
外部での手動CLI利用・別ショートカット・Git外の利用者までは否定できない。
import連鎖の表は関数内の条件付きimportも含めた保守的な依存であり、「全機能を実行した」という意味ではない。
実測のない起動高速化・削除後のCI時間は成功値として扱わない。

## 2. 通常の起動・処理経路

```text
Sora起動.cmd → 既存Python / Streamlit → app.py
  ├─ 先頭の旧画面用importも評価（下記の残存依存）
  └─ __main__ → modules.sora_ui.render_sora_app
       ├─ sora_version：起動中のGit版表示
       ├─ sora_input：ASIN貼付／FROMAX Keepa CSV、形式・重複・500件上限
       ├─ asin_resolver.preview_candidates：直接入力ASINの共通行形式への整形
       ├─ sora_acquisition → sp_api_catalog：明示ボタン後だけ取得／同じ入力内の残件再開
       │    └─ asin_resolver.verify_preview_rows：取得結果と候補・成分・文章の結合
       └─ sora_run.prepare_sora_run → prelisting_candidate_csv ＋ 成分・文章資料
            ├─ listing_inventory_parser：任意の既出品照合
            ├─ prelisting_sg_body_safety ＋ 同UI：SGの本体確認
            └─ evaluate_sora_run → prelisting_gate → guardrails
                 ├─ 共通・国別・個別ASIN方針、成分・文章、電池、ブランド、家電
                 └─ sora_exports ＋ prelisting_gate_uiの行整形 → 4種類の出力
```

### 残す製品module（mainの通常操作で関数・型・定数を使う25ファイル）

|用途|ファイルと利用根拠|
|---|---|
|Sora画面・入力・取得・判定接続・版|`modules/sora_ui.py`、`sora_input.py`、`sora_acquisition.py`、`sora_run.py`、`sora_version.py`。上記の入口、状態破棄、残件、4出力を担当|
|SP-API|`modules/sp_api_catalog.py`。計画回数、取得、応答整形。今回これを実行しない|
|共通のASIN行・資料搬送|`modules/asin_resolver.py` の `preview_candidates`／`verify_preview_rows` とそのparser、`prelisting_candidate_csv.py` の変換・資料一致検証|
|小さな共通依存|`modules/keepa_client.py` の `normalize_asin`、`amazon_data_provider.py` の例外型・provider定数。Keepa／Canopyの通信clientを使う意味ではない|
|入力資料・Gate・表示|`modules/ingredient_safety.py`、`product_text_safety.py`、`listing_inventory_parser.py`、`prelisting_gate.py`、`prelisting_gate_ui.py` の表示行・翻訳処理|
|SG本体確認|`modules/prelisting_sg_body_safety.py`、`prelisting_sg_body_safety_ui.py`。現在の候補・文章と確認を照合|
|保安判定|`modules/guardrails.py`、`safety_policy.py`、`ingredient_text_sections.py`、`battery_presence.py`、`brand_monitoring.py`、`community_ng.py`、`match_context.py`|
|家電停止の共通rule|`modules/home_appliances_classifier.py` の `classify_owned_text` 等。独立した家電ファイル分類画面を使わなくてもGateが利用|

ファイル名を省略したセルも直前の `modules/` 配下を表す。`modules/__init__.py` はpackageの入口として残す。
設置版でResolverを選ぶ場合には、さらに `research_csv_adapter.py` と
`asin_resolver_evidence.py` のsource入力parser等を使う。
`ph_image_safety.py`／`image_inspection_policy.py` は共通importに残るが、
`asin_resolver._verified_row` はSP-APIの場合に画像Fact生成をスキップする。画像AI通信を使う経路ではない。

### 起動時に残る依存

明示されたmodule直下のimportを辿ると、packageの暗黙の `__init__.py` を除き、`app.py` を含む63 Pythonファイルが到達候補になる。
これは上記25ファイルに加え、旧Mapper UI、Category AI、Shopee client、画像UI、Evidence、Keepa cache等を含む。
例えば `app.py:42` の `render_category_mapper_tab` のimportだけでも、
`category_mapper_ui` → `category_mapper`／`category_mapper_sg_ui` → SLS・Brand・AI等が読み込まれる。
旧画面を呼ばないことと、ファイルを読み込まないことは異なる。

`app.py` の `render_application` と専用helperのbodyには通常経路から入らない。
ただし `app_beta.py` がこれを呼び、既存AppTestも直接利用する。
後の削除PRでは、Sora用の入口を保ちながら旧関数・旧import・その呼出元を同時に整理する。

## 3. 機能別の削除候補・保留事項

各ファイルの読込・逆依存は末尾の一覧も参照する。「候補」は次の削除PRで確認・承認する対象であり、現時点の削除可とはしない。

|対象|通常使わないと言える根拠|Sora・保安・保護への依存／削除の前提|
|---|---|---|
|`app.py:926` の `render_application` と旧Resolver／Expansion／Gate画面helper|`__main__` が呼ぶのは `render_sora_app` だけ|`app.py` 自体と新入口は残す。`app_beta.py` と直接AppTestが旧関数を利用。旧importから共通保安まで巻き込まない|
|`app_beta.py`／`app_sg_beta.py`／`app_sg_candidate.py`|正式cmdの起動先でない。専用launcher・旧画面の別経路|通常Soraからの呼出しなし。ただし旧環境・専用runtime・active混在テストが利用。外部での手動利用は未確認|
|`category_ai_benchmark_app.py`|独立Streamlit page。通常cmdも `render_sora_app` も参照しない|専用UIテストは既にretired。共用AI module・設定はMapper等のimportにも残るので同時に全削除しない|
|Category Mapper UI・カテゴリ候補画面|`render_application`／別アプリだけから表示|`tests/test_sls_category_protected.py:9` が `category_mapper_ui._group_progress_label` を直接使用。UIファイル丸ごと削除は保護チェックを壊す|
|Category／Brand backend、保存store、SG準備出力|通常SoraはCategory ID／Brand ID確定を行わない|SLS保護回帰の入力型、評価、ready判定、停止、出力閉鎖が依存。安全部分を独立させるまでは保留|
|Category AI Core／OpenAI／Benchmark／Keepa runner|通常Soraの関数呼出しにない|Mapperの先頭import、共通取得失敗時停止のactiveテストが残る。AI通信削除と安全確認削除を同一視しない|
|`sora_ui._render_resolver`、Shopee調査CSV取込UI|mainのradio・呼出しから外れている（DEC-0172）|設置版には入口がある。設置更新を前提にする。`asin_resolver.py` は直接ASIN入口も利用するため丸ごと削除不可|
|`asin_resolver_evidence.py` の永続Evidence Batch|Soraの通常出力はその回のCSV／TXT／JSONであり、Batch操作を呼ばない|同ファイルのsource入力parserをResolverがimport。設置版の手作業Resolverでも使う。parserと永続処理を切り分ける|
|Keepa Expansion、Canopy、cache、価格・評価filter|Soraの商品取得はSP-APIのみ。旧factory・旧画面だけの通信|`keepa_client.normalize_asin` は現在も多数の保安moduleが使う。成分・文章の搬送や予算のactiveテストも保持。共通関数を先に分離|
|P5のtrusted起動・許可・台帳・Windows観測・更新・UI|Sora入口はP5のinitializer／runtimeを起動しない|既存の停止条件・資料同一性・反復受入テストが混在。専用の運用データ・設置先・記録は削除対象外|
|P1〜P4、準備pool、5状態、product review、分類確認|SoraはFROMAXへ通過ASINを渡し、これらの画面・保存を使わない|Category／SLS保護、既存Safetyの非解除、資料の失効回帰が依存。backendを一括削除しない|
|PH画像UI／画像API／武器画像検査|現在のSora画面は画像入力・画像AI実行を表示しない|画像Fact型が共通importに残り、旧のSLS／出力保護にも依存。API専用46ケース等はretired。Fact型・既存停止を別に扱う|
|SLS Categoryのasset loader／PH・SG evaluator|新Soraは正式なCategory別配送可否を確定しない|`protected.ph`／`protected.sg` の回帰が直接使用。**保護対象として残す**。現在のSoraのSLS禁止語方針と共有Batteryも残す|
|家電ファイル分類CLI・`home_appliances_files.py`|通常画面から起動せず、保存ファイル入力の独立CLI|CLI側だけが候補。共通 `home_appliances_classifier.py` は現在の家電停止に必須。既存70 activeケースも安全ruleとの混在を確認して分ける|
|Safety Shadow・比較UI・report CLI|旧Gate helperからだけ呼ぶ任意の読取比較で、Soraの通常Gateには接続しない|Gate判定本体を削除しない。`test_safety_shadow_comparison_ui.py` のhelperを `test_expansion_gate_handoff.py` がimportするため、テストファイル削除前にhelperを保全|
|FROMAX向けNG語句出力UI|旧Gate画面の `fromax_ng_ui` だけ。現在の4出力から呼ばれない|`fromax_ng_export.py` は `test_brand_monitoring.py` が辞書境界の確認にも使用。UIだけと辞書のexport検証を分ける|
|`prelisting_gate_csv.py`／`prelisting_gate_handoff.py`|新Soraの4出力は `sora_run.sora_exports`。旧CSVとExpansion引継ぎは旧画面用|旧Gate CSV parser／書式はMapper・保護回帰が利用。共通成分・文章一致も混在。名前だけで全削除不可|
|Google Apps Script `Code.gs`／`SgSync.gs` と専用JSテスト|Shopee token／Bridge用でSoraのSP-API経路から参照しない|Pythonの通常CIはJSテストを呼ばない。外部設置の削除・変更は別境界。本棚卸しはrepository内だけ|
|Governance・開発検証script|商品画面から呼ばれない|CI・PH／SG保護・Owner手動mergeの必須確認が使用するため、未使用製品コードと区別して**残す**。旧署名実装・過去記録もDEC-0173に従って保全|

判定資産 `guardrails/` は削除候補にしない。`policy/`、`brand_monitoring/`、`community_ng/`、
市場別辞書、`deterministic_block_rules_v2.csv`、`sls_shared/` は現在のGateが使う。
`sls_market_categories/` は通常Soraの画面で使わなくても保護回帰が使う。
旧出力の `modules/export_csv.py` も、`tests/test_guardrails.py:9` が `rows_to_csv` を直接利用する。
専用の旧出力テストを整理する場合でも、保護回帰が使う関数・安全列の確認は残す。
Benchmark専用の `config/category_ai_benchmark_request_profiles.json`／`category_ai_model_prices.json` は、
AI module・旧UIの依存を外した後に検討する。認証用の設定例、依存package、既存データ・履歴の削除を本報告から推定しない。

## 4. テスト件数・時間の見込み

### 基準となる実測

成功済み [CI run 42202066478](https://github.com/hagiwara777/shopee-expansion-tool/actions/runs/42202066478) の
`test-timing`（artifact ID `13495822101`、`sora-active.xml`）を集計した。
runのheadとmainのtreeが一致すること、123テストファイルのactive件数が今回のcollectionと全件一致することを確認した。
今回のcollectは既存Python環境、CIはWindows／Python 3.12。同じ環境での新規全体実行とは区別する。

|計測対象|件数・時間|
|---|---|
|Sora全範囲のcollectionのみ|4,570ケース、収集成功（テスト本文は実行しない）|
|通常active|3,367ケース。基準CIは3,365成功・2skip・失敗0|
|retired|1,203ケース。通常CIからdeselected。今回実行せず、成功・skipに数えない|
|retiredだけのテストファイル|24ファイル、497ケース。残る706 retiredケースはactiveも含むファイル内|
|Soraのpytest実測|955.620秒（15分55.620秒）。各testcase時間の和は950.580秒で、収集等の差がある|
|Sora CI step|16分00秒。`tests.offline`ジョブ全体17分17秒|
|共通API部品の別step|`commerce-api-core` 40成功、pytest 1.086秒。Sora件数と分ける|
|CI全体の経過|17分25秒（作成から完了、2026-11-06 10:21:38〜10:39:03 UTC）|
|PH／SG保護job|4ファイル812ケース。基準runはjob成功。テスト対象も必須checkも削減しない|

### 削除案ごとの見込み（未実施）

|案|テスト件数の変化|CI時間への見込み|
|---|---|---|
|今回の文書だけのPR|active 3,367＋共通部品40のまま。削除0|短縮なし。上記は過去の同treeの実測で、本PRの実行時間ではない|
|retiredだけの24ファイルを整理|allは497減って4,073。activeは3,367のまま|テスト本文の短縮0秒。collection／importの差だけは未計測。selector・他テストの参照を同時に整える必要あり|
|retiredの1,203ケースを全て整理|allは3,367。activeは3,367のまま|本文の短縮0秒。混在ファイルはactive部分を残すのでファイル単位で消さない|
|旧clipboard補助・旧export・Canopy・Shadow専用の6テストファイルを将来整理|active計209ケースが見直し候補。単純差引きは3,158＋共通部品40|基準のcase時間合計3.959秒。仮に全て純減なら全体17分25秒から約4秒減る程度。Shadow UIの共通helperは移す必要があり、純減は未確定|
|重い混在4ファイルの旧画面往復を小さな安全回帰に置換|66 activeケースが対象。残す／置換する確認数は設計後に確定|既存case時間合計513.571秒（8分33.571秒）が見直し範囲の上限目安。**全量を削れる時間ではない**。置換後の測定が必要|

上記6ファイルは `test_direct_chat_assist.py`（22）、`test_export_csv.py`（2）、
`test_canopy_client.py`（12）、`test_safety_shadow.py`（120）、
`test_safety_shadow_comparison.py`（51）、`test_safety_shadow_comparison_ui.py`（2）。
これは削除済み／削除許可済みの集計ではない。既存のSafety非解除等の共用確認とhelperを移した後の候補である。

重い混在4ファイルは次のとおり。DEC-0163で意図して残したSafety／資料搬送の確認を落とさずに分解する。

|ファイル|active|基準case時間の和|残す確認|
|---|---:|---:|---|
|`tests/test_practical_beta_p4_ui.py`|4|343.179秒|市場切替、再起動後の資料同一性、Resolver受渡し、安全停止非解除|
|`tests/test_p5_acceptance_rehearsal.py`|6|76.205秒|現在資料・明示確認、UNKNOWN保持、重複出力防止、予算・履歴|
|`tests/test_p5_candidates.py`|20|42.138秒|成分・文章の世代対応、出所・同一性、分類で停止を解除しない|
|`tests/test_sg_continuous_operation.py`|36|52.049秒|有限送信予約、実消費、UNKNOWN保持、既存停止|

ケース時間の差引きは将来の予測であり、削除後の全体CI実測ではない。
runnerのばらつき、import・fixture・収集、置換テスト、他jobの所要時間により変わる。
特に「旧機能テストを全部消せば8分34秒短縮」とは判断できない。

## 5. 後続PRの順番案

1. **入口とimportの分離**：`app.py` の新入口を残し、旧 `render_application`、旧画面helper、先頭の旧importを整理する。
   別アプリと旧AppTestの呼出元も同時に扱う。Resolverは設置版との違い・DEC-0172の保全方針を先に確認する。
   共通のASIN整形・Fact搬送・Gate・版表示は残す。短縮値はまだ約束しない。
2. **独立した旧画面・起動script・末端の機能**：Benchmark page、clipboard補助、旧export、Shadow等を小分けにする。
   別ベータの起動先を廃止する単位で `app_beta.py`／SG別アプリと専用Start・Stop・Shortcutを整理する。
   retired専用テスト／専用fixtureは、他テストからのimport・文字列参照を外した同じPRに限って削除候補にする。運用データ・過去記録は残す。
3. **Resolver・Keepa・画像・P5等の共有部品の切分け**：`normalize_asin`、候補行、取得済み資料の搬送等を残し、
   通信client・永続Batch・旧画面専用部分を順に外す。重い混在テストは安全確認を小さな回帰へ移し、前後の件数・時間を測る。
4. **Category／Brand／SLS依存は最後**：SLS保護テストが必要とする型・ready条件・出力停止・市場分離を独立させる。
   `protected.ph`／`protected.sg` の意味・対象の安全条件と必須CIを維持したうえで、残るUI／backendの削除範囲を別途提示する。
   安全機能や旧受入済みcapabilityの廃止を本棚卸しだけで承認したことにしない。

各PRは小さな目的・削除一覧・残す共通部品・該当回帰・通常CI・差分確認を揃え、OwnerがGitHubで取り込む。
Codexはmergeしない。正式版の更新・再起動、実商品／500件の確認、鍵の利用はこの順番案に含まない。
新しい恒久判断を採る場合に限り、該当PRで新Decisionを追加する。今回は調査結果だけなので既存Decisionを変更しない。
実際にコード・旧テストを削除する場合は、DEC-0163／0165／0172等の保全方針を置換する対象と、残す履歴・安全条件をそのPRで明記し、Ownerの判断を得る。

## 6. ファイル別付表の読み方

次の表の「起動import」は、mainの `app.py`／`sora_ui.py` からmodule直下のimportを辿った結果。
「保護依存」は、必須の4保護テストから全import（関数内も含む）を辿った保守的な依存。
`有` はそのままファイルを消せない根拠。`—` も手動利用まで否定するものではない。
関数名・定数参照を確認した通常の25ファイルとpackageの `__init__.py` は候補表から除く。
「参照元例」は実際のimport箇所で、全呼出元を網羅する表示ではない。

### 6.1 通常呼出しがないmodule候補（78ファイル）

|ファイル|用途・保留理由|起動import|保護依存|参照元例|
|---|---|:---:|:---:|---|
|`modules/asin_resolver_evidence.py`|Resolver永続Batch／source parser（設置版利用あり）|有|有|`app.py:23`、`modules/asin_resolver.py:13`|
|`modules/beta_environment.py`|旧P5／専用起動・実行環境|—|—|`tests/test_beta_application.py:137`|
|`modules/beta_runtime_paths.py`|旧取得・設定・cache・filter・出力|有|有|`app.py:51`、`modules/cache.py:10`|
|`modules/beta_work_store.py`|旧準備・分類・永続保存（安全回帰と混在）|—|有|`modules/beta_workbench.py:16`、`modules/classification_workflow.py:13`|
|`modules/beta_workbench.py`|旧準備・分類・永続保存（安全回帰と混在）|—|—|`modules/classification_workflow.py:12`、`modules/classification_workflow_ui.py:9`|
|`modules/brand_confirmation.py`|旧Category／Brand（SLS保護依存を保持）|有|有|`modules/category_mapper_sg_ui.py:9`、`modules/category_mapper_ui.py:12`|
|`modules/cache.py`|旧取得・設定・cache・filter・出力|有|有|`modules/canopy_client.py:13`、`modules/keepa_client.py:10`|
|`modules/candidate_filter_ui.py`|旧取得・設定・cache・filter・出力|有|—|`app.py:119`|
|`modules/candidate_filters.py`|旧取得・設定・cache・filter・出力|有|有|`modules/candidate_filter_ui.py:6`、`modules/keepa_client.py:12`|
|`modules/canopy_client.py`|旧取得・設定・cache・filter・出力|—|有|`modules/amazon_data_provider.py:99`、`tests/test_amazon_data_provider.py:15`|
|`modules/category_ai_benchmark.py`|旧Category AI／候補表示|有|有|`modules/category_mapper_ai.py:9`、`tests/test_category_ai_benchmark.py:9`|
|`modules/category_ai_core.py`|旧Category AI／候補表示|有|有|`modules/category_ai_benchmark.py:12`、`modules/category_ai_leaf_search.py:8`|
|`modules/category_ai_keepa_runner.py`|旧Category AI／候補表示|—|—|`tests/test_category_ai_keepa_runner.py:8`|
|`modules/category_ai_leaf_search.py`|旧Category AI／候補表示|—|有|`modules/sg_candidate_runtime.py:73`、`modules/sg_continuous_runtime.py:496`|
|`modules/category_ai_openai.py`|旧Category AI／候補表示|有|有|`modules/category_ai_leaf_search.py:13`、`modules/category_mapper_ui.py:16`|
|`modules/category_ai_prompts.py`|旧Category AI／候補表示|有|有|`modules/category_ai_core.py:11`、`modules/category_ai_leaf_search.py:12`|
|`modules/category_mapper.py`|旧Category／Brand（SLS保護依存を保持）|有|有|`modules/category_mapper_sg_brand_workflow.py:11`、`modules/category_mapper_sg_ui.py:12`|
|`modules/category_mapper_ai.py`|旧Category AI／候補表示|有|有|`modules/category_mapper_sg.py:15`、`modules/category_mapper_sg_ui.py:11`|
|`modules/category_mapper_sg.py`|旧Category／Brand（SLS保護依存を保持）|有|有|`modules/category_mapper_sg_brand_workflow.py:5`、`modules/category_mapper_sg_preparation.py:7`|
|`modules/category_mapper_sg_brand_workflow.py`|旧Category／Brand（SLS保護依存を保持）|有|有|`modules/category_mapper_sg_ui.py:31`、`modules/sg_candidate_runtime.py:14`|
|`modules/category_mapper_sg_preparation.py`|旧Category／Brand（SLS保護依存を保持）|有|有|`modules/category_mapper_sg_ui.py:33`、`tests/test_prelisting_sg_body_safety_output.py:9`|
|`modules/category_mapper_sg_ui.py`|旧Category／Brand（SLS保護依存を保持）|有|有|`modules/category_mapper_ui.py:14`、`app_sg_candidate.py:9`|
|`modules/category_mapper_store.py`|旧Category／Brand（SLS保護依存を保持）|有|有|`modules/category_mapper.py:13`、`modules/category_mapper_ai.py:18`|
|`modules/category_mapper_ui.py`|旧Category／Brand（SLS保護依存を保持）|有|有|`app.py:42`、`tests/test_app_category_mapper.py:10`|
|`modules/category_suggestion_ui.py`|旧Category AI／候補表示|有|有|`modules/category_mapper_sg_ui.py:10`、`modules/category_mapper_ui.py:13`|
|`modules/classification_workflow.py`|旧準備・分類・永続保存（安全回帰と混在）|—|—|`modules/classification_workflow_ui.py:10`、`modules/p5_material_updates.py:229`|
|`modules/classification_workflow_ui.py`|旧準備・分類・永続保存（安全回帰と混在）|—|—|`app.py:1979`、`modules/p5_ui.py:97`|
|`modules/commerce_keepa_expansion.py`|旧取得・設定・cache・filter・出力|—|有|`modules/amazon_data_provider.py:65`|
|`modules/config.py`|旧取得・設定・cache・filter・出力|有|有|`app.py:50`、`modules/cache.py:9`|
|`modules/direct_chat_assist.py`|旧ChatGPT clipboard補助|有|—|`app.py:52`、`tests/test_direct_chat_assist.py:4`|
|`modules/export_csv.py`|旧取得・設定・cache・filter・出力|—|有|`tests/test_export_csv.py:4`、`tests/test_guardrails.py:9`|
|`modules/fromax_ng_export.py`|旧NG語出力（辞書回帰は保持）|—|—|`modules/fromax_ng_ui.py:3`、`tests/test_brand_monitoring.py:91`|
|`modules/fromax_ng_ui.py`|旧NG語出力（辞書回帰は保持）|—|—|`app.py:361`|
|`modules/home_appliances_files.py`|独立家電CLIの入出力（共通判定は別module）|—|—|`tests/test_home_appliances_files.py:12`、`tests/test_home_appliances_research_replay.py:17`|
|`modules/image_inspection_policy.py`|旧画像経路（Fact型・import／保護依存を保持）|有|有|`modules/p5_runtime.py:653`、`modules/ph_image_safety.py:15`|
|`modules/keepa_bounded_transport.py`|旧取得・設定・cache・filter・出力|—|有|`modules/keepa_client.py:246`、`modules/p5_transport.py:345`|
|`modules/p5_candidates.py`|旧P5／専用起動・実行環境|—|—|`modules/p5_runtime.py:95`|
|`modules/p5_initializer.py`|旧P5／専用起動・実行環境|—|—|`modules/p5_windows.py:249`、`tests/test_p5_initializer.py:12`|
|`modules/p5_live_adapter.py`|旧P5／専用起動・実行環境|—|—|`modules/p5_operator.py:12`、`modules/p5_windows.py:233`|
|`modules/p5_material_updates.py`|旧P5／専用起動・実行環境|—|—|`modules/p5_candidates.py:233`、`modules/p5_runtime.py:255`|
|`modules/p5_operator.py`|旧P5／専用起動・実行環境|—|—|`modules/p5_initializer.py:12`、`tests/test_p5_acceptance_rehearsal.py:19`|
|`modules/p5_runtime.py`|旧P5／専用起動・実行環境|—|—|`modules/p5_candidates.py:15`、`modules/p5_live_adapter.py:17`|
|`modules/p5_setup.py`|旧P5／専用起動・実行環境|—|—|`modules/p5_operator.py:81`、`modules/p5_windows.py:19`|
|`modules/p5_transport.py`|旧P5／専用起動・実行環境|—|—|`modules/p5_live_adapter.py:94`、`modules/p5_runtime.py:561`|
|`modules/p5_ui.py`|旧P5／専用起動・実行環境|—|—|`app.py:1124`、`modules/practical_beta_ui.py:119`|
|`modules/p5_windows.py`|旧P5／専用起動・実行環境|—|—|`modules/p5_operator.py:96`、`tests/test_p5_acceptance_rehearsal.py:22`|
|`modules/ph_image_safety.py`|旧画像経路（Fact型・import／保護依存を保持）|有|有|`app.py:87`、`modules/asin_resolver.py:3`|
|`modules/ph_image_safety_api.py`|旧画像経路（Fact型・import／保護依存を保持）|有|有|`modules/ph_image_safety_ui.py:13`、`modules/sg_candidate_runtime.py:145`|
|`modules/ph_image_safety_ui.py`|旧画像経路（Fact型・import／保護依存を保持）|有|—|`app.py:91`|
|`modules/practical_beta_ui.py`|旧準備・分類・永続保存（安全回帰と混在）|—|—|`app.py:1980`、`modules/classification_workflow_ui.py:164`|
|`modules/practical_weapon_ui.py`|旧画像経路（Fact型・import／保護依存を保持）|—|—|`modules/p5_ui.py:188`、`modules/practical_beta_ui.py:114`|
|`modules/prelisting_gate_csv.py`|旧Gate CSV／Expansion受渡し（共通回帰は保持）|有|有|`app.py:102`、`modules/category_mapper.py:21`|
|`modules/prelisting_gate_handoff.py`|旧Gate CSV／Expansion受渡し（共通回帰は保持）|有|—|`app.py:97`、`modules/candidate_filter_ui.py:7`|
|`modules/preparation_group_output.py`|旧準備・分類・永続保存（安全回帰と混在）|有|有|`modules/category_mapper.py:28`、`modules/category_mapper_sg_preparation.py:10`|
|`modules/preparation_validity.py`|旧準備・分類・永続保存（安全回帰と混在）|—|有|`modules/beta_workbench.py:18`、`modules/category_mapper.py:684`|
|`modules/product_review.py`|旧準備・分類・永続保存（安全回帰と混在）|有|有|`modules/category_mapper_sg_brand_workflow.py:12`、`modules/classification_workflow.py:19`|
|`modules/product_review_transport.py`|旧準備・分類・永続保存（安全回帰と混在）|有|有|`modules/category_mapper_sg_brand_workflow.py:156`、`modules/category_mapper_sg_preparation.py:166`|
|`modules/research_csv_adapter.py`|調査CSV／Resolver（adapterは設置版利用あり）|有|—|`modules/sora_ui.py:12`、`modules/research_csv_adapter_ui.py:10`|
|`modules/research_csv_adapter_ui.py`|調査CSV／Resolver（adapterは設置版利用あり）|有|—|`app.py:118`|
|`modules/safety_shadow.py`|旧Shadow読取比較|—|—|`modules/safety_shadow_comparison.py:16`、`tests/test_safety_shadow.py:12`|
|`modules/safety_shadow_comparison.py`|旧Shadow読取比較|—|—|`modules/safety_shadow_comparison_ui.py:4`、`tests/test_safety_shadow_comparison.py:20`|
|`modules/safety_shadow_comparison_ui.py`|旧Shadow読取比較|—|—|`app.py:895`、`tests/test_safety_shadow_comparison_ui.py:93`|
|`modules/sg_beta_environment.py`|旧SG専用runtime／運用|—|—|`app.py:906`、`modules/beta_environment.py:6`|
|`modules/sg_beta_facts.py`|旧準備・分類・永続保存（安全回帰と混在）|—|有|`app.py:862`、`modules/beta_work_store.py:13`|
|`modules/sg_beta_release.py`|旧SG専用runtime／運用|—|有|`modules/beta_workbench.py:270`、`modules/category_mapper_sg_preparation.py:95`|
|`modules/sg_beta_work_store.py`|旧準備・分類・永続保存（安全回帰と混在）|—|有|`modules/sg_beta_workbench.py:25`、`modules/sg_beta_workbench_ui.py:10`|
|`modules/sg_beta_workbench.py`|旧準備・分類・永続保存（安全回帰と混在）|—|有|`modules/beta_workbench.py:20`、`modules/category_mapper_sg_preparation.py:190`|
|`modules/sg_beta_workbench_ui.py`|旧準備・分類・永続保存（安全回帰と混在）|—|—|`modules/practical_beta_ui.py:13`、`tests/test_sg_initial_beta.py:364`|
|`modules/sg_candidate_runtime.py`|旧SG専用runtime／運用|—|—|`tests/test_category_ai_leaf_search.py:119`、`tests/test_sg_candidate_runtime.py:15`|
|`modules/sg_continuous_runtime.py`|旧SG専用runtime／運用|—|有|`app.py:912`、`modules/category_mapper_sg.py:570`|
|`modules/sg_live_runtime.py`|旧SG専用runtime／運用|—|有|`modules/sg_beta_environment.py:10`、`modules/sg_continuous_runtime.py:18`|
|`modules/sg_live_validation.py`|旧SG専用runtime／運用|—|有|`modules/category_mapper_sg.py:569`、`modules/category_mapper_sg_brand_workflow.py:25`|
|`modules/shopee_access_token_source.py`|旧Shopee API／token|有|有|`modules/p5_runtime.py:609`、`modules/sg_live_runtime.py:18`|
|`modules/shopee_catalog_client.py`|旧Shopee API／token|有|有|`modules/category_mapper.py:25`、`modules/category_mapper_sg.py:24`|
|`modules/sls_category_assets.py`|SLS保護のため保持|有|有|`modules/category_mapper.py:26`、`modules/category_mapper_sg.py:21`|
|`modules/sls_category_rules.py`|SLS保護のため保持|有|有|`modules/category_mapper.py:27`、`modules/category_mapper_ui.py:44`|
|`modules/sls_category_rules_sg.py`|SLS保護のため保持|有|有|`modules/category_mapper_sg.py:22`、`modules/category_mapper_sg_preparation.py:9`|
|`modules/weapon_image_inspection.py`|旧画像経路（Fact型・import／保護依存を保持）|—|有|`modules/category_mapper_sg_brand_workflow.py:43`、`modules/p5_transport.py:419`|

`asin_resolver.py`・`keepa_client.py`・`home_appliances_classifier.py` はこの候補表に入れず、
第2節の「残す25ファイル」で共通の利用部分を示した。旧機能の関数だけは切分け後の候補となる。
表の保護依存には、保護テストがimportするmoduleの未実行分岐からのimportも含む。
直接依存の強い例は `test_sls_category_protected.py` → `category_mapper_ui._group_progress_label` と
`category_mapper`／`category_mapper_sg`／`sls_category_*`。その安全条件を維持する。

### 6.2 通常起動しない別アプリ・起動script・調査CLI

|ファイル／組|根拠・依存・扱い|
|---|---|
|`app_beta.py`|`Start-Beta.ps1` の起動先。旧render_application／P4／P5を使う。Soraのcmdは指定しない。|
|`app_sg_beta.py`<br>`app_sg_candidate.py`|SG専用launcher／旧render_applicationの分岐が起動する。Soraのcmdからは起動しない。|
|`category_ai_benchmark_app.py`|独立page。専用UIテストはretired。共有AI依存の切分けが必要。|
|`scripts/Start-Beta.ps1`<br>`scripts/Stop-Beta.ps1`<br>`scripts/Install-BetaShortcut.ps1`|app_beta用、ポート8503。別アプリの廃止単位で検討し、現行のSora起動.cmd・8510は残す。|
|`scripts/Start-SGBeta.ps1`<br>`scripts/Stop-SGBeta.ps1`<br>`scripts/Install-SGBetaShortcut.ps1`|app_sg_beta用、ポート8502。旧環境での手動利用は未確認。|
|`scripts/Start-SGCandidate.ps1`|app_sg_candidate／BetaRelease時app_sg_betaの専用起動。通常Soraは経由しない。|
|`scripts/SGBetaProcess.ps1`|上記Start・Stop等のprocess同一性helper。正式cmdは使わないが、現物processの限定停止を弱める変更はしない。|
|`modules/p5_windows.ps1`|p5_windows.pyが使う旧P5のOS観測。通常Soraのcmdは使わない。別運用の記録や実機には触らない。|
|`scripts/sg_live_smoke.py`|SGのCategory／Brand／画像AI等の別承認用live CLI。実行しない。共通安全部品は他にも利用。|
|`scripts/sg_category_diagnostic.py`|SG分類の保存資料診断CLI。専用8ケースはretired。|
|`scripts/sg_initial_beta_saved_audit.py`|旧SG保存結果の独立audit。activeのSafety／出所確認からも参照される。|
|`scripts/classify_home_appliances.py`|独立ファイル分類CLI。home_appliances_files側だけの候補で、共通停止ruleは残す。|
|`scripts/safety_shadow_report.py`|保存資料からの読取比較CLI。通常SoraのGateは呼ばない。|
|`scripts/build_sls_category_assets.py`|通常画面からは呼ばないが、SLS保護のsupportがencode／digestを利用。保護資産の変換手順として残す。|
|`scripts/Generate-GovernanceEvidence.ps1`<br>`scripts/Invoke-GovernanceV2.ps1`<br>`scripts/Update-ContextSnapshot.ps1`<br>`scripts/Verify-ContextSnapshot.ps1`<br>`scripts/Verify-GovernanceV2.ps1`<br>`scripts/Test-OwnerEvidencePreparation.ps1`|Governance／CI・旧Verifier保全用。商品経路で使わないことを理由に削除しない。署名鍵・Anchorは本調査で使わない。|
|`scripts/Verify-LightweightDevelopmentPolicy.ps1`<br>`scripts/Verify-WorkBriefHandoff.ps1`|開発・handoff契約とそのテストが利用。残す。|
|`scripts/check_python_syntax.py`<br>`scripts/verify_change.ps1`|開発検証の道具。残す。verify_changeの既定AppTest等は旧画面を参照するので、旧画面廃止時に現在の入口向けへ更新が必要。|
|`scripts/e2e/prepare_browser_e2e.ps1`<br>`scripts/e2e/start_streamlit_e2e.ps1`<br>`scripts/e2e/stop_streamlit_e2e.ps1`<br>`scripts/e2e/verify_browser_downloads.ps1`|開発用browser手順で、通常の起動cmdではない。検証道具として保持し、旧画面fixtureだけを後の変更単位で見直す。今回実行しない。|
|`integrations/google_apps_script/ph_access_token_bridge/Code.gs`<br>`integrations/google_apps_script/ph_access_token_bridge/SgSync.gs`|Shopee認証Bridgeの外部設置用。SoraのSP-APIから依存なし。既設Bridgeや外部データの削除は含めない。|

### 6.3 Pythonテスト全123ファイル

件数はパラメータ展開後。時間は基準CIのactiveケースの和（秒）。retired行の「—」は未実行。
「保持」は現在の通常範囲を維持、「混在」は旧部分の削除前に共通確認を分離、
「旧経路候補」は製品からの依存・helper・現在の契約を外した後の候補。今回の選別は変更しない。

|ファイル（すべてtests/配下）|active|retired|active秒|依存・扱い|
|---|---:|---:|---:|---|
|`test_amazon_data_provider.py`|9|0|0.374|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_app_category_mapper.py`|9|12|11.266|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_app_category_mapper_sg.py`|1|2|0.530|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_app_prelisting_contract.py`|6|0|0.083|混在：旧appのGate入力・失効契約。新入口の同等確認を保持|
|`test_app_prelisting_gate.py`|10|0|1.397|混在：旧画面AppTestだがGate・出力停止も検証|
|`test_app_research_csv_adapter.py`|1|0|0.253|旧経路候補：旧調査CSV画面。設置版のResolverはまだ利用可能|
|`test_app_resolver_contract.py`|9|4|2.835|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_asin_resolver.py`|97|0|3.530|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_asin_resolver_evidence.py`|3|22|0.003|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_asin_resolver_evidence_integration.py`|0|1|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_battery_presence.py`|99|0|0.796|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_beta_application.py`|12|0|2.473|混在／保留：旧専用画面だけでなく市場切替・Keepa cacheと設定の市場分離も確認するため残す。|
|`test_beta_workbench_p2.py`|19|80|22.016|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_brand_monitoring.py`|68|0|0.487|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_browser_e2e_fixture_contract.py`|4|0|0.031|保持：必須CI／開発契約／選別の保護|
|`test_candidate_filter_ui.py`|15|0|9.914|旧経路候補／混在：旧価格評価filterとGate資料搬送|
|`test_candidate_filters.py`|78|0|0.078|旧経路候補：価格・評価条件。Soraの通常判定とは別|
|`test_canopy_client.py`|12|0|0.012|旧経路候補：Canopy専用。通常取得はSP-API|
|`test_category_ai_benchmark.py`|0|25|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_category_ai_benchmark_ui.py`|0|1|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_category_ai_core.py`|0|22|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_category_ai_keepa_runner.py`|3|11|0.084|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_category_ai_leaf_search.py`|0|11|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_category_ai_openai.py`|0|10|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_category_mapper.py`|6|34|13.470|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_category_mapper_ai.py`|0|6|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_category_mapper_sg.py`|15|48|2.151|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_category_mapper_sg_brand.py`|2|107|1.787|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_change_verification_loop.py`|4|0|4.711|保持：必須CI／開発契約／選別の保護|
|`test_classification_p3.py`|5|62|10.239|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_classification_p3_ui.py`|2|2|12.158|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_commerce_keepa_expansion.py`|2|0|0.976|混在／保留：Expansionを含むが、残すKeepa共通取得の応答・失敗時停止も確認するため残す。|
|`test_community_ng.py`|18|0|0.170|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_direct_chat_assist.py`|22|0|0.027|旧経路候補：clipboard補助。通常Soraの呼出しなし|
|`test_expansion_gate_handoff.py`|49|0|21.175|混在／保留：ExpansionとGateへの成分・説明文の同一性／失効を同時に確認するため残す。|
|`test_export_csv.py`|2|0|0.002|旧経路候補：旧Expansion出力|
|`test_fromax_ng_export.py`|8|0|0.096|混在：旧NG語出力。ブランド・辞書回帰が同moduleを使用|
|`test_governance_docs_contract.py`|34|0|0.035|保持：必須CI／開発契約／選別の保護|
|`test_governance_v2.py`|142|0|30.417|保持：必須CI／開発契約／選別の保護|
|`test_guardrail_match_context.py`|9|0|0.035|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_guardrails.py`|563|0|7.935|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_home_appliances_files.py`|68|0|0.162|混在／保留：独立の家電ファイル分類の扱いは今回の廃止指定だけでは確定しないため残す。|
|`test_home_appliances_research_replay.py`|2|0|0.006|混在／保留：独立の家電資料replayの扱いは今回の指定だけでは確定しないため残す。|
|`test_image_inspection_policy.py`|42|0|1.205|混在／保留：画像AI実行だけでなくGateが読む既存画像Factの対象判定を含むため残す。|
|`test_ingredient_safety.py`|18|0|0.018|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_ingredient_text_sections.py`|194|0|1.619|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_keepa_candidate_filters.py`|20|2|1.704|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_keepa_client.py`|9|10|0.340|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_lightweight_development_policy.py`|23|0|9.456|保持：必須CI／開発契約／選別の保護|
|`test_listing_inventory_parser.py`|24|0|0.024|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_owner_evidence_preparation.py`|18|0|6.200|保持：必須CI／開発契約／選別の保護|
|`test_owner_merge_ci_contract.py`|6|0|9.608|保持：必須CI／開発契約／選別の保護|
|`test_p5_acceptance_rehearsal.py`|6|0|76.205|混在／保留：P5受入とResolver資料搬送を複数回まとめて扱う。分離を断定せず全件残す。|
|`test_p5_candidates.py`|20|52|42.138|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_p5_category_acquisition.py`|0|32|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_p5_composition.py`|2|53|3.429|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_p5_initializer.py`|0|24|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_p5_operation_preflight.py`|0|58|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_p5_output.py`|2|14|1.994|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_p5_permission_trial.py`|0|36|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_p5_production_connection.py`|0|29|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_p5_restart_binding.py`|0|36|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_p5_runtime.py`|14|86|3.683|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_p5_storage_probe.py`|0|6|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_p5_ui.py`|6|10|18.965|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_ph_image_safety.py`|107|0|0.325|保持／混在：共通Fact型と旧画像Safetyの境界|
|`test_ph_image_safety_api.py`|0|46|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_ph_image_safety_transport.py`|8|0|0.329|保持／混在：共通取得資料と旧画像Factの搬送|
|`test_ph_image_safety_ui.py`|6|0|3.425|混在：旧画像確認画面の安全条件|
|`test_practical_beta_p4_ui.py`|4|11|343.179|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_prelisting_candidate_csv.py`|35|0|0.040|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_prelisting_gate.py`|84|0|0.418|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_prelisting_gate_csv.py`|53|0|0.053|保持：旧CSVをCategory／SLS保護回帰が使用|
|`test_prelisting_gate_ui.py`|29|0|0.029|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_prelisting_sg_body_safety.py`|53|0|0.421|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_prelisting_sg_body_safety_output.py`|8|0|12.492|混在：旧準備出力でも本体停止が非解除|
|`test_prelisting_sg_body_safety_ui.py`|4|0|5.230|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_preparation_exit_contract.py`|26|0|12.152|混在／保留：旧カテゴリ準備出力と共通の資料・Safety失効条件を同時に扱うため残す。|
|`test_preparation_group_output.py`|5|0|25.646|混在／保留：旧カテゴリ出力と共通CSV整形・順序・式文字列保護を扱うため残す。|
|`test_preparation_validity.py`|64|0|17.630|混在／保留：P1の共通現在根拠・Safety条件。P2〜P4の廃止だけで共通条件まで外さない。|
|`test_product_review.py`|13|0|22.465|混在／保留：旧分類・画像確認と共通の人による確認・Safety条件が混在するため残す。|
|`test_product_review_transport.py`|14|0|11.083|混在／保留：GateのCandidate・説明文・確認資料の受渡しも確認するため残す。|
|`test_product_text_safety.py`|28|0|0.113|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_research_csv_adapter.py`|11|0|0.025|旧経路候補：調査CSV parser。設置版利用とコード保全方針あり|
|`test_safety_policy.py`|266|0|4.147|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_safety_policy_false_positives.py`|69|0|0.878|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_safety_product_evidence.py`|81|0|0.960|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_safety_shadow.py`|120|0|2.529|旧経路候補：独立Shadow。保安rule本体は別|
|`test_safety_shadow_comparison.py`|51|0|0.722|旧経路候補：旧比較UIからもhelper参照あり|
|`test_safety_shadow_comparison_ui.py`|2|0|0.667|旧経路候補：Expansion引継ぎテストがhelperを利用|
|`test_sg47_false_positives.py`|86|0|1.233|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_sg_beta_environment.py`|25|0|7.975|混在／保留：旧設置設定とKeepaの継続取得予算の共通条件が混在するため残す。|
|`test_sg_beta_process_identity.py`|0|2|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_sg_beta_release.py`|10|11|13.750|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_sg_brand_confirmation_ui.py`|3|14|7.060|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_sg_candidate_runtime.py`|1|12|7.740|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_sg_category_diagnostic.py`|0|8|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_sg_continuous_operation.py`|36|0|52.049|混在／保留：カテゴリ取得とKeepaの送信予約・実消費・UNKNOWN保全が混在するため残す。|
|`test_sg_image_inspection.py`|0|21|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_sg_initial_beta.py`|27|47|13.289|混在：旧機能＋資料同一性・安全停止等。現行selectorでactiveを保持|
|`test_sg_live_runtime.py`|0|16|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_sg_live_ui.py`|0|2|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_sg_live_validation.py`|0|39|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_sg_preparation_preview.py`|0|10|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_sg_safety_files_ui.py`|2|0|1.184|混在：旧UIの成分・文章ファイル必須停止|
|`test_shopee_access_token_source.py`|0|42|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_shopee_catalog_client_marketplace.py`|0|14|—|旧機能専用：明示selectorで全件retired。通常CIの実行短縮なし|
|`test_sls_category_assets.py`|16|0|1.702|保持：PH／SGのSLS・市場分離・出力停止|
|`test_sls_category_lifecycle.py`|3|0|2.283|保持：PH／SGのSLS・市場分離・出力停止|
|`test_sls_category_protected.py`|23|0|13.962|保持：PH／SGのSLS・市場分離・出力停止|
|`test_sls_category_rules.py`|11|0|1.461|保持：PH／SGのSLS・市場分離・出力停止|
|`test_sls_category_sg_assets.py`|30|0|3.349|保持：PH／SGのSLS・市場分離・出力停止|
|`test_sls_category_sg_lifecycle.py`|13|0|8.474|保持：PH／SGのSLS・市場分離・出力停止|
|`test_sls_category_sg_rules.py`|39|0|2.777|保持：PH／SGのSLS・市場分離・出力停止|
|`test_sls_category_sg_ui.py`|5|0|0.654|保持：PH／SGのSLS・市場分離・出力停止|
|`test_sls_category_transform.py`|5|0|1.522|保持：PH／SGのSLS・市場分離・出力停止|
|`test_sora_acquisition.py`|5|0|0.174|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_sora_input.py`|15|0|0.026|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_sora_research_handoff.py`|7|0|0.222|保持：通常2択・通信なしの契約＋旧Resolver手順|
|`test_sora_run.py`|21|0|0.229|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_sora_ui.py`|9|0|4.703|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_sp_api_catalog.py`|15|0|0.018|保持：通常Sora／共通ASIN・Fact／保安の回帰|
|`test_test_scope.py`|7|0|1.484|保持：必須CI／開発契約／選別の保護|
|合計|3,367|1,203|950.580|通常／別実行を区別|

テスト用supportの `tests/preparation_validity_support.py`、`sls_category_support.py`、
`sls_category_sg_support.py` は上記のケース数に含めないhelper。特に後者2つは保護テストが使用する。
他の `test_*.py` 内にもhelperがあり、テスト関数を残さない場合でもimport先を逆引きして移す。

JavaScriptは `tests/js/ph_access_token_bridge.test.js` に6、`sg_access_token_bridge.test.js` に11の
`test(...)` 宣言を静的確認した。今回収集・実行しておらず、Python 4,570ケースに加算しない。
通常のworkflowにこのJSテストの実行stepはないため、これらを削除しても通常CIのテスト実行短縮はない。

### 6.4 次に削除PRを作る時の確認

この一覧の基準版と差分を確認し、追加された呼出元・未採用変更・実際の設置版を調べ直す。
moduleのimportだけでなく、AppTestのコード文字列、script名、fixture名、設定の文字列参照も検索する。
retired selectorの欠損・不正時に収集失敗する条件、共通helper、PH／SG保護の812ケース、
必須の6チェックを維持する。文書や過去Evidenceをコードの現在の依存先と混同せず、履歴自体は削除しない。
