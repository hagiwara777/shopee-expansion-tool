# Offline Safety Shadow v1

KNIFE / CONTACT_LENSの商品本体と付属品を、保存済みFactから小規模に比較する開発用機能。
本書の独立比較CLIは通常アプリ、Guardrail、Prelisting Gate、Category Mapperへ接続しない。
通常Gate画面の任意の読取専用比較は[比較接続](SAFETY_SHADOW_COMPARISON.md)を参照する。
分類結果は商品の候補的な役割であり、国別の販売可否・法令適合・BLOCK / REVIEW / SAFEを決めない。
既存Safetyを変更しないため、Shadow完成によって実運用の見逃し・過剰BLOCK・人間REVIEW件数が減ったとは扱わない。

## 責務と対象

- `modules/safety_shadow.py`: 保存済みKeepa Fact adapterと共通の純粋Evaluator。
- `scripts/safety_shadow_report.py`: 明示したJSONの読み取り、既存PH / SG Guardrailとのoffline比較、JSON / Markdown出力。
- `tests/fixtures/safety_shadow/synthetic_products.json`: 合成例と、Evaluator出力から生成していない手書きの期待分類。実商品Evidenceではない。

分類Coreと独立CLIは新しいsidecar、Candidate列、DB、Rule DSL、巨大taxonomy、AI、Keepa client、追加APIを導入しない。
既存Ingredient / Product Text / Community NG / Shared Battery / Image / SLSの責務を置換しない。
MY / THは評価対象外で、市場runtimeを開始しない。本機能をBeta MUSTにしない。

## 入力と出所

入力は明示したJSON envelopeの`products`配列。形式を自動推測しない。

- `keepa_response`: 保存済みProduct応答の`asin / title / brand / categoryTree / categories / domainId`と文章5欄・成分3欄を使う。
- `cache_snapshot`: 明示して書き出された保存資料の`category_tree`と既存Product Text payloadを使う。アプリcacheを開いたり再取得したりしない。
- 文章の抽出・旧payloadの`NOT_CAPTURED`処理は既存 `product_text_safety` を再利用する。
- `category_origin`は`OWN_PRODUCT / SEED_FALLBACK / MISSING`。保存済みProductのstructuredカテゴリがある場合だけ既定をOWN_PRODUCTとする。Candidateの文字列`category`から構造を復元しない。
- 分類用category IDはOWN_PRODUCTかつdomainId=5の場合だけ採用する。キャッシュにdomainIdがない場合は推測でJPを補わず、そのIDを分類に使わない。
- `categories`全ID、type、更新日時は欠けていれば欠けたままにする。categoryTree末端は返却階層の末端であり、Category APIで真のleafを確認したものではない。
- 取得日をoffline実行日へ置換しない。Keepa `lastUpdate`はraw値で保持し、カテゴリ個別の更新日時とは扱わない。
- 入力ごとのSHAを記録する。SHAは同一性の証拠であり、API応答の真正性、資料の現在性、入力宣言の正しさを証明しない。

旧キャッシュ再取得なしで利用できるFactの範囲を比較する段階であり、完全搬送機構を先に作らない。
候補ASINの重複、壊れたFact・payload、label binding不一致はofflineレポートを失敗させる。
カテゴリ配列・title / brand / type・取得時刻は、未指定とnullを不正な型から区別する。
空object、数値0、boolean等を空配列・空文字へ黙って置換しない。
これは本番Gateの停止や全欠損商品のREVIEWを追加することではない。

## 最小分類規則

分類設定は2つの小さい`FamilyRule`で管理し、国別Policyを含めない。
分類versionはKNIFE_JP_SHADOW_V1 / CONTACT_LENS_JP_SHADOW_V2、EvaluatorはSAFETY_SHADOW_V3。

| 出力 | 意味 |
|---|---|
| BODY_CANDIDATE | 対象familyの商品本体を支持するEvidenceがある |
| ACCESSORY_CANDIDATE | 付属品・周辺用品を支持するEvidenceがある |
| CONFLICT | 本体と付属品の役割、または本体同梱の有無を示すEvidenceが矛盾する |
| UNKNOWN | familyとの関連はあるが役割を判別できない |

関連が検出されない商品はsignalを出さない。family外をUNKNOWNと混同しない。
一商品から複数familyのsignalを出せる。UNKNOWN / CONFLICTだけでREVIEWにしない。
各signalにfield、一致語・ID、一致箇所周辺の正規化済み抜粋、出所、Rule / Evaluator versionを残す。

- KNIFEのJP body IDは490276011 / 13945771 / 490275011、accessory IDは13945801 / 14617042051。
  根拠は2026-10-08の保存済みKnife20商品metadata監査。分類の補助例であり、IDの全商品が同じ実体という保証ではない。
  13944721はfamilyの関連だけに使い、本体分類へ昇格しない。巨大な親カテゴリ継承はしない。
- CONTACT_LENS_JP_SHADOW_V2は、承認済み12商品metadata観察からJPのソフトコンタクトレンズ
  2356869051、コンタクトケース362602011、洗浄・保存液362594011だけを分類設定へ追加する。
  この便宜標本で確認したIDを販売規制の根拠・商品実体の保証にせず、未観察のハードレンズ等へ拡張しない。
  Shopee Unique Category ID 100435等からAmazon IDを推測しない。
- EvaluatorはOWN_PRODUCT / domainId=5のcategoryTree先頭が本465392である場合、
  本文中の対象商品語を本体の言及として扱う。本体／付属品の登録IDとも重なればCONFLICT、
  言及だけならUNKNOWNとする。Keepa type、seed root、外国／不明domainはこの文脈根拠にしない。
  書籍候補も既存Safetyの停止を解除せず、UNKNOWNを販売可否へ結び付けない。
- accessoryの説明にあるknife/lensの語は、本体が同梱される証拠と混同しない。明示的な付属品表現がある文章の一般的本体語をBODY_MENTIONとして記録する。
- 本体を含むセットはBODY_CANDIDATE＋`bundle_candidate=true`とする。本体・付属品の共存自体をCONFLICTにしない。
  初期版は明示的な「includes a knife」「contact lenses included」「包丁付き」等がある場合に限る。
  商品情報の矛盾があればセットであってもCONFLICTへ置く。
- 複数category IDがあるだけではCONFLICTにしない。検証対象のbody / accessory両方を支持する場合は、明示セットがない限り矛盾候補とする。
- typeは監査表示だけで、分類やBODY確定に使わない。書籍・図鑑等の明示表現も実物の語と区別する。

この方式は語句とIDによる小さなheuristicであり、否定・引用・用途・セットの全面的な意味理解を保証しない。
未登録leaf、異なる表記、複雑な商品説明には見逃し・誤分類があり得る。ACCESSORYを販売可能と解釈しない。

## 比較と実行

同じFactでtitleのみ、title＋文章、title＋文章＋自分のカテゴリの3方式を比較する。
各方式の分類件数、一致Evidence、処理秒数を記録する。
コードSHAには既存GuardrailのCommunity NG loaderも含め、比較中の変更を検出する。
PH / SGは既存 `apply_guardrails` を市場別に実行し、分類の前後で全出力が同じか確認する。
保存FactのASIN・title・brand・own category path・成分3欄・文章5欄による比較であり、
本番Candidate / SHA結合済みsidecar / Gateの既出品照合 / Image / Mapper / 出品可能性の再現ではない。
seed fallbackのcategoryはこの比較入力にも使用しない。

SAFE/REVIEW＋BODY、BLOCK/REVIEW＋ACCESSORYは調査候補として記録する。
禁止の検出漏れ、過剰BLOCK、解除可能なREVIEWの確定数とは呼ばない。
既存BLOCKはexact NGや別の理由でも生じるので、一致語とsource・noteを並べて確認する。

比較レポートV2は、追加文章・追加カテゴリによる分類変更を、根拠の増加や期待ラベルとの一致と分ける。
familyが対象外から検出された場合とbundle flagだけが変わった場合も、分類変更として記録する。
既存一致語・source別に不一致候補をまとめ、商品本体・付属品・セットと国別条件の具体的な確認事項を表示する。
REVIEW＋本体候補も表示し、確定禁止か、本体確認で販売可能性が残るかを国別Policyと照合できる。
これは開発者のoffline調査用で、通常画面のREVIEW件数・人間確認義務・販売判断を増やさない。
レポートV1の既存項目は保持するが、JSONのschema_versionはSAFETY_SHADOW_REPORT_V2となる。

```powershell
python -B scripts/safety_shadow_report.py --evidence tests/fixtures/safety_shadow/synthetic_products.json --evidence-kind SYNTHETIC --source-format keepa_response --output-dir outputs/safety-shadow/synthetic-run
python -B scripts/safety_shadow_report.py --evidence <saved-response-1.json> <saved-response-2.json> --evidence-kind SAVED_PRODUCT --source-format keepa_response --labels <metadata-labels.json> --output-dir outputs/safety-shadow/saved-run
```

出力は指定した未使用directoryの`report.json / report.md`。既存出力・入力への上書きを拒否する。
通常appから実行しない。入力snapshotとcacheを書き換えず、credential / API envを読み込まない。

任意のlabels JSONは次の形とする。

```json
{"label_basis":"SYNTHETIC_EXPECTATION","labels":[{"asin":"B0SYN00001","family":"KNIFE","classification":"BODY_CANDIDATE"}]}
```

label_basisはSYNTHETIC_EXPECTATION / METADATA_OBSERVATION / INDEPENDENT_HUMAN_REVIEWを区別する。
合成入力には合成期待値、保存実商品にはmetadata観察または独立レビューを使う。
正解ラベルをEvaluator自身の出力から生成しない。一致数を一般精度やheld-out精度とは報告しない。
Knife20件は便宜標本で、この標本からカテゴリ設定も得ているので独立評価集合ではない。
CONTACT_LENSの合成契約や少量実商品での一致を一般精度と呼ばない。
追加metadata12件は本体4、空ケース3、ケア用品3、書籍2の便宜標本であり、独立評価集合ではない。
本体付きセット、カメラ用品、否定・矛盾・欠損の境界は合成検証と実商品観察を区別する。

## 続行判断

両familyで共通処理を使え、既存Guardrailとの不一致を具体的なEvidenceで説明できることが初期成果。
カテゴリ追加がtitle＋文章に比べて役立つかを別に評価し、カテゴリ構造の完成自体を目的としない。
通常UI / DB / 新sidecar、追加API、familyごとの大量例外やRule DSLが必要になり始めたら、
小さな辞書修正との効果・保守負担を再比較する。
本番Policy接続・既存BLOCK緩和・新BLOCK / REVIEW・追加実商品取得には自動移行しない。
独立したGun parts / Fireworks等の重大不足の検討を本Shadow完成待ちにしない。

共通の残る境界は、本体と付属品のセット表記、写真・引用に含まれるだけの同梱語、
商品についてのガイド等である。Literalの一致と販売内容に本体が含まれる根拠を区別する。
両familyへ同じ反例を当てて小さく改善し、商品群別の例外やtaxonomyの拡大を先行しない。
その評価と、SG等の個別販売Rule採用・本番接続は別に判断する。

SAFETY_SHADOW_V3は文単位の小さな共通処理を追加する。decimalの小数点は文区切りにしない。
本体・付属品を別の対象としてand等で列挙したset表記は同梱候補として記録する。
付属品だけのset、用途説明、別売品の紹介から本体を捏造しない。
写真内の同梱語はBUNDLE_REFERENCEとして記録し、非同梱が明示されなければCONFLICTにする。
同梱と非同梱が別の文で食い違う場合もCONFLICTを維持する。
buying guide／instruction guide等は媒体の文脈として扱うが、明示的な本体with instruction guideを
媒体と取り違えない。ガイドtitleの文脈をfeatures等の本体言及にも適用する。
限定した表現のheuristicであり、引用・否定・日本語の係り受けを網羅した意味解析ではない。
新signalや販売Policyは追加せず、既存BLOCK／REVIEWを解除しない。
