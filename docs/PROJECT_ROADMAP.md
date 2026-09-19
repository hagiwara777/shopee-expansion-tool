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

PH Beta Minimum Feasibility Auditと、B1〜B7完成定義に対する旧差分監査は完了し、確認済み`MISSING_IMPLEMENTATION`は0件だった。この結果は履歴として保持する。DEC-0049で切り替えた新Beta完成線のB0 read-only差分監査も完了し、description / features等が現行Gateへ届かないこととPH hemp Rule未実装を確認した。B1では固定15列Candidateを維持した`PRODUCT_TEXT_SAFETY_FACT_V1` sidecarとPH限定hemp Ruleを必要最小限で実装し、独立read-only reviewとKeepa JP production read-onlyのlive技術確認をPASSした。実商品2件でProduct Text Safety Factが`CAPTURED` 2件となり、Candidateからsidecarを経て通常PH Gateまで成立した。Product Textの2件超の取得率とhemp実商品live BLOCKは未確認だが、新しいBeta blockerにはしない。B2ではResolver / Expansionの両入口について、Candidate生成からSafety、exact重複、Category、Brand / No Brand、`listing_ready`、CSV / TXT handoffまで少量実商品で成立した。B3ではPH画像Safety 5商品live検証と人間REVIEWの`EXCLUDE` / `ALLOW_PREPARATION`実務確認を完了し、技術blockerなしを確認した。DEC-0055でオーナーがDEC-0049のBeta MUST 10項目を最終受入したため、Gate PとPH Minimum Betaは`PASS / OWNER_ACCEPTED`とし、PHの少量Beta実利用フェーズへ移行する。Amazon Data Provider Test Bridge Design Gateでは、Keepaを本番標準として維持し、Canopyを明示設定時だけ用いる開発・試験専用providerとして採用した（DEC-0033）。Canopy Test Provider v0.1はmain上の正式技術成果であり、CanopyはKeepa本番確認を代替せず、Safety / Category / Brandの責務は変更しない。外部出品ツールの正式入力契約はBeta MUSTではなく、mandatory attribute全面対応はconditionalのままとする。

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

- Category Mapper（Safety判定を通過した候補について、対象市場ごとのCategory IDを決定・確認する。PHは正式成果あり、SGはPR #82でoffline Category Mapper Minimum Betaをformal mainへ統合済みで、operationはINACTIVEのまま商品単位確認で停止する）
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

### B3 — PH 画像Safety・人間REVIEW（実装・live検証・実務確認完了）

DEC-0051で、対象を画像上で見える武器・武器形状物の疑義発見に限定し、AI単独ではBLOCK、SAFE保証、既存BLOCK解除を行わず、画像AI対象商品の`NO_SIGNAL`以外のAI結果を原則商品単位REVIEWへ止める事業ルールを確定した。人間最終判断は`ALLOW_PREPARATION`と`EXCLUDE`とし、前者は画像由来REVIEWだけを解除し、後者は対象商品だけを準備対象から外す。固定15列Candidateを維持し、画像Safetyは独立sidecarを基本方針とする。

DEC-0052で販売規制ガイドを市場横断のGit外Evidenceとして登録し、DEC-0053でPH画像Safety selectorのBeta範囲を確定した。対象4 root、root不明時の対象化、既存BLOCK優先、未実行とNO_SIGNALの分離はDEC-0053を正本とし、資料索引は `docs/evidence/GUARDRAIL_SOURCE_MANIFEST.csv` を参照する。

DEC-0054でOpenAI Responses API、`gpt-5.6-terra`の画像入力、最大3画像・原則1商品1 request、Structured Outputs、保存不要設定を基本方式として確定した。既存Keepa応答からのroot・画像情報搬送、未実行・AI結果・システム状態の分離、安全なCandidate bindingを持つ専用sidecarを最小実装の境界とする。DEC-0054に基づく最小実装として、両入口の画像情報搬送、専用JSON sidecar、Responses API接続、既存Safety後の画像判定、人間REVIEW UIを追加し、synthetic / mock / AppTestで検証した。続く正式計画では5商品live検証を完了し、疑義あり2/2を`REVIEW`、非該当2/2を`NO_SIGNAL`、境界1件を`REVIEW`として技術blockerなしを確認した。人間REVIEWではW1 `EXCLUDE`とA1 `ALLOW_PREPARATION`からの`ELIGIBLE`復帰、binding、sidecar再読込、rerun保持、既存`BLOCK` / `REVIEW`非解除を実物確認した。

Category 170 / 108 / 62件、Category Safety網羅化、高度な重複判定、確定NGリスト外の広範な知財AI推測、他marketplace、自動出品を新しいBeta blockerへ追加しない。GABA-free matcher差分は既知差分として保持するが本工程に含めない。Boseは既存Evidence上の未接続事項として保持し、画像Safety設計へ混在させず、Beta前の追加実装要否を別途判断する。

### B4 — 最終オーナー受入（完了）

DEC-0055でオーナーがDEC-0049のBeta MUST 10項目を基準にPH Minimum Betaを最終受入した。Gate Pは`PASS`、PH Minimum Betaは`PASS / OWNER_ACCEPTED`であり、PHに限定した少量実務投入を承認済みとする。これは完全なSafety保証、規約適合保証、自動出品完成、外部出品ツール正式契約確認、他marketplace受入、Resolver成功判定を意味しない。

### Beta実利用

PH Minimum Betaを少量の実務へ投入し、最初の実運用で重大事故または実務ボトルネックが発生するかを確認する。改善は実利用で観測した頻度、被害、運用負荷、修正コストに基づいて判断し、既存の`BETA_AFTER_CANDIDATE`をBeta前blockerへ戻さない。

### Category AI Benchmark Ver1 / Category Mapper AI Minimum Beta（main正式受入済み / Luna採用）

現行Category Mapperの判断を入力にせず、商品Evidenceとmarketplace別Shopee Category snapshotだけで
rootからleafまで探索する汎用AI Category Coreを、正式Mapper・AI Shadowと分離して実装する。
local実装、PH / SG合成catalog、Fake Provider tests、独立Streamlit UIは完了した。Fake Providerの
PASSは入力・schema・ABSTAIN・fail closed等の契約確認であり、AI意味理解精度を示さない。

固定100商品でLuna / Terraを同一Prompt V1・Traversal V1・request条件により比較し、モデル選定を
完了した。Minimum BetaのCategory候補提示には`gpt-5.6-luna`を採用し、Terraは精度差が小さい一方で
実コストが約10倍だったため不採用、Solは検証しない。AIは候補提示だけを担当し、Category自動確定、
Safety判断、`manual_review_required`や`listing_ready`等の既存安全機構の解除には使用しない。
Hobbies & CollectionsはLuna / Terraとも0/10の既知弱点として手動確認する。Prompt / Traversal / Hobbies
改善は先行せず、実運用で真のボトルネックになった場合だけ別Version・別判断で行う。Category Mapperへの
Minimum Beta最小統合は、Recommendationを変更しない独立候補、明示実行、未確定行限定、同一leafへの
group consensus、人間採用後の既存Brand確認を維持する方式でlocal実装・mock回帰検証まで完了した。
続く実商品3件の`gpt-5.6-luna` live smokeでは全件`COMPLETED`、retry 0、費用上限内で、人間採用前の
安全条件と採用後のBrand確認を維持した。技術的live smokeと実務受入候補はPASS、blockerなしである。
PR #68を通常のmerge commit方式でmainへ統合し、formal main
`f9426d41961206ad3c2574d74d7b55f16df2304e`上の正式成果として受入済みである。

### SLS Shared Safety（Battery v0.1 formal main正式受入済み）

PH / SGの既存runtimeに対し、SLS Battery要件を現行Candidate情報だけで確定できない候補を
共通`REVIEW`へ止める。単一資産`guardrails/sls_shared/battery_review_rules.csv`の明示11語だけを
v0.1対象とし、市場別BLOCK、Community NG、own penalty、PH / SG市場分離を維持する。
Prelisting Gateの公開契約とCandidate schemaは変更せず、共有Battery `REVIEW`を`ELIGIBLE`にしない。

2162件のSLS Category MatrixはSLS Market Category Rules Minimum Betaとして正本資産化し、
PR #78をmerge commit方式でmainへ統合した。PHは確認済みShopee Unique Category IDにだけJOINし、
canonical taxonomyとPH assetだけをruntimeで読む。CURRENTなCATEGORY_ALLOWだけがready、groups CSV、listing TXTへ進み、
SLS停止状態はCategory / Brand確認済みでも完了表示にならない。MY / TH / TW / VNを含む非PH runtimeは開始していない。
PR #78の製品merge commitは`5079795fd1eb7a4ae1940852b76e2bd2315e0006`であり、source更新やnon-PH runtimeは別タスク・別承認とする。current formal mainはGitで観測する。

### Shopee Open Platform共通認証・Catalog基盤（次の優先工程）

PHの`ShopeeCatalogClient`は既存のread-only Category / Brand / Attribute取得経路として維持するが、現状はPH固定であり、Access Token refreshはCategory Mapperの責務外である。SG以降で市場ごとに認証・Catalog取得を複製実装せず、共通Shopee認証基盤をPHで先行検証してから、marketplace-neutralな共通Catalog Clientを整備する。この順序はSG production Category catalogのsource identity調査を取り消すものではなく、その安全な前提を先に整える変更である。

認証は代表となる認証済みshop単位、Category / Brand / Attribute catalogはmarketplace単位で管理する。各marketplaceでは原則として代表shopを一つ使用し、同一marketplace内の全shopについて同じCatalog masterを重複取得・保存しない。注文・在庫等のshop固有APIのtoken管理は別責務とし、今回のCatalog取得設計へ混在させない。

Token ManagerはCategory Mapperへ埋め込まず、有効なAccess TokenをCatalog Clientへ提供する独立した共通認証責務とする。Access Tokenは常駐タイマー更新を前提にせず、API利用時に有効性を確認し必要な場合だけrefreshするon-demand方式を第一候補とする。refresh時はAccess Tokenだけを更新してRefresh Tokenを失わず、新旧tokenの整合性を保つ。atomic保存方式、TTL、endpoint、request / response contractは後続設計Gateで一次資料または実APIのcurrent contractを確認して確定し、推測の数値を恒久仕様にしない。

token、partner key、refresh tokenその他のcredentialはGit、docs、log、UI平文、snapshot、Evidenceへ含めない。自動refreshの実運用確認前は、既存PHの一時Access Token手入力経路を非常時fallbackとして維持する。refresh失敗時はfail closedとし、既存Safetyや保護済み運用を解除しない。

次の長期工程を現在からの優先順とする。各工程の実装・live API実行・運用開始には、その工程に必要な別scope・設計Gate・Owner承認を要する。

1. **Shopee共通Token Manager Minimum Beta 設計Gate** — marketplaceと代表shopのbinding、credential保存、Access Token有効性確認、Refresh Token更新、refresh失敗時fail closed、秘密情報保護、一時Access Token fallback、PH既存経路保護を設計する。
2. **共通Token Manager最小実装とPH先行検証** — PHのCategory / Brand / Attribute取得と`ph.beta.operation`を壊さず、refresh障害でもSafetyを解除しないことを確認する。
3. **ShopeeCatalogClientのmarketplace-neutral化** — PH用コードをSG用に複製せず、marketplaceを明示bindする共通Category / Brand / Attribute clientとし、未承認marketplaceはfail closedとする。
4. **SG production Category catalog source identity最終確認** — SG代表shopの正式認証contextでread-only確認を行い、`v2.product.get_category`契約、Category ID、parent、leaf、hierarchy、production identityを確認する。source identity未確認なら停止する。
5. **SG production Category catalog import / acceptance** — production responseを共通normalization、SG 6列catalog、全件validation、SG-only replaceへ通す。SLS catalogをCategory masterへ流用しない。
6. **SG実商品Category acceptance** — 少量実商品を人間が確認し、保存済みCategoryを現在catalogで再validationする。この時点でも`listing_ready=false`を維持する。
7. **SG Brand** — production Category確認後にSGの`get_brand_list`経路を確認・接続し、他marketplaceのBrand IDを流用しない。
8. **SG SLS runtime** — Category / Brand後の独立工程として扱い、既存Safetyを解除しない。
9. **SG Minimum Beta完成判定** — Category、Brand、Safety、SLS、handoff条件を別Owner Acceptanceで確認する。`listing_ready=true`、handoff、SG operation ACTIVE化は自動的に行わない。
10. **SG実運用** — 別Owner承認後にだけ検討する。
11. **MY展開** — 共通Token / Catalog基盤を再利用し、MY固有Safety、source identity、production確認だけを追加する。MY runtimeを先行有効化しない。
12. **TH展開** — 同じ共通基盤を再利用し、TH固有差分だけを追加する。TH runtimeを先行有効化しない。

MY / THの具体的な着手順は将来のEvidenceと事業優先順位で変更できるものとし、今回固定しすぎない。

### BETA_AFTER_CANDIDATE

- 画像Safetyのtitle trigger、subcategory細分化、全rootの網羅的画像リスク調査（DEC-0053）
- `gpt-5.6-luna`へのコスト最適化比較、provider複数対応、AI結果cache、その他root拡張（DEC-0054）
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
- SG Brand / SG SLS runtime / SG Handoffの実装（共通Token Manager、PH先行検証、共通Catalog Client、SG production source identity確認の後の別工程）
- MY／THの実装（共通Token / Catalog基盤を再利用する将来工程）
- AI候補の1クリック採用 Ver0.3
- wrong category蓄積 Ver0.4

## 判断方針

- 証拠保存機能の完成だけでResolver成功を宣言しない。
- Resolver成功は英字商品名から正しいASINへの到達性能で判断する。
- 未確認の既存出品ツール契約を実装済みとして扱わない。
- SG Category Mapper Minimum BetaはPR #82でformal mainへ統合済みのoffline製品成果である。正式SG Gate入力、検証済みSG catalog、Category AI Coreのoffline候補契約、商品単位の人間確認、ASIN単位保存を提供する。SG UIのlive OpenAI API経路は閉鎖済みで、現在は手動Category確認だけを提供する。SG operationはINACTIVE、Category確定後も`listing_ready=false`を維持し、Brand、SLS runtime、Handoffは後続独立工程とする。
- MY／THの順序は証拠と事業判断なしに固定しない。
- 出品支援ツールの内部工程間の連携は、必要な場合に別設計ゲートを通す。
- Category Mapper AI Shadowと自動出品は、明示承認なしに開始しない。

## Management Foundation V2

管理基盤Ver2を複数市場開発の共通前提とする。

1. Versioned State / Config / schema、repo外Task Context、Trust Anchor、Generator / Verifierをformal mainへ統合する。
2. PH Beta運用を継続し、`ph.beta.operation`をprotected capabilityとして回帰保護する。
3. SGはoperation INACTIVE / development ALLOWEDを維持する。SG Category Mapper Minimum Betaのoffline実装はPR #82でformal mainへ統合済みであり、`sg.safety.baseline`はprotected capabilityとして維持する。
4. SG Brand / SLS runtime / Handoffへ戻る条件は、SG Category Mapper Minimum Betaとは別の設計Gate、PH/SG保護gate成立、別タスク開始承認である。
5. MY / THはNOT_STARTEDを維持し、capabilityを先行定義しない。

Governance CIはbranch protectionと独立してmandatory checkを評価する。初期checkは
`governance.validate`、`governance.ps51`、`governance.ps7`、`tests.offline`、`protected.ph`、`protected.sg`。

Deferredはcomponent別test細分化、外部Evidence個別期限、cryptographic signature、MY/TH capability定義だけとする。
GUI、外部DB、自動deploy、自動merge、製品新機能は本基盤実装へ含めない。
