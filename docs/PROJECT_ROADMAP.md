# PROJECT ROADMAP

## 当面の全体目標

出品支援ツールの目的は、安全に出品準備できるASIN数を少ない人手で増やすことである。

**開発原則：完成度最大化ではなく、実務上使えるMinimum Betaを早く成立させ、実利用→ボトルネック発見→次Version改善を反復する。**

出品支援ツールは、出品先市場に依存しない候補生成と、対象市場ごとの出品判断・準備を分ける。候補生成は、既知Amazon ASINから関連Amazon ASIN候補を広げるASIN Expansionと、Shopeeに出品されている商品の英字タイトルから対応するAmazon ASINへ到達するASIN Resolverの二つの入口とする。PHは現在の最初の受入確認市場であり、候補生成機能をPH専用とする意味ではない。対象市場ごとのGuardrail、既出品照合、Shopee Category ID、Shopee Brand IDを確認し、作業者が既存出品ツールへ手作業で入力できる状態を段階別に検証する。Resolverの成功は、英字タイトルから正しいASINへの到達性能で判断する。外部出品ツール契約、自動Workflow、自動出品は別設計・別承認とする。

## 開発対象と優先順位

Shopee事業で開発する対象は、次の三つの独立ツールである。三つのツールは相互にデータ連携せず、一つのツールの出力を他のツールの正式入力としない。ツール間に実行順序、API接続、自動連携、共有状態管理を設けない。

1. **出品支援ツール** — ASIN、Shopee Category ID、Shopee Brand IDの取得・確認を省力化する。
2. **出品後商品改善ツール** — Shopeeへ出品済みの商品リストの編集・改善を省力化する。
3. **Amazon仕入れ支援ツール** — Amazonでの商品購入・仕入れを省力化する。

現在は出品支援ツールの完成を最優先とする。この優先順位は開発順序であり、三ツール間の技術的依存関係を意味しない。出品後商品改善ツールとAmazon仕入れ支援ツールの本格設計・実装は、出品支援ツールの完成受入後に優先順位を再判断する。両ツールの詳細仕様は今回決めない。PH Minimum Betaの完成定義・受入条件はDEC-0034、B1〜B7に対する差分監査結果と残る受入GateはDEC-0035で正本化済みである。少量実商品のB2 E2E全体フロー技術確認は完了し、次は画像Safety・人間REVIEWの最小設計ゲートである。

外部出品ツールへの自動接続・自動投入は出品支援ツールの中核目的と別の責務境界であり、別設計・別承認とする。外部契約未確認の事実は残すが、その未確認だけを理由にASIN、Shopee Category ID、Shopee Brand IDの取得・確認に関する中核開発全体を停止しない。


## V2の論理責務と実装順

V2では、候補ASINと出所を`Candidate`、確認済み事実を`FactSnapshot`、Safety判定を`SafetyDecision`、不足Factを解決する構造化質問・回答を`ReviewCase`、Primeまたは翌日発送等の当社運用条件を`OperationalFilter`、Categoryと必須属性単位のASIN groupを`CategoryBatch`として論理的に分離する。物理CSV列、DB構造、API fieldは今回確定しない。新しい公開status / enumは追加せず、既存statusとの具体的対応は後続技術設計で決める。

APIはFact、RuleはDecision、AIはPrediction、HumanはExceptionを担当する。Gate／Guardrailが無秩序に外部APIを直接呼ばない。実効BLOCKは`COMMON_BLOCK ∪ 選択市場BLOCK`とし、市場別BLOCKはCOMMON_BLOCKを解除せず、BLOCKを後工程でREVIEWまたはPASSへ降格しない。

ExpansionとResolverは候補生成の二入口であり、候補生成自身にSafety責務を持たせない。両入口の候補は共通Safetyへ渡し、Resolver由来またはShopee既出品であることだけを安全の根拠にしない。Safetyは、Shopee Category確定前に商品自体のFactで禁止・確認要件を判定し、Category決定後かつ`listing_ready`前にCategory・市場条件へ依存する禁止・確認要件を再判定する。確認済み禁止は除外し、未解決ケースだけを具体的な確認項目とともに人へ回す。Category決定へ進むことは安全保証を意味しない。

Category Mapperは出品可否の最終判断者ではなく、Safety判定を通過した候補を対象市場のどのCategoryへ準備するかを担当する。唯一の正しいleaf Categoryの完全自動確定ではなく、既存出品ツールで一括処理しやすいCategoryと必須属性単位へのBatch Preparationを主目的とする。AI Category predictionは候補予測に限り、Safety BLOCK根拠にしない。Safety判定とCategory Confirmationは別責務とする。AIはFact・商品種別・確認項目・Categoryの候補抽出を補助できるが、最終的な禁止または通過を決定しない。

PHではPhase 1 deterministic BLOCKのmain技術受入後、PH Beta Minimum Definitionを先に置く。Beta Minimum Coreは、(B1) ExpansionとResolverの両入口による候補ASIN取得、(B2) PH Safety、(B3) 確認済みShopee Category IDへの経路、(B4) 確認済みShopee Brand IDまたはNo Brandへの経路、(B5) 未確定を推測で準備完了にしない停止能力、(B6) ASIN・Category ID・Brand ID / No Brandの揃い具合の一意な判別、(B7) 人間が確認済み情報を取得して既存出品ツールへの手入力準備に利用できるhandoffとする。これは外部出品ツールへの自動投入や実際の出品可能を意味しない。

PH Beta Minimum Feasibility Auditと、B1〜B7完成定義に対する旧差分監査は完了し、確認済み`MISSING_IMPLEMENTATION`は0件だった。この結果は履歴として保持する。DEC-0049で切り替えた新Beta完成線のB0 read-only差分監査も完了し、description / features等が現行Gateへ届かないこととPH hemp Rule未実装を確認した。B1では固定15列Candidateを維持した`PRODUCT_TEXT_SAFETY_FACT_V1` sidecarとPH限定hemp Ruleを必要最小限で実装し、独立read-only reviewとKeepa JP production read-onlyのlive技術確認をPASSした。実商品2件でProduct Text Safety Factが`CAPTURED` 2件となり、Candidateからsidecarを経て通常PH Gateまで成立した。Product Textの2件超の取得率とhemp実商品live BLOCKは未確認だが、新しいBeta blockerにはしない。B2ではResolver / Expansionの両入口について、Candidate生成からSafety、exact重複、Category、Brand / No Brand、`listing_ready`、CSV / TXT handoffまで少量実商品で成立した。これはE2E技術確認であり、画像Safetyと重大Safety判断不能時の人間REVIEWという残るBeta MUSTがあるため、Gate PとPH Minimum BetaはHOLDを継続する。Amazon Data Provider Test Bridge Design Gateでは、Keepaを本番標準として維持し、Canopyを明示設定時だけ用いる開発・試験専用providerとして採用した（DEC-0033）。Canopy Test Provider v0.1はmain上の正式技術成果であり、CanopyはKeepa本番確認を代替せず、Safety / Category / Brandの責務は変更しない。外部出品ツールの正式入力契約はBeta MUSTではなく、mandatory attribute全面対応はconditionalのままとする。

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

### 2. 商品自体のSafety

- Shopee Category確定前に、商品自体から判断可能な禁止・確認要件を対象市場を明示して判定する
- 明確な禁止は除外し、判断材料不足は具体的な確認項目を示して人へ止め、それ以外だけをCategory決定へ進める
- Category決定へ進むことは安全保証を意味しない

### 3. Category決定

- Category Mapper（Safety判定を通過した候補について、対象市場ごとのCategory IDを決定・確認する。現在はPHのみ）
- Category predictionとSafety判定を混同しない

### 4. Category依存Safety

- Shopee Category確定後かつ`listing_ready`前に、確認済みのCategory・市場依存禁止条件がある場合は再判定する
- 禁止は除外し、追加確認が必要な対象は人へ止める
- Category自身のversioned Evidenceを優先し、Category階層から独自の一般則を推測しない。Category依存Safetyの網羅的Rule化はBeta前MUSTにしない

### 5. 出品準備

- Category ID
- Brand ID
- 必須属性情報
- 人間確認
- 既存出品ツール向け受け渡し準備

### 6. 出品

- 既存出品ツールを使用
- 正式入力契約は未確認
- 自動接続・自動出品は未承認

## 現在から先の工程

### B0 — 新Beta MUSTのread-only差分監査（完了）

次の10項目について、現行実装を確認済み実装、部分充足、未充足、未確認に区別する。監査中はコード、Rule、辞書、testsを変更せず、未確認事項を新しいBeta blockerへ自動追加しない。

1. Expansion / Resolverの既存機能の継続利用
2. 既出品ASINおよび入力内ASINのexact重複チェック
3. 確定済みNG ASIN / Brand / 知財Evidenceによる除外
4. GABA、hemp等の確定禁止条件の商品情報からの検出
5. titleに加え、description、featuresその他の取得可能文章を対象とする禁止判定
6. 武器等、文章で明確な禁止対象の除外
7. 画像AIによる疑わしい商品の発見と人間確認。AI推定だけでは自動BLOCKしない
8. 判断不能な重大Safety案件のsafe stopと人間確認
9. Category Mapper / Brand / handoffの既存機能の継続利用
10. 少量の実商品による一連の流れの確認とオーナーBeta受入

### B1 — 確認済み不足だけを必要最小限で対応（Product Text Safety実装・review・live技術確認PASS）

B0で確認したdescription / features等の未搬送とPH hemp Rule未実装に対し、固定15列Candidateを維持したProduct Text Safety sidecar、追加Keepa requestなしの共通搬送、PH限定literal substring `hemp`を必要最小限で実装した。独立read-only reviewはPASSし、Keepa JP production read-onlyでは実商品2件で`CAPTURED` 2件、Candidate→sidecar→通常PH Gate成立を確認した。2件超の取得率とhemp実商品live BLOCKは未確認のまま保持し、新しいBeta blockerにはしない。GABA-free、画像AI、Bose、Category Safety、汎用sidecar frameworkは同時実装しない。

### B2 — 少量実商品のE2E全体フロー技術確認（完了）

Resolver入口ではCandidate 1件、Expansion入口ではstrict 1ページから人間追跡対象1件に限定し、両入口でIngredient Safety / Product Text Safety CAPTURED、PH Gate SAFE / ELIGIBLE、入力内exact UNIQUE、既出品exact CLEAR、Category確定、Brand / No Brand確定、`listing_ready = TRUE`、CSV / TXT handoff取得まで成立した。使用したPH既出品CSVは0 ASINで、オーナー確認でもPHショップの既出品は0件だったため、既出品exact CLEARは実態と整合する。Shopee live書込みとコード・Rule・辞書・tests変更は0だった。

この結果は現行機能でE2E全体フローが成立した技術確認であり、Gate P PASSまたはPH Minimum Beta PASSではない。B2を最初から再実行することは次工程にせず、残るBeta MUST対応後に最終オーナーBeta受入を行う。

### B3 — PH 画像Safety・人間REVIEW（事業ルール・selector確定・技術選定へ）

DEC-0051で、対象を画像上で見える武器・武器形状物の疑義発見に限定し、AI単独ではBLOCK、SAFE保証、既存BLOCK解除を行わず、画像AI対象商品の`NO_SIGNAL`以外のAI結果を原則商品単位REVIEWへ止める事業ルールを確定した。人間最終判断は`ALLOW_PREPARATION`と`EXCLUDE`とし、前者は画像由来REVIEWだけを解除し、後者は対象商品だけを準備対象から外す。固定15列Candidateを維持し、画像Safetyは独立sidecarを基本方針とする。

DEC-0052で販売規制ガイドを市場横断のGit外Evidenceとして登録し、DEC-0053でPH画像Safety selectorのBeta範囲を確定した。対象4 root、root不明時の対象化、既存BLOCK優先、未実行とNO_SIGNALの分離はDEC-0053を正本とし、資料索引は `docs/evidence/GUARDRAIL_SOURCE_MANIFEST.csv` を参照する。次の単一作業は「selectorを前提としたPH画像Safety使用技術・最小実装方式の選定」とする。AI provider、API、model、prompt、正式sidecar schema、cache方式、具体的料金は未決定であり、実装範囲の確定前にコード、Rule、辞書、testsを変更しない。Gate P / PH Minimum BetaはHOLDを継続する。

Category 170 / 108 / 62件、Category Safety網羅化、高度な重複判定、確定NGリスト外の広範な知財AI推測、他marketplace、自動出品を新しいBeta blockerへ追加しない。GABA-free matcher差分は既知差分として保持するが本工程に含めない。Boseは既存Evidence上の未接続事項として保持し、画像Safety設計へ混在させず、Beta前の追加実装要否を別途判断する。

### B4 — 残るBeta MUST対応後の最終オーナー受入

B3で確定した設計に基づく必要最小限の対応と検証が完了した後、オーナーへPH Minimum Betaを実務投入してよいかの最終判断を求める。受入まではGate PとPH Minimum BetaをHOLDとする。

### BETA_AFTER_CANDIDATE

- 画像Safetyのtitle trigger、subcategory細分化、全rootの網羅的画像リスク調査（DEC-0053）
- SLS旧Category 170件（strict接続可能62件、未解決108件）の完全追跡
- Category依存Safetyの網羅的Rule化と古いCategoryの後継Category完全特定
- P1c `ADDITIONAL_FACT_REQUIRED` 59件のうち、新Beta MUSTを越えるFact取得・搬送
- 確定済みNGリスト外の知財をAI等で広範囲に推測してBLOCKすること
- ASIN exact一致を越える高度な重複商品判定
- 他marketplace対応と自動出品
- structured REVIEW完成形、API auto-resolution、Shipping / Operational Filter、Category Batch完成形、AI Shadow、Workflow、固定工数削減KPI、詳細E2E時間測定

P1cの成果物、identity、SHA-256、170件・62件・108件の確認済み件数、二段階Safety設計は削除または無効化せず、将来Evidenceとして保持する。Category完全追跡を別名称でBeta前に継続しない。

## 旧Beta前工程（DEC-0049で優先順位を置換・履歴保持）

以下のP0〜P6はDEC-0043時点の履歴であり、DEC-0049以降のBeta前必須順序または自動blockerとして使用しない。各工程の完了済み成果とEvidenceは保持する。

### P0 — PH Guardrail BaselineをBeta MUSTとして正本化する

PH Guardrail BaselineをPH Minimum BetaのMUSTとして正本化し、Gate PをHOLDする。P0はmain統合後にP1へ進む。既存のGate P結果は履歴として保持するが、P0〜P2を経るまで新しい受入根拠として使わない。

### P1a — PH Guardrail Evidence Coverage Inventory

現時点で利用可能・確認可能なPH向け禁止根拠を全件棚卸しする。

### P1b — Evidence disposition

各Evidence項目を`BLOCK`、`REVIEW`、`非対象・根拠不足`へdispositionし、未判断を残さない。

### P1c — 二段階Safetyに基づく技術分類と確定BLOCKのGuardrail登録

DEC-0046の正本化差分がmainへ統合された後、P1bで受入済みの229候補を、Category確定前に判定できるもの、Category確定後に判定するもの、追加Factが必要なもの、Rule境界が未解決なものへ技術的に整理する。その後、確定したBLOCKを`COMMON_BLOCK`と`PH_BLOCK`に区別してGuardrailへ登録し、関連testを行う。具体的なstatus対応、Fact接続、Rule境界は技術設計で確定し、分類前に実装を開始しない。

### P1d — PH Guardrail Baseline受入

`PH_GUARDRAIL_BASELINE_COMPLETE`を受入する。P1d受入までGate PはHOLDを維持する。

### P2 — Gate通常利用導線の簡素化

通常利用の目標フローを次に固定する。

`Expansion / Resolver → Candidate CSV → 市場別Gate → ELIGIBLE / REVIEW / EXCLUDE`

Ingredient Safety sidecar、Rule CSV、SHA binding等の内部安全機構は必要に応じて維持する。ただし、通常利用者に不要な操作は極力隠す。DB化はこのBeta MUSTへ自動追加せず、具体方式は別設計で決定する。

### P3 — Gate P B2 — PH Safety再受入

完成したPH Guardrailを使い、Ingredient Safetyと最新Guardrailを含むGate P B2 — PH Safetyをオーナー実物再受入する。

### P4 — Gate P B1〜B7全体受入

Gate P B1〜B7全体を、実商品・実画面・実業務で受入する。

### P5 — Evidence Packageと第三者独立レビュー

Ingredient Safetyおよび最新Guardrailを含むEvidence Packageを再生成し、第三者独立レビューを行う。実装前の古いEvidence Packageは使用しない。

### P6 — PH Minimum Beta最終受入

第三者レビュー結果を確認後、オーナーがPH Minimum Betaの最終受入を判断する。受入時のみPH実運用へ進む。

### Post-Beta

DEC-0049の`BETA_AFTER_CANDIDATE`、DB化、他市場展開、出品後商品改善ツール、Amazon仕入れ支援ツール等の優先順位を、Beta実利用で得たEvidenceに基づいて再判断する。Post-Betaの開発管理基盤整備はPH実運用の開始条件でも、新しいBeta MUSTでもない。

## 保留

- Workflow層
- SP-APIによるKeepa Expansion全面代替調査（HOLD。Beta実利用後にKeepaコスト、契約、障害、利用制限、運用負荷が実際のボトルネックになった場合だけ再検討）
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
