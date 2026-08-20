# 出品支援ツール完成定義案（V1現行評価とV2目標）

## 文書の状態

候補生成 → 市場別Gate → Category / Brand準備という責務分離は、DEC-0021で決定済みである。DEC-0028はV2の論理責務と実装原則を追加し、Phase 1 deterministic BLOCKとCanopy Test Provider v0.1はmain上の技術成果である。一方、V2のより先の完成目標は未実装である。
この文書は、承認済みPH Minimum Beta完成定義・受入条件を基準にしつつ、V1のより広い完成受入候補とV2の将来目標を整理する草案である。
決定済みの責務分離を変更する文書ではなく、DECISION_LOGの代替にもならない。

## 目的と背景

出品支援ツールは、作業者がASIN、Shopee Category ID、Shopee Brand IDを根拠とともに
確認し、既存出品ツールへ手作業で入力できるようにする。

V2の目的は、安全に出品準備できるASIN数を少ない人手で増やすことである。通常利用UI、質問、判定理由、エラー、操作案内は平易な日本語を優先する。

当初はSGの出品数を増やす目的で候補を広げる機能を作った。SGでのアカウント保護上の
問題を受けてPH向けの市場別機能を急いで追加した。この経緯は、候補を作る機能と、
出品可否を市場別に判断する機能を混同しない理由である。

PHは現在、最初に実画面・実業務で受入確認を行う市場である。候補生成機能そのものを
PH専用にする意味ではない。

## 役割分担

### 出品先市場に依存しない候補生成

- **ASIN Expansion**: 既知ASINを起点に、関連ASIN候補を広げる。
- **ASIN Resolver**: Shopeeに出品されている商品の英字タイトルを起点に、対応するAmazon ASINへ到達する。

両機能は候補を作るだけで、候補がどの市場で出品可能かを決めない。候補が正しいASIN
であるかの確認は必要だが、出品可否の判断とは別である。

### 対象市場ごとの出品判断・準備

1. 作業者が対象市場を選び、出品前保安ゲートで候補を確認する。
2. Gateは対象市場のGuardrail、既出品照合、重複、メタデータを基に、
   ELIGIBLE、REVIEW、EXCLUDEを分ける。
3. ELIGIBLEの候補だけについて、対象市場のCategory ID、Brand ID、必須属性情報を
   確認する。
4. 作業者が確認済みの情報を既存出品ツールへ手入力する。

市場ごとの違いは、Gateのルール、既出品照合、Category ID、Brand ID、必須属性に置く。
自動実行順序、共有状態、外部出品ツールへの自動投入は作らない。

### V2の論理責務と目標

V2では`Candidate`、`FactSnapshot`、`SafetyDecision`、`ReviewCase`、`OperationalFilter`、`CategoryBatch`を論理的に分離する。APIはFact、RuleはDecision、AIはPrediction、HumanはExceptionとし、Gate／GuardrailはFact取得層と決定層を分離する。物理schema、API field、confidence thresholdは実装前の確認まで確定しない。

実効BLOCKは`COMMON_BLOCK ∪ 選択市場BLOCK`とし、BLOCKを後工程で解除しない。structured REVIEWはPASS / BLOCKに必要な不足Factを示し、APIで解決できるものを人間へ出さない。発送条件はSafetyとは別のOperational Filterとする。

Category Mapperは唯一の正しいleaf Categoryの完全自動確定ではなく、Categoryと必須属性単位のBatch Preparationを主目的とする。AI predictionは候補であり正解保証やSafety BLOCK根拠にしない。接続は手動CSVを維持する。

## 完成時の利用者シナリオ

作業者は、次のどちらかの入口から始められる。

1. **既知ASINの入口**: ASIN Expansionで関連候補を作る。
2. **商品名の入口**: ASIN Resolverで英字商品名から候補を探し、確認する。

その後、作業者は対象市場を選んでGateを実行し、ELIGIBLEの候補だけを市場別の
Category / Brand確認へ進める。確認済みのASIN、Category ID、Brand ID、必須属性の
情報をダウンロードまたは画面で確認し、既存出品ツールへ手入力する。

不明、要確認、除外の候補は、出品準備済みとして混ぜず、理由が分かる状態で止める。

## V1のより広い完成受入候補とV2目標

次をすべて満たしたとき、出品支援ツールv1を完成受入の候補とする。

1. ASIN ExpansionとASIN Resolverの両方から、候補を作り、対象市場のGateへ
   手動で渡せる。
2. Gateは対象市場を明示し、REVIEWまたはEXCLUDEの候補を出品準備済みにしない。
   SAFEやELIGIBLEは、規約・法令・出品可否を保証する表現に使わない。
3. 対象市場のCategory / Brand確認では、表示された候補または確認済みローカル情報から
   作業者が選んだものだけを出品準備済みにする。推測したIDは使わない。
4. 少なくとも最初の受入市場で、作業者が両方の候補生成入口のうち必要な入口を使い、
   Gate、Category / Brand確認、既存出品ツールへの手入力準備までを実画面で確認し、
   現状より出品準備に役立つとオーナーが受け入れる。
5. ResolverのASIN到達性能とExpansionの候補品質は、実データによる事前固定の評価方法で
   測定する。測定前に根拠のない件数・正答率を完成条件として固定しない。

PHは最初の受入市場とする。PHの受入が完了しても、他市場のGate、Category / Brand確認、
実業務受入が自動的に完了したことにはならない。

## 現行実装との照合

次表は現行V1の確認済み動作であり、V2機能の実装状況を示すものではない。V2は実装前である。

| 領域 | 確認できた現行の動作 | v1に向けた扱い |
| --- | --- | --- |
| ASIN Expansion | 既知ASINからKeepaを使い関連候補を作る。検索範囲、キャッシュ、CSV出力、Gate用CSV出力がある。 | 候補生成の中核。実Keepa・実業務の受入は未実施 |
| ASIN Resolver | 商品名から外部AI用プロンプトを作り、返答の候補を確認する。対象市場は選ばない。 | 候補生成の中核。到達性能は未評価 |
| 出品前保安ゲート | SG / PHを選択し、市場別辞書でELIGIBLE / REVIEW / EXCLUDEを出す。 | 対象市場の正式な候補選別。PH実業務受入は未実施 |
| Category Mapper | 現在PH限定。現在のGate形式（`PRELISTING_GATE_RESULT_V1`）のPH ELIGIBLE CSVだけを出品準備済みにできる。 | 市場別の出品準備。PH以外は未対応 |
| 既存出品ツール | 貼付用テキストは作れるが、正式な入力契約は未確認。 | 手入力のみ。自動連携は対象外 |

Expansionの旧SG一次判定と`SAFE`出力は、候補生成と市場別判断を混同させるため画面から外す。
ExpansionとResolverは候補をGate用CSVへ渡し、出品可否は市場を選んだ出品前保安ゲートだけで判断する。
Expansion機能そのものやGate内部の市場別Guardrailは削除しない。

## 今回の完成条件に含めないもの

- Keepa、Shopee Catalog API、外部AIの無承認実行
- 実商品データを使う無承認評価
- Shopeeまたは既存出品ツールへの書込み、自動投入、自動出品
- Gate、Category Mapper、既存出品ツール間の自動接続
- PH以外の市場についての実業務受入
- Category Mapper AI Shadow
- 出品後商品改善ツール、Amazon仕入れ支援ツール

## PH Beta Minimum Definition

この節はDEC-0034で承認された、PHで実際に使い始められる最小Betaの完成定義・受入条件である。上記のV1のより広い完成受入候補および後述するV2の完成受入目標とは別に扱う。Betaは完全自動化、外部出品ツールへの自動投入、実際の出品可能の保証、固定工数削減KPIを意味しない。

実物受入は`docs/PH_MINIMUM_BETA_ACCEPTANCE_PROTOCOL.md`に従う。Gate K（Keepa本番標準経路live技術確認）のPASS後だけ、Gate P（PH Minimum Beta実物受入）へ進む。

Beta Minimum Coreは次のB1〜B7とする。

1. **B1 Candidate取得** — ASIN ExpansionとASIN Resolverの両入口で、実利用可能なAmazon ASIN候補を得る経路がある。両入口は候補生成だけを担当し、PH出品可否、Category、Brandを決めない。
2. **B2 PH Safety** — 対象市場PHを明示してGateを実行でき、BLOCK / EXCLUDEを出品準備へ進めず、未解決REVIEWを準備完了に混ぜず、ELIGIBLEだけをCategory / Brand確認へ進める。structured REVIEW完成形やAPI auto-resolution完成形はBeta MUSTではない。
3. **B3 Shopee Category ID** — PHのELIGIBLE候補が確認済みShopee Category IDへ到達する、現実的かつ反復可能な経路がある。完全自動化やAIによるもっともらしいIDの生成だけを確認済みFactとは扱わない。
4. **B4 Shopee Brand ID / No Brand** — PHのELIGIBLE候補が確認済みShopee Brand IDまたは確認済みNo Brandへ到達する、現実的かつ反復可能な経路がある。AI推測だけのBrand IDを確認済みFactとは扱わない。
5. **B5 未確定の安全な扱い** — Category ID、Brand IDその他のBeta準備情報を確認できない候補を、推測値で埋めて準備完了にせず、未確定または要確認として止められる。
6. **B6 Beta準備状態の判別** — Amazon ASIN、確認済みShopee Category ID、確認済みShopee Brand IDまたは確認済みNo Brandが揃ったかを、候補ごとに一意に判別できる。これはShopeeへ実際に出品可能、または外部出品ツールへの完全入力準備済みという表現ではない。
7. **B7 人間への引渡し** — 確認済みのAmazon ASIN、Shopee Category ID、Shopee Brand ID / No Brandを画面またはファイルで人間が取得・確認し、既存出品ツールへの手入力準備に利用できる。自動投入・自動接続はBeta MUSTではない。

B8等の要件は追加しない。

mandatory attribute全面対応は現時点でconditionalであり、Beta MUSTではない。PH実物受入で、mandatory attribute不足により既存出品ツールへの実務的な手入力準備が成立しないと確認された場合だけ、Beta blocker候補としてオーナー判断事項へ戻す。

Beta受入は、B1〜B7にBeta成立を妨げるBLOCKEDがなく、残るPARTIALの通常利用可能性をオーナーが実物で確認し、少量の実商品で一連の導線を実画面・実業務として確認した後に行う。EXCLUDE / 未解決REVIEWや未確認Category / Brandを準備完了に混ぜず、確認済みASIN / Category ID / Brand IDを取得できることを要する。実画面、実データ、実業務の受入はオーナー確認前に完了扱いにしない。

完成定義と現行実装の差分監査は完了し、B1〜B7に対する確認済み`MISSING_IMPLEMENTATION`は0件である。これはBeta完成、Beta受入、実商品、実画面、実業務の受入完了を意味しない。残るBeta MUSTは、ASIN Expansion / ASIN ResolverのKeepa本番標準経路のlive技術確認と、PH Minimum Betaのオーナー実物受入である。実物受入で新たなblockerが判明する可能性は残る。

Canopy Test Provider v0.1とCanopy Resolver / Expansionのlive正常系は技術確認済みであり、B2〜B7はFeasibility Audit上READYである。ただし、PH Minimum Beta全体、実商品による一連の導線、実画面、実業務、Keepa本番標準経路の最終実務確認は、オーナー確認前に受入完了としない。Keepaは本番標準provider、Canopyは明示設定時だけ用いる開発・試験専用providerであり、Canopy結果でKeepa本番確認を代替せず、自動fallbackは行わない。外部出品ツールの正式入力契約はBeta MUSTではなく、自動投入または正式E2E接続を検討する場合のHOLDとする。

SP-APIによるKeepa Expansion全面代替調査はHOLDとする。SP-APIは将来のKeepa依存削減候補であり、Beta MUSTを追加せず、Minimum Beta完成前にExpansion providerとして新規開発しない。Beta実利用後にKeepaコスト、契約、障害、利用制限、運用負荷が実際のボトルネックになった場合だけ再検討する。

Beta後は、実利用でオーナーが実務ボトルネックを報告し、次versionで改善して再利用する。詳細なE2E時間測定はBeta前の必須Gateではなく、必要になった場合のBeta後の改善手段候補とする。

## 次の推奨工程

1. Gate Kの実行条件を確認し、Keepa利用・有料API利用についてオーナーの明示承認を得る。
2. Gate K PASS後だけ、Gate Pで少量の実商品、必要な外部API、実画面によるPH Betaの実業務受入を行う。
3. 実物受入でBeta成立を妨げる事実が確認された場合だけ、別途承認した範囲で対応を判断する。

画面導線のオーナー確認と、Category Mapper入力時のGate結果CSV schema version再検証は完了している。

この段階でオーナーに技術方式の選択を求めない。実業務で「候補を安全に絞れ、確認済みの
情報を手入力準備できれば役立つか」を確認する。
## V2の完成受入目標

このV2の完成受入目標はPH Beta Minimum Definitionとは別の、より先の完成目標である。

PHを最初の受入市場とし、(1) deterministic BLOCK、(2) structured REVIEW + API auto-resolution、(3) 発送条件、(4) Category Batch Builder、(5) mandatory attribute Batch化、(6) exception-only human confirmationを順に成立させる。V1 / V2の契約は区別し、既存V1を破壊しない。

PHでの実画面・実業務において、オーナーが安全に候補を絞り、確認済み情報を既存出品ツールへ手入力準備できる有用性を確認する。ResolverのASIN到達性能とExpansionの候補品質は実データで評価し、根拠のない正答率・件数目標を事前固定しない。PHの受入は他市場の受入を意味しない。

AI Category predictionは候補予測にとどめ、存在しないCategory IDを創作せず、Safety BLOCK根拠にしない。価格、利益率、販売価格、在庫管理は対象外とする。
