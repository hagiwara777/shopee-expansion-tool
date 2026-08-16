# PROJECT ROADMAP

## 当面の全体目標

出品支援ツールの目的は、安全に出品準備できるASIN数を少ない人手で増やすことである。

出品支援ツールは、出品先市場に依存しない候補生成と、対象市場ごとの出品判断・準備を分ける。候補生成は、既知Amazon ASINから関連Amazon ASIN候補を広げるASIN Expansionと、Shopeeに出品されている商品の英字タイトルから対応するAmazon ASINへ到達するASIN Resolverの二つの入口とする。PHは現在の最初の受入確認市場であり、候補生成機能をPH専用とする意味ではない。対象市場ごとのGuardrail、既出品照合、Shopee Category ID、Shopee Brand IDを確認し、作業者が既存出品ツールへ手作業で入力できる状態を段階別に検証する。Resolverの成功は、英字タイトルから正しいASINへの到達性能で判断する。外部出品ツール契約、自動Workflow、自動出品は別設計・別承認とする。

## 開発対象と優先順位

Shopee事業で開発する対象は、次の三つの独立ツールである。三つのツールは相互にデータ連携せず、一つのツールの出力を他のツールの正式入力としない。ツール間に実行順序、API接続、自動連携、共有状態管理を設けない。

1. **出品支援ツール** — ASIN、Shopee Category ID、Shopee Brand IDの取得・確認を省力化する。
2. **出品後商品改善ツール** — Shopeeへ出品済みの商品リストの編集・改善を省力化する。
3. **Amazon仕入れ支援ツール** — Amazonでの商品購入・仕入れを省力化する。

現在は出品支援ツールの完成を最優先とする。この優先順位は開発順序であり、三ツール間の技術的依存関係を意味しない。出品後商品改善ツールとAmazon仕入れ支援ツールの本格設計・実装は、出品支援ツールの完成受入後に優先順位を再判断する。両ツールの詳細仕様は今回決めない。出品支援ツールの完成条件も未決定であり、次の完成定義設計ゲートで定める。

外部出品ツールへの自動接続・自動投入は出品支援ツールの中核目的と別の責務境界であり、別設計・別承認とする。外部契約未確認の事実は残すが、その未確認だけを理由にASIN、Shopee Category ID、Shopee Brand IDの取得・確認に関する中核開発全体を停止しない。


## V2の論理責務と実装順

V2では、候補ASINと出所を`Candidate`、確認済み事実を`FactSnapshot`、Safety上のPASS / REVIEW / BLOCKを`SafetyDecision`、不足Factを解決する構造化質問・回答を`ReviewCase`、Primeまたは翌日発送等の当社運用条件を`OperationalFilter`、Categoryと必須属性単位のASIN groupを`CategoryBatch`として論理的に分離する。物理CSV列、DB構造、API fieldは今回確定しない。

APIはFact、RuleはDecision、AIはPrediction、HumanはExceptionを担当する。Gate／Guardrailが無秩序に外部APIを直接呼ばない。実効BLOCKは`COMMON_BLOCK ∪ 選択市場BLOCK`とし、市場別BLOCKはCOMMON_BLOCKを解除せず、BLOCKを後工程でREVIEWまたはPASSへ降格しない。

Category Mapperは唯一の正しいleaf Categoryの完全自動確定ではなく、既存出品ツールで一括処理しやすいCategoryと必須属性単位へのBatch Preparationを主目的とする。AI Category predictionは候補予測に限り、Safety BLOCK根拠にしない。Safety REVIEWとCategory Confirmationは別責務とする。

PHではPhase 1 deterministic BLOCKのmain技術受入後、PH Beta Minimum Definitionを先に置く。Beta Minimum Coreは、(B1) ExpansionとResolverの両入口による候補ASIN取得、(B2) PH Safety、(B3) 確認済みShopee Category IDへの経路、(B4) 確認済みShopee Brand IDまたはNo Brandへの経路、(B5) 未確定を推測で準備完了にしない停止能力、(B6) ASIN・Category ID・Brand ID / No Brandの揃い具合の一意な判別、(B7) 人間が確認済み情報を取得して既存出品ツールへの手入力準備に利用できるhandoffとする。これは外部出品ツールへの自動投入や実際の出品可能を意味しない。

次は、B1〜B7をmainの実装・テスト・既存Evidenceへ読み取り専用で照合するPH Beta Minimum Feasibility Auditである。監査でBLOCKED、またはBeta成立を妨げるPARTIALと確認された不足だけを実装し、その後にPH Betaの実画面・実業務受入へ進む。structured REVIEW、API auto-resolution、Shipping、Category Batch、mandatory attribute、AI Shadow、Workflow等は、同監査でBeta成立に必要と確認された場合、またはBeta後の実利用で優先度が高いと確認された場合だけ着手判断する。mandatory attributeは現時点でconditionalである。

Beta前に詳細なE2E人間作業時間測定、`CORE_INFO_READY ASIN / human hour`、Human Touch Rate、固定工数削減目標を必須Gateにしない。Beta後は実利用、オーナーによる実務ボトルネック報告、次versionでの改善を反復する。必要になったE2E時間測定はこのBeta後の改善手段候補とし、既存の件数、status、未解決理由等の自動出力を優先して、人間へ詳細な時間記録を常時要求しない。他市場への共通化はPH Betaの成立確認後に別途判断する。
## 正式完成済み

- PH Category Mapper Ver0.1
- Shopee Research CSV Import Adapter Ver0.1
- ASIN Resolverの不正URL耐性修正
- PH固定30件評価とオーナー受入
- ASIN Resolver Evidence Persistence Ver1
- formal main commit `8f664cdb42edc521371c389f6ad72ac7e0f3aecd`

ASIN到達性能とResolver成功は未評価であり、Evidence Persistenceの完成だけで成功を宣言しない。

## 実験中・未承認

- PH Category Mapper AI Shadow Ver0.2.1
- branch: `feature/ph-category-mapper-ai-shadow-v0.2.1`
- 実行開始はオーナー明示承認まで保留

## 出品支援ツールの内部工程

### 1. 候補生成

- ResolverとExpansionは、出品先市場を決めず、候補を作る。候補の出品可否は決めない。
- Shopeeに出品されている商品の英字タイトル → Resolver → 対応するAmazon ASIN
- 既知Amazon ASIN → Expansion Tool → 関連Amazon ASIN候補

### 2. 候補選別

- Guardrail／出品前保安ゲート（対象市場を明示して実行）
- ELIGIBLE / REVIEW / EXCLUDE
- 現在の市場対応範囲は別途コード・仕様監査が必要

### 3. 出品準備

- Category Mapper（対象市場ごとのCategory ID、Brand ID、必須属性確認。現在はPHのみ。V2ではBatch Preparationを主目的とする）
- Category ID
- Brand ID
- 必須属性情報
- 人間確認
- 既存出品ツール向け受け渡し準備

### 4. 出品

- 既存出品ツールを使用
- 正式入力契約は未確認
- 自動接続・自動出品は未承認

## 現在から先の工程

1. 三つの独立ツール構成と出品支援ツール優先順位の正本化
2. 出品支援ツールの完成定義、残課題、利用者シナリオ、受入条件の設計ゲート
3. 完成定義と現行実装の差分監査（PH Guardrailの一発アウト基準・根拠監査を含む）
4. 不足実装、テスト、技術検収
5. 出品支援ツールの実画面・実業務受入
6. 完成受入後、出品後商品改善ツールまたはAmazon仕入れ支援ツールの優先順位を判断

Resolver、Expansion、Prelisting Gate、Category Mapperの既存詳細工程は、上記の出品支援ツール配下で維持する。外部契約証拠回収は、自動投入またはE2E接続を検討する場合の保留事項とし、現在の最優先工程には置かない。

## 保留

- Workflow層
- Resolver／ExpansionからGateへの自動投入
- GateからCategory Mapperへの自動投入
- 既存出品ツールへの自動投入
- 既存出品ツールの正式入力契約の証拠回収（自動投入またはE2E接続を検討する場合）
- Category自動確定
- 自動出品
- SG／MY／THの実装
- AI候補の1クリック採用 Ver0.3
- wrong category蓄積 Ver0.4

## 判断方針

- 証拠保存機能の完成だけでResolver成功を宣言しない。
- Resolver成功は英字商品名から正しいASINへの到達性能で判断する。
- 未確認の既存出品ツール契約を実装済みとして扱わない。
- PHで成立確認後にSG／MYへ進む。
- SG／MYの順序は証拠と事業判断なしに固定しない。
- 出品支援ツールの内部工程間の連携は、必要な場合に別設計ゲートを通す。
- Category Mapper AI Shadowと自動出品は、明示承認なしに開始しない。
