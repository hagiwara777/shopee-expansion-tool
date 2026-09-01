# CURRENT WORK

この文書は、現在実行中の作業、再開地点、停止条件の正本です。コードと正式履歴は
Git、重要判断の理由は `docs/DECISION_LOG.md`、長期工程は
`docs/PROJECT_ROADMAP.md` を確認してください。

## 更新ルール

- 実作業の事実、進捗、次の単一作業、停止条件が変わった場合だけ更新する。
- 重要な方針変更は、この文書に理由を重複記載せず `DECISION_LOG.md` に追記する。
- 商品名、CSV本文、秘密情報、長大な日次ログは記録しない。
- Git外成果物は、この文書で定めた最小索引だけを記録する。

## 現在作業

- current_work_type: `PH Minimum Beta / B2 E2E全体フロー技術確認完了 / 画像Safety・人間REVIEW最小設計ゲート / Gate P HOLD`
- current_phase: `B0完了 / B1 Product Text Safety確認完了 / B2 E2E技術確認完了 / 残るBeta MUST設計前 / Gate P HOLD`
- working_branch: `codex/ph-b2-flow-owner-acceptance-sync`
- marketplace: `PH`
- module: `出品支援ツール / Candidate Generation / PH Guardrail / Category Mapper / Brand / Handoff`
- phase: `PH Minimum Beta重大実務リスク中心の完成線 / B2 E2E全体フロー技術確認完了 / 画像Safety・人間REVIEW設計前 / Category完全追跡はBeta後候補 / Gate P HOLD`
- next_action: `PH 画像Safety・人間REVIEW 最小設計ゲート`

latest main `b62be9152b2c1ddc009e304e26a63fe8f33847e0`を基準に、少量実商品のB2全体フローを通常画面で確認した。Resolver入口はCandidate 1件、Expansion入口はstrict 1ページで候補を取得し、人間追跡対象を1件に限定した。両入口ともIngredient Safety / Product Text SafetyはCAPTURED、PH GateはSAFE / ELIGIBLE、入力内exactはUNIQUE、既出品exactはCLEARとなり、Category、Brand / No Brand、`listing_ready = TRUE`、CSV / TXT handoffまで成立した。使用したPH既出品CSVの登録ASINは0件で、オーナー確認でも現在のPHショップに既出品商品は存在せず、今回の既出品exact CLEARは実態と整合する。Shopee live書込み、コード・Rule・辞書・tests変更はいずれも0である。これは現行機能によるE2E全体フロー成立の技術確認であり、Gate P PASSまたはPH Minimum Beta PASSではない。

formal main `0e640efbbe6e0586bc085fd93ad6fd3c0ac7c437`と当時の作業開始時HEADは一致した。DEC-0049に基づくB0 read-only差分監査は完了し、現行Gateへdescription / features等が届かないことと、PH hemp Ruleが未実装であることを確認した。B1では固定15列の`PRELISTING_CANDIDATE_V1`を維持して`PRODUCT_TEXT_SAFETY_FACT_V1` sidecarを追加し、Expansion / Resolverの両入口、Candidate SHA-256 binding、ASIN集合・schema検証、PH Gate、literal substring `hemp` Ruleを共通経路で接続した。旧cacheは`NOT_CAPTURED`、新規応答に承認済み文章fieldがなければ`NOT_AVAILABLE`、Canopyは`PROVIDER_UNSUPPORTED`とし、これらのstatusだけではBLOCK / REVIEWにしない。既存Ingredient Safety sidecar、GABA 6 alias、GABA matcherは変更していない。Gate PはHOLDを維持する。

Product Text Safetyのlocal technical validationは、関連targeted pytest 592件、PH UI必須経路修正後の再確認44件、全pytest 899件で成功した。これらのtestsはsynthetic / mockまたは既存fixtureによる確認である。その後のKeepa JP production read-only確認では、実商品2件でProduct Text Safety Factが`CAPTURED` 2件となり、固定15列Candidateから対応sidecarを経て通常PH Gateまで成立した。Product Textの2件超の取得率とhemp実商品によるlive BLOCKは未確認だが、これらを新しいBeta blockerにはしない。

PR #47のProduct Text Safety実装差分について、GPT独立read-only reviewはPASSした。Keepa live read-only確認についても、GPTがCandidate CSV、Product Text Safety sidecar、通常PH Gate結果画面の実物Evidenceを直接確認し、PASSとして受入した。これはProduct Text Safetyの技術確認結果であり、Gate PまたはPH Minimum Beta全体フローのオーナー受入PASSを意味しない。Gate PはHOLDを維持する。

P1c POST_CATEGORY 170件の確認済み内訳はstrict接続可能62件と未解決108件である。Work Briefの「61件」表記で既存の確認済み件数を変更しない。170件・108件・62件の完全追跡、Category依存Safetyの網羅的Rule化、古いCategoryの後継Category完全特定は`BETA_AFTER_CANDIDATE`へ移し、過去のP1c成果物、identity、SHA-256、分類、二段階Safety原則を履歴・将来Evidenceとして保持する。Category調査を別名称でBeta前に継続しない。

formal main `0d1d58a59c7f3e729e0c305fb367cbde9f693889`でDEC-0047正本化差分のmain統合を確認した。P1c POST_CATEGORY Connection Design v1と3つのGit外artifactはオーナー受入済みであり、identity・完全SHA-256は索引のとおり実物再計算一致した。POST_CATEGORY 170件のstrict照合結果は、current Categoryへ接続可能62件（`CURRENT_ID_EXACT` 62、`CURRENT_FULL_PATH_EXACT_UNIQUE` 0）、未解決108件（`LEGACY_UNRESOLVED` 106、`PARENT_SCOPE_UNRESOLVED` 2）である。108件の受入は未解決監査結果の受入であり、解決済みを意味しない。62件の受入もRule実装・有効化の許可ではない。Category確定後にGuardrail所有のCategory依存Safety判定を行い、問題がない場合だけ`listing_ready`へ進める二段階Safety原則を維持する。P1c implementationとGate PはHOLDを維持する。

Shopee PH Category Taxonomy Freshness AuditとCategory ID exact照合は完了した。2026-08-29のread-only auditでは、Seller Centreだけに存在する79 Category IDとSeller Centre `is_prohibit=true`の79 IDがexact一致した。これは取得dataset間の観測事実であり、Shopee APIの恒久仕様とは扱わない。CodexとClaudeの独立設計レビューはいずれも`ACCEPT_WITH_REQUIRED_CHANGES`で完了し、オーナーは指摘を反映した二段階Safety設計原則を採用した。P1c implementationとGate PはHOLDを維持する。

P1b Evidence disposition v1-r1はオーナー受入済みであり、P1bを完了とする（DEC-0045）。Git外artifactの完全SHA-256は`27641fc0cde3bc3d585f939f9db3aeeb54545283716350554e4c74b1de382deb`で、727件、`BLOCK` 243、`REVIEW` 125、`非対象・根拠不足`（SAFEの意味ではない）359、未分類0である。P1c candidateは`YES` 229、`NO` 498であり、GSA-0659（Bose）は`BLOCK`を維持しつつDEC-0030のRule境界HOLDによりP1c対象外（`NO` / `N/A`）とする。229 candidateはP1cでCOMMON_BLOCK / PH_BLOCK具体化を検討する入力であり、受入だけでRuleを実装・有効化したものではない。P1b受入正本化はPR #41でmainへ統合済みであり、formal main commitは`eb14622d3a8e062a44fec7829212555f4a7cdf75`である。P1c Expressibility Auditは、現行contractで安全に実装可能0件、新しいFactまたはconnection changeが必要189件、安全なRule boundary未解決40件、合計229件とした。旧優先順位ではP1c implementationとP1d受入までGate PをHOLDしていたが、DEC-0049によりP1c完全追跡をBeta前MUSTから外した。

P1b candidateの作業baseはformal main `7a49110caddc62467e010e67e759d3bbb07a002b`である。

旧優先順位ではDEC-0043によりPH Guardrail BaselineをBeta MUSTとしてP0に置き、PR #37のmain統合（formal main commit `0626a6504af15ebc0a1723a13dcac613aef7e676`）後にP1aを開始した。DEC-0049はP0〜P6をBeta前の必須順序とする部分を置き換えた。過去の成果とGate P結果は履歴として保持するが、Gate PまたはPH Minimum Betaの現在のPASS根拠にしない。

P1aの棚卸し後、P1bを始める前にDEC-0044でPH Guardrailの市場別Evidence、community operational evidence、ブランド・IP、許認可、REVIEWの境界と、依存工程前の確定判断の正本化順序を明確化した。PR #39はmainへ統合済みで、formal main commitは`98a16ff12f131912688c9a1885edfbbc605f9f33`である。当時の次の単一作業はP1bの個別Evidence dispositionであり、完了済みの履歴として保持する。

Gate Kの正式技術確認はPASS済みである。Gate PはB1 Candidate、B2 PH Safety、B3 Category、B4 Brand / No Brand、B5 Safe Stop、B6 listing_ready、B7 Human Handoffの全項目を実画面で確認し、B1〜B7をPASSとする。B2ではPH、Candidate 2件、ELIGIBLE 2件、REVIEW 0件、EXCLUDE 0件とshop label UX修正を確認した。B3ではCategory Path `Beauty > Skincare > Toner`、Category ID `100892`を採用した。B4ではCategory Mapper一時認証入力のsecurity reviewをPASS後、承認済みのShopee Brand List read-only取得を1回・retry 0で実行し、No BrandをBrand ID `0`としてオーナーが確定した。B5ではBrand未確定時に出力対象がなく次工程へ進めないこと、B6では2件がlisting_readyになること、B7では2件・1グループのCSV / text handoffを取得できることを確認した。これらは旧優先順位における受入履歴である。商品名、ASIN、CSV本文、credentialはこの正本に記録しない。

オーナーはGate Pの結果画面を実物確認し、問題なしとして受入した。これは旧仕様におけるGate P PASSの受入履歴である。新たにオーナーが確認したPHのGABA成分に関するアカウント凍結報告を、Shopee公式禁止物質の断定ではない運用上のSafety evidenceとして扱い、DEC-0041により第三者独立レビューを一旦保留した。PH Minimum Betaの正式技術判定と最終事業決裁は未実施であり、Gate P PASSをPH Minimum Betaの正式完成と扱わない。Category Mapperは認証情報を更新・永続保存せず、Category / Brand等のread-only取得が必要なときだけオーナー入力のACCESS_TOKENをブラウザsession内で一時利用する。Canopyは開発・試験専用とし、Keepa / JPを本番標準として維持する。

DEC-0035で、B1〜B7のMinimum Beta完成定義に対する確認済み`MISSING_IMPLEMENTATION`は0件と正本化した。その後、Gate KとGate Pの実物受入がPASSした。DEC-0041で保留した第三者独立レビューより先に、DEC-0042でIngredient Safety Factと市場別BLOCK成分辞書の設計原則を正本化し、repo-grounded技術設計を完了した。GABAのowner attestationはGit外Evidenceとして正本化し、Rule V2の`evidence_ref`を`ART-PH-GABA-FREEZE-OWNER-ATTESTATION-V1`、`source_type`を`community_report`、`decision_ref`を`DEC-0042`と一意に確定した。この設計正本化だけではGABA RuleまたはIngredient Safety実装の完了を意味しなかった。Canopyは開発・試験専用providerのままとし、Keepa本番確認を代替しない。

承認済みWORK_BRIEFに基づくIngredient Safety実装とlocal technical validationをbranch上で完了した。`PRELISTING_CANDIDATE_V1`の固定15列と`PRELISTING_GATE_RESULT_V1`を維持し、Keepa既存responseから3成分Factを通常処理の追加request 0で保持する。Candidate最終bytesのSHA-256に結び付く`INGREDIENT_SAFETY_FACT_V1` sidecar、Rule schema `GUARDRAIL_RULE_V2_V2`、既存13 Brand exact ruleの移行、PH GABA 6 alias、Expansion / Resolver / optional Gate uploadを実装した。旧cache markerなしは`NOT_CAPTURED`、Canopyは`PROVIDER_UNSUPPORTED`とし、Fact欠損だけではREVIEW / BLOCKにしない。local technical validationはtargeted pytest 695件、全pytest 868件成功である。

Ingredient Safety実装差分の独立security / compatibility reviewはPASSした。review再実行ではtargeted pytest 579件、全pytest 868件が成功した。Keepa Ingredient Safetyのlive技術確認もPASSした。production / JP / read-onlyのKeepaで実商品2 ASINについてIngredient Safety Fact取得経路、`IngredientSafetyFact`変換、sidecar生成・parser、Candidate SHA binding、ASIN集合、Gate到達を確認した。これらは空のin-memory PH inventoryによる技術確認であり、Gate P B2 PH Safetyのオーナー実物再受入ではない。GABAを含む実商品でのlive BLOCK確認は未実施である。GABA matching / marketplace boundary / BLOCK vetoのPASSは、既存unit testsおよび独立security reviewによるものであり、live BLOCK確認とは区別する。これらは作業branch上の技術検証事実であって、PH Minimum Beta PASS、Gate P PASS、またはB2受入PASSを意味しない。実装前の古いClaude Evidence PackageはSTALEであり、第三者レビュー用に使用しない。

外部出品ツールの正式入力契約はBeta MUSTではなく、自動投入または正式E2E接続を検討する場合のHOLDとする。mandatory attribute全面対応もconditionalのままとし、実物受入で手入力準備の成立を妨げると確認された場合だけBeta blocker候補としてオーナーへ戻す。

PR #29はmainへ統合済みで、当該PRのformal main commitは`471c63ce0d2206f4ab74b1813f9522db121c331d`である。Canopy Test Provider v0.1はmain上の正式技術成果である。`AMAZON_DATA_PROVIDER`は未設定時`keepa`、明示`canopy_test`時だけCanopy REST adapterを選択し、未知値はfail closedとする。Canopy Resolverは1回最大10 ASIN、`CANOPY_VERIFIED`をKeepaと区別し、Candidate CSV V1の15列を維持して`source=asin_resolver_canopy_verified`へ変換する。Canopy Expansionは起点商品、brandによるJP Search 1ページ、候補詳細最大5件のbrand exact matchに限定し、最大7 requests、retryなし、fallbackなし、Keepa SQLite cache no-writeとした。通常UIにprovider選択を追加せず、Canopy modeだけtest表示する。CanopyのHTTP transportはrequestsを使い、API-KEY / Accept / timeout、HTTP分類、retryなし、ASIN完全一致のfail-closedをmockで検証済みである。targeted pytestは119 passed、全pytestは787 passed。オーナー承認済みのlive技術検証では、`B0CP4RLMDB`のProductとResolverがASIN完全一致・title / brandありで成立し、Resolverは1 requestで`FOUND` / `CANOPY_VERIFIED`を返した。Expansionはsource brand取得、Search 20件、有効候補5件、brand exact・ASIN完全一致・titleありの最終候補5件を合計7 requestsで返した。Keepaは本番標準のまま、Canopyは開発・試験専用であり、自動fallbackは行わない。Canopy経路の長期品質・安定性と実商品の網羅確認は未実施である。

PR #24はmainへ統合済みで、formal main commitは`5ebd4270e516d199a8e592298a15723414d2da9a`です。DEC-0030で限定した13 Brand-exact PH_BLOCKはmain上の正式技術成果です。独立V2 rulesetとGuardrail層のdeterministic BLOCK evaluatorを既存`apply_guardrails()`内でV1結果へBLOCK vetoとして合成し、V2非該当時のV1完全互換、malformed rulesetのfail-closed、Gate public interface不変、PH限定有効化を技術検証しました。targeted pytestは`tests/test_guardrails.py`が323 passed、`tests/test_prelisting_gate.py`が58 passed、全pytestは761 passedです。実商品、実データ、実画面、実業務受入は未実施であり、Phase 1の技術受入と業務受入を混同しません。Bose、一般用医薬品、医療用針、その他711候補は対象外のままです。

PH Beta Minimum DefinitionのB1〜B7 Feasibility Auditは完了した。B1 CandidateのKeepa本番標準経路はGate Kで確認済みであり、Expansion / ResolverはともにPASSした。B2 PH Safety、B3 Category ID、B4 Brand ID / No Brand、B5 未確定停止、B6 準備状態判別、B7 Handoffは技術Feasibility上READYであり、BLOCKEDはない。これらはBeta実画面・実商品・実業務受入の完了を意味せず、Gate Pで確認する。Beta前に詳細なE2E人間作業時間を測定せず、`CORE_INFO_READY ASIN / human hour`、Human Touch Rate、固定工数削減目標を必須Gateにしない。mandatory attributeはconditionalであり、structured REVIEW、API auto-resolution、Shipping、Category Batch、AI Shadow、Workflow、外部出品ツールへの自動投入、他市場展開はBeta MUSTではない。

B1 Amazon Data Provider Test Bridge Design Gateは完了した（DEC-0033）。本番標準providerはKeepaのままとし、Canopyは明示設定 `AMAZON_DATA_PROVIDER=canopy_test` 時だけ使うBeta開発・試験専用providerとする。自動fallbackは行わず、Resolverの確認値は `KEEPA_VERIFIED` と `CANOPY_VERIFIED` を区別する。`PRELISTING_CANDIDATE_V1` の15列schemaは維持し、Canopy経路では既存列に `source_verification=CANOPY_VERIFIED`、`source=asin_resolver_canopy_verified` を記録する。Canopy v0.1はResolverを1回最大10 ASIN・retryなし、Expansionを1回最大7 requests・最大5候補・pagination継続なしとし、既存Keepa SQLite cacheへ書き込まない。Safety / Category / Brandの責務と既存の通常UI構造は変更しない。オーナー承認済みのlive技術検証でProduct、Resolver、Expansionの通常経路はrequest上限内で成立した。これはCanopyを本番providerへ変更するものではなく、長期品質・安定性、実画面・実業務受入は未確認である。

DEC-0028で、出品支援ツールV2の目的、責務、論理データ契約、実装順を承認済み方針として正本化しました。これは実装前の設計であり、コード、辞書CSV、Gateロジック、既存V1 schema、物理CSV列、API fieldは変更していません。DEC-0027の727候補とGit外監査成果物は正式辞書へ昇格していません。

三つの独立ツール構成と出品支援ツール優先順位はmain上で受入済みです。開発運用は軽量開発運用v1へ移行し、GPTを必須の伝言役または承認者にしません。リサーチツール定義、現行正本、実装、テストソース、PH Guardrail辞書の読み取り専用整合監査は完了しました。オーナーは、ASIN ExpansionとASIN Resolverを出品先市場に依存しない候補生成の二入口とし、出品可否、既出品照合、Category ID、Brand IDを対象市場ごとの後段処理とする責務分離を確認しました。PHは最初の受入確認市場であり、候補生成をPH専用とする意味ではありません。Codexはこの前提で、完成定義案と候補生成・市場別処理の境界監査を作成しました。主要な経路は方針と整合します。オーナーは、ExpansionまたはResolverで候補ASINを集め、市場を選んだGateで確認し、Category / Brand情報を準備する流れを完成形として確認しました。このため、Expansionの旧SG一次判定とSAFE／監査CSV出力は正式フローから外しました。GPT独立レビューは商品コードの追加修正を求めず、READMEのCSV契約、完成定義の状態と工程、監査時と修正後のテスト根拠、現在地の整合修正を求めました。これらの文書修正後の再確認では、削除した旧SAFE CSVボタンの実際のラベルを直接検査する回帰テストが不足していると指摘されました。Codexは指定された2テストを補強し、全pytest 716件の再実行を完了しました。GPT独立レビューは最終承認済みです。オーナーの画面確認で、通常のResolver利用に不要なEvidence Batchが分かりにくいと分かったため、通常画面から非表示にしました。証跡保存・再開の内部機能は、明示的な開発設定がある場合だけ表示して維持します。続いてオーナーの確認により、Category MapperのPHカテゴリ同期の状態表示と手動同期ボタンも通常画面から非表示にしました。Category／Brand候補を作るCSV入力と推薦機能は維持します。同期管理は明示的な開発設定時だけ表示します。さらに、タブ名を正本の用語に合わせてASIN ExpansionとASIN Resolverへ統一しました。全pytest 719件成功後、オーナーは「候補生成 → 市場別Gate → Category／Brand準備」の画面導線を問題ないと確認しました。PR #15はGitGuardian Security Checks成功後にmainへ統合され、formal main commitは`39f4a4416209509226a10b922c5a8207345aa78c`です。続いてCategory MapperがGate結果CSVを受け取る際、現在の`PRELISTING_GATE_RESULT_V1`だけを受け入れ、空・未知・混在したschema versionを停止するようにしました。関連94件と全pytest 720件が成功しています。Gate結果CSVの再検証は未完了差分ではありません。出品支援ツール全体の完成受入と現行実装との差分は未確定であり、完成済みとは扱いません。

PR #16はGate結果CSVのschema version再検証をmainへ統合し、formal main commitは`a364b42d09afd11ba61b556ead675d677652aa70`です。PH Guardrail一発アウト基準・根拠監査では、PH辞書の89ルール、実装・テスト、Shopee公式ポリシーを照合しました。Guardrailは網羅的な規約適合を約束するものではなく、明確に危険な候補を先に止めることを最優先とします。`ELIGIBLE`は現在のフィルタを通過したことを示すだけで、出品承認や規約・法令適合を保証しません。`REVIEW`は完全にアウトとは言えない候補を人が試すか判断するために残します。PH Guardrailの根拠・カバレッジ監査結果は`docs/PH_GUARDRAIL_EVIDENCE_COVERAGE_AUDIT.md`に記録する。運用ルールの正本は市場別Guardrail辞書CSVとする。オーナー承認済みの分析先行範囲で、既存31 BLOCKルールにKeepa追加情報が役立つかを読み取り専用で整理した。`docs/PH_GUARDRAIL_KEEPA_FIELD_IMPACT_ANALYSIS_DRAFT.md` はレビュー用分析資料であり、辞書CSVを置き換えない。結論はHOLDで、親ASINまたは識別番号による自社ペナルティ品の同一性確認だけが小規模Keepa確認候補として残った。

## 完了・受入済み

- B2少量実商品のE2E全体フロー技術確認を完了した。Resolver入口はCandidate 1件、Expansion入口はstrict 1ページのうち人間追跡対象1件とし、両入口でIngredient Safety / Product Text Safety CAPTURED、PH Gate SAFE / ELIGIBLE、入力内exact UNIQUE、既出品exact CLEAR、Category確定、Brand / No Brand確定、`listing_ready = TRUE`、CSV / TXT handoff取得まで成立した。PH既出品CSVは0 ASINで、オーナー確認でもPHショップの既出品は0件だった。Shopee live書込みとコード・Rule・辞書・tests変更は0だった。これは技術確認であり、Gate PまたはPH Minimum BetaのPASSではない。
- DEC-0049でPH Minimum Beta完成線を重大実務リスク中心へ再設定。旧P1cのCategory完全追跡を`BETA_AFTER_CANDIDATE`へ移し、過去成果・Evidenceは保持。Gate PはHOLD
- P1c POST_CATEGORY Connection Design v1とGit外成果物3件のOWNER_ACCEPTED。170件 = strict接続可能62件 + 未解決108件。108件は追加Evidence対象であり解決済みではなく、62件はRule実装済みではない（DEC-0048）
- Shopee PH Category Taxonomy Freshness AuditとCategory ID exact照合完了（2026-08-29 read-only audit）
- PH Safety二段階設計のCodex・Claude独立レビュー完了（ともに`ACCEPT_WITH_REQUIRED_CHANGES`）とオーナー採用
- DEC-0045 PH Guardrail P1b Evidence dispositionのOWNER_ACCEPTEDとPR #41のmain統合（formal main commit `eb14622d3a8e062a44fec7829212555f4a7cdf75`）
- DEC-0044 PH Guardrail P1b判断基準の正本化とPR #39のmain統合（formal main commit `98a16ff12f131912688c9a1885edfbbc605f9f33`）
- P0 PH Guardrail BaselineのBeta MUST正本化とPR #37のmain統合（formal main commit `0626a6504af15ebc0a1723a13dcac613aef7e676`）
- P1a PH Guardrail Evidence Coverage Inventory。Git外一次Evidence 3件の実物SHA-256が正本索引と完全一致し、固定storage aliasを解決した。P1b dispositionは未実施
- Gate Kの正式技術確認PASS
- Gate P B1〜B7の実物受入PASS
- Gate P結果画面のオーナー実物確認PASS
- Gate P PASS（旧仕様の受入履歴。PH Minimum Beta正式完成ではない）
- Ingredient Safety Factと市場別BLOCK成分辞書の設計正本化（DEC-0042）
- Ingredient Safety Fact transport、SHA-bound sidecar、Rule V2 V2、PH GABA deterministic BLOCK、Expansion / Resolver / Gate / UIのbranch実装とlocal technical validation完了（targeted 695件、全pytest 868件、外部API 0）
- Ingredient Safety実装差分の独立security / compatibility review PASS（再実行: targeted 579件、全pytest 868件）
- Keepa Ingredient Safety live technical verification PASS（production / JP / read-only、実商品2 ASIN、空のin-memory PH inventoryによる技術確認）。これはGate P B2 PH Safetyのオーナー実物再受入ではない
- PR #29をmainへ統合。formal main / current base `471c63ce0d2206f4ab74b1813f9522db121c331d`上でCanopy Test Provider v0.1を正式技術成果として受入（全pytest 787件成功）
- Resolverの読み取り専用仕様監査完了
- 過去成果物の証拠回収監査完了
- 候補なし21件の停止工程は過去証拠から復元不能
- Evidence Gate Liteの3作業試行完了
- 実行記録フォーマットv0.1.1 final受入済み
- テンプレートv0.1.1 finalの正本SHA再確定
- Handoff Contract v1を適用
- 固定30件証跡パッケージ初回監査は、許可された探索範囲で完全な元入力を発見できずSTOP
- 完全SHAとproducer記録を持つ固定30件入力候補を回収
- JPH→R対応監査は、実行記録欠如と30/30タイトル不一致によりSTOP
- 回収TSVは歴史的初回exportの入力として未証明
- 再現可能な固定30件基準実行の設計ゲート完了
- 必要性分類 `RESOLVER_CHANGE_REQUIRED`
- 回収TSVを新規基準実行専用としてオーナー受入
- Resolver証拠永続化改修を承認
- テンプレート最小補強を承認
- 外部AI・Keepa・実データ実行は未許可
- Resolver証拠永続化実装のbranch技術検収完了
- Resolver関連122件成功
- 全pytest 696件成功
- オーナー実画面確認完了
- Excel／Guide rev2オーナー正式受入完了
- PR #7の全差分についてChatGPT正式技術検収完了
- PR #7 main統合完了
- formal main commit `8f664cdb42edc521371c389f6ad72ac7e0f3aecd`確認完了
- Resolver証拠永続化実装をmain上の正式成果として受入
- 事業全体フローの設計ゲート完了
- PR #8の正本3文書差分についてChatGPT正式検収完了
- branch commit・通常push・Draft PR #8作成完了
- PR #8 main統合完了
- formal main commit `6fa608f807538ba442164d506c8f26551234b790`確認完了
- DEC-0015と事業全体フロー・ロードマップをmain上の正式成果として受入
- GPTチャット切替基準のbranch差分についてChatGPT正式技術検収完了
- GPTチャット切替基準のcommit・通常push許可判断完了
- GPTチャット切替基準のcommit・通常push完了
- GPTチャット切替基準のDraft PR #9作成完了
- PR #9初回正式検収はno-PR FORMAL作業の閉鎖経路不足により差戻し
- no-PR閉鎖経路と未確定戻し先検出の修正・通常push完了
- PR #9修正後全差分のChatGPT正式再検収完了
- PR #9 main統合完了
- formal main commit `87ed73115652c181d4e25da585a3f6104f94f6a5`をChatGPTがGitHubから直接確認完了
- DEC-0016、GPTチャット切替基準、WORK_BRIEF canonical field、静的検証をmain上の正式成果として受入
- 既存出品ツール契約・PH工程接続の読み取り専用監査完了
- 読み取り専用監査結果をChatGPTが正式技術結果として受入
- `EXTERNAL_CONTRACT_UNCONFIRMED`
- Candidate生成からPrelisting Gate、Category Mapper、listing-tool向けtextまでの内部受け渡し候補をコード・テストソースで確認
- テストは未実行であり、実行成功としては受け入れていない
- 端から端の接続可能性は未確認で、停止境界は外部出品ツール契約およびShopee出品区間
- READMEのPrelisting Gate対応市場記載と実装のCONTRADICTIONを確認
- Gate eligible CSVのgate_schema_version再検証不足を確認
- オーナー確認により、Shopee事業で開発する対象は三つの独立ツールであることを確認
- 三つのツールは相互連携しないことを確認
- 一つ目の出品支援ツール完成を現在の最優先とする設計ゲート完了
- 出品支援ツールの中核成果はASIN、Shopee Category ID、Shopee Brand ID
- 一つ目の優先は開発順序であり、三ツール間の技術的依存ではないことを確認
- 外部出品ツールへの自動接続と中核情報取得を別境界として整理
- 外部契約証拠回収の開始Gateは、対象製品・一次資料不足によりSTOP。これは証拠回収を開始できなかった事実であり、出品支援ツール中核開発全体の停止理由ではない。
- 三独立ツール構成・出品支援優先順位のbranch差分をChatGPTが正式技術受入
- commit・通常push・Draft PR作成をChatGPTが許可
- 三独立ツール構成・出品支援優先順位のcommit・通常push完了
- Draft PR #10作成完了
- PR #10の全差分をChatGPTが正式技術受入
- PR #10をReady for reviewへ変更
- PR #10をmerge commit方式でmainへ統合
- merge commit `2e536af7478a0ad53c52622146e52088289333d6`をChatGPTがGitHubから直接確認
- DEC-0017、三つの独立ツール構成、出品支援ツール優先順位、更新後ロードマップをmain上の正式成果として受入
- READMEのPrelisting Gate対応市場記載を実装に合わせて修正し、PR #13をmainへ統合
- リサーチツール定義、現行正本、実装、テストソース、PH Guardrail辞書の読み取り専用整合監査完了。関連ローカルテスト541件成功。実データ・実画面・実業務受入および出品支援ツール全体の完成判定は未実施
- 候補生成と市場別処理の責務分離に対する読み取り専用差分監査完了。共通候補CSV、Gate市場選択、PH Category MapperのGate通過条件を確認。Expansion画面のSG固定一次判定を未完了差分として記録
- オーナーが、Expansion／Resolver → 市場別Gate → Category / Brand準備を完成形として確認。Expansionの旧SG一次判定とSAFE／監査CSV出力を正式フローから外す修正・関連テスト完了（全pytest 716件成功）
- Category Mapper入力時にGate結果CSVの`PRELISTING_GATE_RESULT_V1`を再検証し、空・未知・混在したschema versionを停止する修正・関連94件および全pytest 720件成功
- PR #16をmainへ統合。formal main commit `a364b42d09afd11ba61b556ead675d677652aa70`
- PH Guardrail一発アウト基準・根拠監査完了。PH 89ルール、実装・テスト、Shopee公式ポリシーを照合し、明確な一発アウト候補の遮断を最優先、その他の不確実な候補はREVIEWとして人が判断する方針を記録
- GPT独立レビュー最終承認済み。商品コードの追加修正は不要。正本文書の整合修正と、実際の旧SAFE CSVボタン名を直接検査する2箇所の回帰テスト補強を完了（全pytest 716件成功）
- オーナー画面導線フィードバックにより、通常のResolver画面からEvidence Batchを非表示化。明示的な開発設定時だけ内部機能を表示し、全pytest 717件成功
- オーナー画面導線フィードバックにより、通常のCategory Mapper画面からPHカテゴリ同期の状態表示・手動同期を非表示化。CSV入力と推薦機能は維持し、全pytest 719件成功
- オーナー画面導線フィードバックにより、タブ名をASIN Expansion・ASIN Resolverへ統一。全pytest 719件成功
- オーナーが、内部管理UIの非表示とASIN Expansion／ASIN Resolverを含む画面導線を確認し、問題ないと受入

## 固定30件評価の受入済み結果

- marketplace: `PH`
- module: `ASIN Resolver・ChatGPT-Codex運用基盤`
- phase: `固定30件評価受入後・21件再評価準備前`
- 固定評価コホート: 元Shopee商品30件
- Amazon候補を取得できた元Shopee商品: 9件
- Amazon候補なしの元Shopee商品: 21件
- 候補取得率（元商品単位）: 30.0%（9 / 30）
- MATCHありの元Shopee商品: 8件
- Amazon候補: 13件
- MATCH（Amazon候補単位）: 9件
- VARIANT_MATCH（Amazon候補単位）: 2件
- UNCERTAIN（Amazon候補単位）: 0件
- MISMATCH（Amazon候補単位）: 2件
- 完全一致率（Amazon候補単位）: 69.2%（9 / 13）
- Keepa確認: 13候補すべて確認済み
- PH Prelisting Gate: 13候補すべて `ELIGIBLE`

元Shopee商品単位の候補取得状況と、Amazon候補単位の同一性判定は分けて集計します。
上記はユーザー確認済みかつオーナー受入済みの実運用結果であり、Git、テストレポート、
CI成果物で再確認された事実ではありません。コード機能の対応市場を証明する情報としても
扱いません。

## Git外成果物索引

| artifact_id | 種別・版 | ファイル名 | SHA-256 | producer task | 受入状態 | storage alias | 用途 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ART-PH-ASIN-EXEC-RECORD-V0.1.1 | Excel実行記録テンプレート v0.1.1 | `PH_ASIN_Resolver_Execution_Record_v0.1.1_final.xlsx` | `d150be6a552d0ef212f0ee4965f11f0c8f324eacbf3d8c56e05db07efd8d616e` | `PH_ASIN_Resolver_実行記録v0.1設計` | `OWNER_ACCEPTED` | `ARTIFACT_ROOT/HANDOFF_EXECUTION_RECORD/PH_ASIN_Resolver_Execution_Record_v0.1.1_final.xlsx` | 21件再評価の工程・証拠記録 |
| ART-PH-ASIN-EXEC-GUIDE-V0.1.1 | 非エンジニア向け記入Guide v0.1.1 | `PH_ASIN_Resolver_Execution_Record_v0.1.1_Guide.txt` | `642fe64970efbb83d7e6d175a2c9bde08474f596b004b952429bad6252e15e7e` | `PH_ASIN_Resolver_実行記録v0.1設計` | `OWNER_ACCEPTED` | `ARTIFACT_ROOT/HANDOFF_EXECUTION_RECORD/PH_ASIN_Resolver_Execution_Record_v0.1.1_Guide.txt` | 実行記録テンプレートの記入手順 |
| ART-PH-FIXED30-BASELINE-INPUT-V1 | 固定30件基準入力 v1 | `PH_Japan_AI_Eval_Resolver_Input_V1.tsv` | `32e2dcc21f6820134d7919bbc572e1f91781082cd1d28eee892c3213aaa3d5e1` | `PH_Japan_AI_Eval_Selection_Report_V1.md` | `OWNER_ACCEPTED_FOR_NEW_BASELINE_ONLY` | `LOCAL_RECOVERED_PH_FIXED30_INPUT` | 新規固定30件基準実行専用入力 |
| ART-PH-ASIN-EXEC-RECORD-V0.1.2-CANDIDATE-REV2 | Excel実行記録 v0.1.2 candidate rev2 | `PH_ASIN_Resolver_Execution_Record_v0.1.2_candidate_rev2.xlsx` | `054f771328b9be4d128c42e650791a22f6c0e4bab9892bb8ebd9fb0ca98e4f7b` | `PH ASIN Resolver 証拠永続化実装` | `OWNER_ACCEPTED` | `LOCAL_ARTIFACT_ROOT/HANDOFF_EXECUTION_RECORD/candidate/v0.1.2/` | PH固定30件の人間可読実行記録 |
| ART-PH-ASIN-EXEC-GUIDE-V0.1.2-CANDIDATE-REV2 | 非エンジニア向け実行Guide v0.1.2 candidate rev2 | `PH_ASIN_Resolver_Execution_Record_v0.1.2_Guide_candidate_rev2.txt` | `7e55527e6eee6288b679db37937954be1cb8ccd23b51a327eea2171aa6e59540` | `PH ASIN Resolver 証拠永続化実装` | `OWNER_ACCEPTED` | `LOCAL_ARTIFACT_ROOT/HANDOFF_EXECUTION_RECORD/candidate/v0.1.2/` | 非エンジニア向け実行Guide |
| OWNER_SOURCE_SLS_PROHIBITED_CATEGORY | SLS出品可否確認表・2025年3月17日適用 | `【SLS対象マーケット】SLS出品可否確認表（Prohibited Category List）2025年3月17日適用.xlsx` | `ee68151aa951921dfb7c8a5ea76ea67441342b5be5511d4b18905591e4c621c2` | オーナー提供（producer metadata独立確認未実施） | `OWNER_PROVIDED_SOURCE / NOT_CANONICAL` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Sources/【SLS対象マーケット】SLS出品可否確認表（Prohibited Category List）2025年3月17日適用.xlsx` | P1aで実物SHA-256一致を確認。P1bで具体的なBLOCK／REVIEW／非対象・根拠不足を判断 |
| OWNER_SOURCE_COMMUNITY_NG_LIST | コミュニティNGリスト・版指定なし | `ＮＧリスト.xlsx` | `82a4b72cfdfa53fdfec87f00685ea3f81ced6bde747e54a71155e56ef92312d1` | オーナー提供（producer metadata独立確認未実施） | `OWNER_PROVIDED_SOURCE / NOT_CANONICAL` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Sources/ＮＧリスト.xlsx` | P1aで実物SHA-256一致を確認。P1bで具体的なBLOCK／REVIEW／非対象・根拠不足を判断 |
| ART-PH-GABA-FREEZE-OWNER-ATTESTATION-V1 | Owner Attestation v1 | `PH_GABA_Freeze_Community_Report_Owner_Attestation_v1.md` | `cc6b369250bedb0a99c9731e438e420ee1e2bccd14721e75546aa2f191919a88` | `Owner attestation recorded by Codex` | `OWNER_ATTESTATION_RECORDED_NOT_INDEPENDENTLY_VERIFIED` | `LOCAL_GITEXCLUDED_PH_GABA_EVIDENCE_V1` | PH GABA deterministic BLOCK Rule V2の`evidence_ref`。Rule実装時はartifact ID / SHA / index照合のみ必須で、原コミュニティ投稿の実物アクセスは不要 |
| OWNER_SOURCE_PH_RESTRICTION_IMAGE | PH制限参考画像・元資料版未確認 | `2026-08-13_121116.png` | `7df6f6196b7ad4ac7a63a380f3eb3c03a3b6ab661bd4941152b6a4484196a681` | オーナー提供（producer metadata独立確認未実施） | `OWNER_PROVIDED_SOURCE / NOT_CANONICAL` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Sources/2026-08-13_121116.png` | P1aで実物SHA-256一致を確認。P1bで具体的なBLOCK／REVIEW／非対象・根拠不足を判断 |
| ART-PH-GUARDRAIL-P1B-DISPOSITION-CANDIDATE-V1 | P1b Evidence disposition candidate v1 | `PH_GUARDRAIL_P1B_DISPOSITION_CANDIDATE_v1.csv` | `f1daed1bcdcb1388d42859b9050b216d665c0dff6853feb3fa4229f662bcae19` | `PH Guardrail Baseline P1b Evidence disposition` | `P1B_CANDIDATE / OWNER_ACCEPTANCE_PENDING / CHATGPT_RETURNED_FOR_CORRECTION` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/PH_GUARDRAIL_P1B_DISPOSITION_CANDIDATE_v1.csv` | 修正元を保持。727件のP1b disposition、既存V1/V2 coverage、旧P1c候補scope hint。辞書・Rule V2・Candidate schemaの正本ではない |
| ART-PH-GUARDRAIL-P1B-DISPOSITION-CANDIDATE-V1-R1 | P1b Evidence disposition candidate v1-r1 | `PH_GUARDRAIL_P1B_DISPOSITION_CANDIDATE_v1_r1.csv` | `27641fc0cde3bc3d585f939f9db3aeeb54545283716350554e4c74b1de382deb` | `PH Guardrail Baseline P1b Evidence disposition` | `OWNER_ACCEPTED` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/PH_GUARDRAIL_P1B_DISPOSITION_CANDIDATE_v1_r1.csv` | P1b正式disposition。727件、BLOCK 243、REVIEW 125、非対象・根拠不足 359、P1c candidate YES 229 / NO 498。P1c技術分類v1-r1の受入済み入力 |
| ART-PH-GUARDRAIL-P1C-TECHNICAL-CLASSIFICATION-CANDIDATE-V1-R1 | P1c technical classification candidate v1-r1 | `PH_GUARDRAIL_P1C_TECHNICAL_CLASSIFICATION_CANDIDATE_v1_r1.csv` | `fadb8d18aec2dd8ac0453d608fd643b421d5fc7ec7f24b09f33562a3b121e68f` | `Codex / PH Guardrail P1c Owner Decisions Applied` | `OWNER_ACCEPTED` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/` | 229件。PRE 0、POST 170、ADDITIONAL_FACT_REQUIRED 59、RULE_BOUNDARY_UNRESOLVED 0。分類受入でありRule実装ではない |
| ART-PH-GUARDRAIL-P1C-OWNER-DECISION-QUEUE-V1-R1 | P1c owner decision queue v1-r1 | `PH_GUARDRAIL_P1C_OWNER_DECISION_QUEUE_v1_r1.csv` | `16d17bad452ead487769f5a51c104c96b6e9c24d7d256a1538f8e302e897e707` | `Codex / PH Guardrail P1c Owner Decisions Applied` | `OWNER_ACCEPTED` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/` | 残件0。15件のowner decisionを分類へ反映済み |
| ART-PH-GUARDRAIL-P1C-TECHNICAL-CLASSIFICATION-SUMMARY-V1-R1 | P1c technical classification summary v1-r1 | `PH_GUARDRAIL_P1C_TECHNICAL_CLASSIFICATION_SUMMARY_v1_r1.md` | `5cf4f313e94f3e1cbddc599a92e6a22419c345d44ee91633779b7209baa0e434` | `Codex / PH Guardrail P1c Owner Decisions Applied` | `OWNER_ACCEPTED` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/` | 4分類、hemp、GABA、武器を持つキャラクター玩具の境界と未実装事項を要約 |
| ART-PH-SHOPEE-CATEGORY-SNAPSHOT-20260829-V1 | Shopee PH Category snapshot v1 | `SHOPEE_PH_CATEGORY_SNAPSHOT_2026-08-29_v1.csv` | `16cc9bcd0be87326e2d221bcf113f54a99b2d4698f3e911abb2878611b9e8211` | `Codex` | `AUDIT_OUTPUT_PENDING_REVIEW` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/` | 2026-08-29 Open Platform Category snapshot。実物とSHA-256を確認済み |
| ART-PH-GUARDRAIL-P1C-POST-CATEGORY-MAPPING-CANDIDATE-V1 | P1c POST_CATEGORY mapping candidate v1 | `PH_GUARDRAIL_P1C_POST_CATEGORY_MAPPING_CANDIDATE_v1.csv` | `f12b96dbe8a073c67a5d6bc75b0c542431b956cc50023321c617d130566c2ecd` | `Codex / PH Guardrail P1c POST_CATEGORY Connection Design` | `OWNER_ACCEPTED` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/` | 170件。strict接続可能62件、未解決108件。62件の受入はRule実装許可ではない |
| ART-PH-GUARDRAIL-P1C-POST-CATEGORY-UNRESOLVED-V1 | P1c POST_CATEGORY unresolved v1 | `PH_GUARDRAIL_P1C_POST_CATEGORY_UNRESOLVED_v1.csv` | `b61d2d78149ad2b8bd50193d660ae63486b7dc825c2b0d694fc51bfc1f4218c9` | `Codex / PH Guardrail P1c POST_CATEGORY Connection Design` | `OWNER_ACCEPTED` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/` | 未解決108件。LEGACY 106、PARENT_SCOPE 2。受入は解決済みを意味しない |
| ART-PH-GUARDRAIL-P1C-POST-CATEGORY-CONNECTION-DESIGN-V1 | P1c POST_CATEGORY connection design v1 | `PH_GUARDRAIL_P1C_POST_CATEGORY_CONNECTION_DESIGN_v1.md` | `7f46486883f1b96f1631d0fc5a6f4ac398f066ad7ba691cbbf243ce104e461ee` | `Codex / PH Guardrail P1c POST_CATEGORY Connection Design` | `OWNER_ACCEPTED` | `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/` | strict mapping基準、Category MapperとGuardrailの責務分離、二段階Safety、後続内部interface方針 |
| GAR-AUD-CLASSIFICATION-CANDIDATES | 727候補詳細分類・版指定なし | `classification_candidates.csv` | `b6c0329e1d5d63a38507c34588ca95e0c8483a05614c4bb711f27ea0a4dc2832` | Guardrail 3資料監査 | `GENERATED_AUDIT_CANDIDATE / NOT_CANONICAL` | `LOCAL_GITEXCLUDED_GUARDRAIL_AUDIT_CLASSIFICATION_CANDIDATES` | 727候補の詳細分類。実物アクセス確認済み |
| GAR-AUD-SUMMARY | 監査要約・版指定なし | `audit_summary.md` | `0f76e38904c6f4eeaa6be3338f75dbb15c10725260b5e0ba2451a431d14efeb1` | Guardrail 3資料監査 | `GENERATED_AUDIT_CANDIDATE / NOT_CANONICAL` | `LOCAL_GITEXCLUDED_GUARDRAIL_AUDIT_SUMMARY` | 監査要約。実物アクセス確認済み |
| GAR-AUD-EXISTING-DICTIONARY-COMPARISON | 既存辞書比較・版指定なし | `existing_dictionary_comparison.csv` | `c5a2c6faaf5d24ca722d406e571bcdd669c1a271e5779c96a6d2be6370cbd180` | Guardrail 3資料監査 | `GENERATED_AUDIT_CANDIDATE / NOT_CANONICAL` | `LOCAL_GITEXCLUDED_GUARDRAIL_AUDIT_EXISTING_DICTIONARY_COMPARISON` | 既存89ルールとの比較。実物アクセス確認済み |
| GAR-AUD-NEW-CANDIDATE-EXISTING-COVERAGE | 新候補既存辞書カバレッジ比較・版指定なし | `new_candidate_existing_coverage.csv` | `e545583f8b3765ddecadc6878128f95e446bd358bfb2ea3f7162475495b9b08b` | Guardrail 3資料監査 | `GENERATED_AUDIT_CANDIDATE / NOT_CANONICAL` | `LOCAL_GITEXCLUDED_GUARDRAIL_AUDIT_NEW_CANDIDATE_EXISTING_COVERAGE` | 新候補363件と既存辞書の比較。実物アクセス確認済み |

P1a対象のGit外一次Evidence 3件は、上記の`LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Sources/`に固定保存する。Git管理対象にはせず、更新または差替えが必要な場合は次の作業開始時に完全SHA-256を再照合する。

## 未完了事項

- Product Textの2件超の取得率とhemp実商品によるlive BLOCKは未確認だが、新しいBeta blockerにはしない
- 画像でしか判別しにくい武器等について、AIで疑わしい商品を発見し、自動BLOCKせず人間確認へ回すBeta MUST
- 重大Safetyで判断不能な商品を`listing_ready`へ進めず、人間REVIEWへ止めるBeta MUST
- 上記2件の残るBeta MUST対応後に行うPH Minimum Betaの最終オーナー受入。Gate PはそれまでHOLD
- `BETA_AFTER_CANDIDATE`: P1c POST_CATEGORY 170件（strict接続可能62件、未解決108件）の完全追跡、Seller Centre Category Evidenceの追加照合、62件の個別Rule scope review、Category依存Safetyの網羅的Rule化、古いCategoryの後継Category完全特定
- `BETA_AFTER_CANDIDATE`: P1c `ADDITIONAL_FACT_REQUIRED` 59件のうち、新Beta MUSTの重大リスク対応を越えるFact取得・搬送設計
- `BETA_AFTER_CANDIDATE`: 確定済みNGリスト外の知財の広範推測、高度な重複商品判定、他marketplace、自動出品、および旧P0〜P6のうち新Beta MUSTに含まれない全面工程
- 既存GABA Rule V2が`GABA-free`までBLOCKするmatcher差分の別修正（既知差分として保持し、今回の次工程には含めない）
- Boseは既存Evidence上の未接続事項として保持し、画像Safety設計へ混在させず、Beta前に追加実装が本当に必要かを別途判断する
- GABAを含む実商品によるlive BLOCK確認
- Canopyの長期品質・安定性、実商品の網羅確認
- Category ID等を扱うGuardrail候補データ構造・判定単位・根拠種別の設計
- Gate P branch全体の第三者独立レビュー（P5で、Ingredient Safetyと最新Guardrailを含むEvidence Packageを再生成した後に実施する。実装前の古いClaude Evidence Packageは使用しない）
- 残るBeta MUST対応後のPH Minimum Beta正式技術判定とオーナー最終事業決裁
- ASIN到達性能の評価
- 出品後商品改善ツールの将来優先順位判断
- Amazon仕入れ支援ツールの将来優先順位判断
- 外部既存出品ツールの正式入力テンプレートまたは仕様書の読み取り専用証拠回収（自動投入またはE2E接続を検討する場合）
- 外部出品ツールの正式ヘッダー順序、エンコーディング、必須値、カテゴリ・ブランド・属性、バリエーション・SKU・在庫契約の確認（同上）
- 出品支援ツール内部工程の接続設計ゲート（必要な場合）
- 外部AI・Keepa・実データ実行の別決裁
- 新規固定30件基準実行
- Resolver成功基準と続行・保留・打ち切り判断
- SG／MY市場展開設計
- TH優先順位判断

## 旧・次の単一作業（DEC-0047で完了）

DEC-0046正本化差分のmain統合確認後、P1cの受入済み229候補をCategory確定前に判定できるもの、Category確定後に判定するもの、追加Factが必要なもの、Rule境界が未解決なものへ技術的に分類する。

## 旧・次の単一作業（DEC-0048で完了）

本正本化差分のmain統合確認後、受入済みPOST_CATEGORY 170件をcurrent Shopee Categoryへ安全に接続する技術設計を開始する。ADDITIONAL_FACT_REQUIRED 59件の実装は開始しない。

## 旧・次の単一作業（DEC-0049で置換）

本正本化差分のmain統合確認後、108件を解決するためのSeller Centre Category Evidenceのidentity確定とstrict再照合をread-onlyで実施する。DEC-0049により、このCategory調査はBeta前の次作業ではなく`BETA_AFTER_CANDIDATE`とする。

## 次の単一作業

PH 画像Safety・人間REVIEW 最小設計ゲート

## 停止条件

- 残るBeta MUSTの対応と最終オーナーBeta受入までは、Gate P PASSまたはPH Minimum Beta PASSとして扱わない。
- B2全体フローは現行機能によるE2E技術確認完了として扱い、新しい不具合Evidenceがない限り最初からの再実行を次工程にしない。
- 次工程は画像Safety・人間REVIEWの最小設計ゲートに限定し、承認された実装範囲が確定する前にコード、Rule、辞書、testsを変更しない。
- 重大Safetyで判断不能な商品を`listing_ready`へ進める設計にせず、人間REVIEWへ止める。
- B0未確認事項または理想的な追加機能を新しいBeta blockerへ自動追加せず、個別に承認された不足以外のdictionary registration、Rule changes、code changes、関連testsを開始しない。
- 未解決108件のSeller Centre Category Evidence調査・strict再照合、62件のRule設計、Category依存Safetyの網羅的Rule化、古いCategoryの後継Category完全特定を、Beta前に別名称で再開しない。
- 未解決108件を解決済みとして扱わず、62件をRule実装済みまたは有効化済みとして扱わない。POST_CATEGORY 170件を実装完了、ADDITIONAL_FACT_REQUIRED 59件をFact取得済み、または229件をRule登録済みと扱わない。
- 未解決108件をfuzzy、AI、leaf名だけの一致、親Categoryから子Categoryへの推測継承で接続しない。
- Seller Centre Category Evidenceはidentityを固定してから使用し、未索引のローカルファイルを推測で正式根拠にしない。
- GABA-free matcher差分を本正本化作業へ混在させず、別の承認済み修正までRule、辞書、code、testsを変更しない。
- 画像AIの推定だけで自動BLOCKせず、疑わしい重大Safety案件は人間確認へ止める。
- Boseの既存Evidence上の未接続事項を画像Safety設計へ混在させず、追加実装の要否は別途判断する。
- 確定済みNGリスト外の知財をAI等で広範囲に推測してBLOCKしない。
- 今回のKeepa Ingredient Safety live技術確認を、オーナー実物受入またはGABA実商品live BLOCK確認として扱わない。
- GABAを含む実商品によるlive BLOCK確認を、既存unit testsおよび独立security reviewのPASSから推測しない。
- 実装前の古いClaude Evidence Packageを第三者レビュー用に再利用しない。
- 外部APIを実行しない。
- Candidate物理schemaを推測で変更しない。
- P5のEvidence Package再生成前に第三者独立レビューへ戻らない。
- Gate P PASSをPH Minimum Beta正式完成またはmain統合済みと扱わない。
- 人間作業時間measurement logを作らず、E2E時間測定を開始しない。
- Phase 2へ自動直進しない。
- AI Shadowを開始しない。
- 外部API・実データを無承認使用しない。
- mandatory attributeを自動的にBeta MUSTへ昇格しない。
- SG / MY / THへ展開しない。
- 実データによるE2E測定を今回開始しない。
- 本実装と次の読み取り専用reviewでは、Shopee、Keepa、AIその他の外部APIを呼ばない。
- live Canopy APIを、mock test完了後の別途オーナー承認なしに呼ばない。
- Canopyを本番標準にせず、通常UIにprovider選択を追加せず、自動provider fallbackを実装しない。
- Rainforestを実装せず、Canopy結果をKeepa SQLite cacheへ書き込まず、`PRELISTING_CANDIDATE_V1`の15列schemaを変更しない。
- AI Shadowを今回開始しない。
- 新しいExcel、CSV、physical measurement schemaを作成または確定しない。
- structured REVIEW、ReviewCase、API auto-resolutionを実装しない。
- 承認済みのCategory Mapper一時認証入力範囲を越えてBrand resolution、Guardrail辞書、Gateロジック、Phase 1の13 Brand rulesを変更しない。Resolver／ExpansionをCanopy v0.1契約外へ拡張しない。
- Shipping / Operational Filter、Category Batch Builder、mandatory attribute Batchへ進まない。
- SG / MY / THへ展開せず、Marketplace-neutral schemaを先行確定しない。
- push、PR作成、merge、deployを行わない。
- 727候補を、設計・根拠の確認なしに正式COMMON_BLOCK、PH_BLOCK、REVIEW辞書として扱わない。
- 理由不足の一般コミュニティNG 311行を、今回のPHコミュニティ14項目の採用判断だけでBLOCKまたはREVIEWへ昇格しない。
- 台湾・タイ・マレーシア等の参考資料から具体辞書を作らず、PHルールへ混ぜず、共通項目へ昇格しない。
- 今回の正本化だけで、Category ID等を扱うデータ構造、判定単位、根拠種別の実装方式を確定しない。
- オーナー提供3資料の実物照合前に、COMMON_BLOCK、PH_BLOCK、REVIEWの具体項目を確定しない。
- 既存Guardrail辞書を正解として新辞書へ移植せず、比較・移行対象として扱う。
- 辞書CSV、商品コード、Gate判定ロジックは、別の実装範囲と承認が確定するまで変更しない。
- COMMON_BLOCKを市場別ルールで解除する仕組み、またはBLOCKからREVIEWへ降格する経路を設計しない。
- SG／MY／TH等の具体的辞書内容は、各市場の根拠資料と別の作業範囲が確定するまで作成しない。
- Category Mapper / AI Shadowは、オーナーの明示的な開始承認があるまで開始しない。
- 固定30件評価のオーナー受入だけでは、Category Mapper / AI Shadowの開始を承認した
  ものと扱わない。
- Resolverの成功基準が未決定のまま、大機能を追加しない。
- SG / MY / THの資料、規則、Category情報を今回のPH作業へ使用しない。
- 外部APIは、作業票またはCodex指示で許可されたAPI・目的・最大件数・再試行条件の
  範囲内だけ実行する。許可範囲が明記されていない場合は実行せず停止する。
- Shopee商品系書込APIと自動出品は、明示許可がない限り禁止する。
- 完全な30件一覧を証拠なしで補完しない。
- 回収TSVを歴史的初回exportの入力として扱わない。
- JPH→R対応を行順、タイトル類似、商品同一性判断で補完しない。
- source map等の一次証拠がない限り、歴史的JPH→R対応探索を再開しない。
- 新しい固定30件基準実行が完了するまで、既存の9件・21件区分を回収TSVへ接続して21件再評価バッチを作成しない。
- 外部AI、Keepa、実運用はオーナー明示許可前に開始しない。
- Evidence Manifestとsource mapを保存できない状態で実行しない。
- 回収TSVを歴史的初回exportへ接続しない。
- 外部AI、Keepa、実データ、新batchの再検索対象商品の再評価は別途明示許可前に実行しない。
- 検索精度改善や商品同一性ロジックを今回の証拠永続化改修へ混在させない。
- 証拠保存機能の完成だけでResolver成功を宣言しない。
- Excelだけを全成果物証拠台帳の正本にしない。
- 実画面受入前に改修完了扱いにしない。
- 新batchの再検索対象商品の再評価前に実行記録フォーマットを使用する。
- 初回検索、再検索、Resolver解析、Keepa確認、同一性判定を混在させない。
- 成功基準は新batchの再検索対象を含む工程別証拠がそろう前に決定しない。
- この正本更新だけでWorkflow実装を開始しない。
- 既存出品ツールの入力契約を推測で確定しない。
- PH端から端の受入前にSG／MY実装を開始しない。
- SG／MYの順序を証拠なしで固定しない。
- THを自動的に次市場としない。
- 外部AI、Keepa、実商品、固定30件実行は別決裁まで開始しない。
- 証拠保存機能の完成だけでResolver成功を宣言しない。
- Category Mapper AI Shadowはオーナー明示承認まで開始しない。
- 自動出品は明示承認なしに開始しない。
- 外部既存出品ツールの正式入力テンプレートまたは仕様書を確認する前に、接続設計ゲートへ進まない。
- listing-tool向けtextを外部出品ツールの正式入力契約として扱わない。
- 外部出品ツールの正式契約なしにWorkflow、自動接続、自動出品を開始しない。
- README記載修正とgate_schema_version検証修正を、外部契約証拠回収へ無断で混在させない。
- テスト未実行の監査結果を、実行テストPASSとして扱わない。
- 実商品、実在庫、実画面、実取込を確認前に端から端の業務成立を確定しない。
- 読み取り専用監査結果だけでWorkflow実装または自動接続を開始しない。
- 以前の外部契約証拠回収用Briefおよびそのcloseout Briefは失効済みとして再利用しない。
- 外部契約証拠回収を現在の最優先作業として再開しない。
- 出品支援ツール完成前に、出品後商品改善ツールまたはAmazon仕入れ支援ツールの本格設計・実装を開始しない。
- 出品支援ツールの完成条件を確定する前に、完成済みと扱わない。
- 三つのツール間のデータ連携、API連携、実行順序、共有状態管理を設計しない。
- 一つのツールの出力を、他のツールの正式入力として扱わない。
- 外部出品ツール契約未確認だけを理由に、ASIN、Shopee Category ID、Shopee Brand IDの取得・確認に関する中核開発全体を停止しない。
- 自動投入、自動出品、E2E受入には別設計・別承認を必要とする。
- 出品後商品改善ツールとAmazon仕入れ支援ツールの詳細仕様を今回確定しない。
- リポジトリ分割または共通ライブラリを今回決定しない。

## 成功判定の状態

- 評価完了とResolverの成功判定は別です。
- 成功基準は現時点で未決定です。
- 評価完了だけでResolverの成功や完成を宣言しません。
- 新batchの再検索対象を含む工程別証拠がそろうまで、成功基準は未確認のままです。

## 既知の文書不整合

- README / 実装間の既知不整合はない。GABA-freeについては、P1cオーナー確定境界と既存Rule V2 matcher実装との差分があり、別修正事項として未着手である。

## 情報の根拠・確認レベル

| 情報 | 根拠・確認レベル |
| --- | --- |
| 現在作業、次の単一作業、停止条件、Git外成果物索引 | この文書とオーナー決定で確認済み |
| テンプレートv0.1.1 finalの正本SHA | オーナー一次記録と読み取り専用監査で確認済み |
| 30件、9件の候補あり元商品、21件の候補なし元商品、13候補、判定区分、Keepa確認、PH Gate結果 | ユーザー確認済みかつオーナー受入済みの実運用結果。Git・テスト・CIでの再確認は未実施 |
| 候補なし21件の停止工程 | 過去成果物の証拠からは復元不能とする監査結果 |
| 回収TSVのファイル名、完全SHA、30件構成、producer chain | 読み取り専用監査で確認済み |
| 歴史的初回exportとの対応と正式実行入力としての同一性 | 未証明 |
| JPH→R行順仮説 | タイトル照合0/30 |
| 設計ゲートと必要性分類 | コード・テスト・3成果物の読み取り照合済み。`RESOLVER_CHANGE_REQUIRED` |
| 回収TSVの今後の正式基準入力としての採用 | 新規基準入力専用としてオーナー受入済み |
| Resolver証拠永続化改修、テスト、実画面 | branch技術検収、オーナー実画面確認、PR #7 main統合およびformal main確認済み |
| B2全体フローの実商品・実画面 | Resolver / Expansion各1追跡対象でCandidate生成からSafety、exact重複、Category、Brand / No Brand、`listing_ready`、CSV / TXT handoffまでオーナー確認済み。PH既出品CSVとPHショップはいずれも既出品0件。E2E技術確認であり最終Beta受入ではない |
| PH対応のコード上の事実 | Ingredient Safety既存検証に加え、Product Text Safety関連targeted pytest 592件、PH UI再確認44件、全pytest 899件でlocal technical validation済み。Product Text Safetyは独立read-only review PASS、Keepa JP production read-onlyの実商品2件で`CAPTURED` 2件、Candidate→sidecar→通常PH Gate成立を実物Evidenceで確認済み。2件超の取得率とhemp実商品live BLOCKは未確認だが、新しいBeta blockerにはしない。Keepa Ingredient Safetyのproduction / JP / read-only live技術確認は実商品2 ASIN・空のin-memory PH inventoryでPASS。B2 E2E全体フローの技術確認は完了したが、残る画像Safety・判断不能時の人間REVIEWというBeta MUSTがあるためGate PとPH Minimum BetaはHOLD。GABA-free matcher差分はP1c v1-r1受入で確認済みだが未修正 |
| 新batchで確定する再検索対象件数・source_id、再評価の実行日・担当者・使用外部AI、Resolver成功基準、改善対象と改善方法 | 未確認 |

## 最終更新日

2026-09-02
