# PH・SG共通 実務Beta完成条件と差分監査

## 目的・正本・完成の意味

DEC-0137に基づき、PH・SGの事業へ投入する共通システムの初版を定義する。
完成後は原則としてMY・TW・TH等の国追加と軽微な不具合修正へ移る。
主要機能や共通の日常操作をBeta後に作り足す前提を置かない。
PH基準の保護とSG Minimum Beta Step 8の受入履歴は維持するが、それだけで本Beta完成とはしない。
DEC-0116の固定PH基準は既存機能の回帰基準として残し、今後の完成判断は本書を用いる。

監査基準は`aac8548657c1f028368a7e98c8ac44d426821c1b`（Home Appliances CLI採用後のmain）。
これは監査時点の固定参照であり、現在HEADや稼働releaseの宣言ではない。
同CLIは独立維持し、再監査・再実装・通常フローへの組込みを本計画へ含めない。
最新の実装状態は各後続変更のGit・tests・Evidenceで確認し、本表を無条件に完成へ繰り上げない。

実商品受入は[PH・SG受入計画](PH_SG_BETA_ACCEPTANCE_PLAN.md)、Beta前MUSTの追加条件は
[価格帯・平均レビュー評価](CANDIDATE_PRICE_RATING_FILTERS.md)を参照する。
本書は設計であり、実装、実API、環境設置、出費、release切替、実出品の承認ではない。

## 固定する完成条件

以下C01〜C12は全てMUST。PHとSGの両方で成立し、C12の実務受入まで確認して完成とする。
見出しの一致、SGだけの実装、offline試験成功を両市場の完成に読み替えない。

| ID | 完成条件 | 人間に残す作業・限界 |
|---|---|---|
| C01 | 同じ統一アプリの市場選択から、候補取得→確認→準備→出品状態管理へ進む | 市場・ショップを確認する |
| C02 | Expansion／Resolver双方から商品候補を得て、出所を保ちSafetyへ渡せる | Resolverの外部AIへの送信・結果選択、商品同一性の疑義確認 |
| C03 | Safety、全ショップ重複、確認待ちを共通操作で処理する。BLOCK／REVIEW／EXCLUDEを一括操作で解除しない | 判断不能・本体／同梱・対象の武器画像疑義等を確認する |
| C04 | Category／Brandの検索、候補、限定条件での自動確定、人間確認、保存、再確認が一貫する | 未知・曖昧・根拠不足は保留。No Brandへの無断fallback禁止 |
| C05 | グループを確認し、任意の商品部分集合と必要な商品単位確認を同じ操作で扱う | グループ名一致だけで未確認商品へ判断を拡張しない |
| C06 | 準備完了商品を商品群をまたいで蓄積し、現在条件で再検証してCategory／Brand単位にCSV／TXT出力する | Seller Center必須属性・発送条件・販売可否の最終確認 |
| C07 | Safety／Category／Brand確認待ちと、出品待ち・出品確認待ち・出品済み・出品エラー・再確認必要を継続管理する | 外部ツールへの投入結果、最新の全ショップ出品資料を確認する |
| C08 | 再起動・追加商品群・資料変更でも履歴を保存し、適切な単位で確認を維持／失効する | 古い資料を最新として再申告しない。復旧時の不明結果を解決する |
| C09 | 通常画面の手順・項目・ボタン・状態表示がPH／SG共通である | 国別に必要な確認内容の差は明示する |
| C10 | 開発・診断・重複UIを日常操作から整理し、停止理由と復旧操作を残す | 管理設定は必要時に管理画面で行う |
| C11 | Category ID／Brand ID、Safety、SLS、公式catalog、認証・保存先を市場／ショップに正しく結合する | 他市場の確認記録やIDを流用しない |
| C12 | 両市場で少量の実商品を反復処理し、保存・再起動・追加・失効・出力・作業状態が成立する | 操作者とOwnerが実務上の成立を受け入れる |

全面自動出品、外部出品ツールの自動操作、全商品の安全保証、未知商品の完全自動分類は対象外。
全商品に追加画像確認を復活させず、DEC-0125の対象・疑義別確認を守る。
DEC-0138により、C01〜C12に加えてF1（Amazon本体価格帯）・F2（平均レビュー評価）をBeta前MUSTとする。

## 差分監査

「完成済み」は限定した機能の対応が揃う意味。「部分実装」は市場・入口・保存等に不足がある意味。
「未検証」はコードの存在とは別の軸であり、実API／実商品／実務受入の証拠がない箇所に併記する。
以下の参照は監査基準commitの関数／testを指す。受入番号Aは受入計画のシナリオ。

| 条件・正本仕様 | 対応コード・tests | PHの状態 | SGの状態 | 総合判定・事業影響 | Beta前の最小対応・受入 |
|---|---|---|---|---|---|
| C01：本書、DEC-0128、BETA_APPLICATION | `app_beta.py:render_beta`、`app.py:render_application`／`test_beta_application.py` | 共通入口・4タブあり | 同じ入口。長期作業画面はoptional入口へ分岐 | 入口は完成済み、全操作は部分実装。別画面へ移ると日常手順が分断 | 必須：長期作業を共通通常入口へ接続。A01/A03 |
| C02：DEC-0019/0021/0132、EXPANSION_GATE_HANDOFF | `keepa_client.py:find_related_products,verify_products_by_asin`、`asin_resolver.py:verify_selected_rows`、`prelisting_candidate_csv.py`／`test_keepa_client.py`、`test_asin_resolver.py`、`test_expansion_gate_handoff.py` | 両取得・15列Candidate、Expansion内部搬送あり | 同じ取得、SG予算開始が先に必要 | 部分実装／共通手順の実務未検証。Resolver手動経路は存在し自動接続はMUSTでない | 必須：開始操作・資料搬送の共通案内、両入力の保存結合。A01/A02 |
| C03：DEC-0125/0129/0130/0133、本書 | `app.py` Gate、`prelisting_gate.py`、`category_mapper_sg_preparation.py:assess_sg_preparation`、`sg_beta_workbench.py:assess`／`test_prelisting_gate.py`、`test_guardrails.py`、`test_sg_initial_beta.py` | Gate／画像／Batteryは既存、後段はPH固有 | SG本体確認・strict準備再検証、offline確認待ちあり | 部分実装。旧Gate通過を永続的な出力許可にすると事故につながる | 必須：両市場の出力直前に同じ有効性契約で既存validatorを呼ぶ。A02/A04/A05 |
| C04：DEC-0116/0121/0135、本書 | `category_mapper.py:_recommend_category`、`category_mapper_ui.py:_render_category_search,_render_brand_controls`、`category_mapper_sg_ui.py`、`sg_beta_workbench.py:auto_category,auto_brand`／`test_category_mapper.py`、`test_category_mapper_sg_brand.py`、`test_sg_initial_beta.py` | 検索・候補・mapping保存あり。旧Category／Brand policy再利用は新AUTO_RULE契約と異なる | strict Brand・人間確認あり。限定AUTO_RULEはSG offlineのみ、公式有効性は未受入 | 部分実装／実務未検証。誤確定・過剰な再確認の両リスク | 必須：対象自身のJP Fact、rule/alias版、公式Brandの更新条件、項目別authorityを共通化。A03/A04 |
| C05：DEC-0135、本書 | `category_mapper_ui.py` group controls、`category_mapper_sg_ui.py:_render_group_confirmation`、`sg_beta_workbench.py:confirm`／上記Mapper tests、`test_sg_initial_beta.py` | Keepa Categoryグループの確認。耐久保存付き任意部分集合の同等操作なし | 通常グループ全件／商品確認、offlineで任意部分集合をtransaction保存 | 部分実装。不要な一括確定や二重作業 | 必須：共通選択表・部分集合・全件rollback・古い選択停止。A03 |
| C06：DEC-0126/0134/0135、本書 | `category_mapper.py` export、`category_mapper_sg_preparation.py:build_sg_beta_preparation_files`、`sg_beta_workbench.py` outputs／Mapper・SG preparation・initial beta tests | Category／Brand別出力あり、耐久準備poolなし | 通常のready subset出力あり、商品群横断poolはofflineのみ | 部分実装。追加群や再起動で作業が分断 | 必須：市場別poolから現在のready subsetを共通formatterへ渡す。A03/A05 |
| C07：DEC-0135、本書 | `sg_beta_work_store.py` products/events/copy_locks、`sg_beta_workbench.py:finish_copy,listing_action,queue_csv`／`test_sg_initial_beta.py` | 5状態の長期作業管理は未実装 | SG offlineで5状態と結果不明lock、通常SGには未接続 | 部分実装。重複投入・結果不明・出品済み誤認 | 必須：PH対応の市場別保存と通常入口接続。出力／投入／出品済みを区別。A05 |
| C08：DEC-0132/0134/0135、本書 | `category_mapper_store.py`、`sg_continuous_runtime.py`、`sg_beta_work_store.py`／`test_sg_continuous_operation.py`、`test_expansion_gate_handoff.py`、`test_sg_initial_beta.py` | mapping保存とsession失効。長期商品履歴なし | API枠保存、通常batch変更で確認失効。作業DBはofflineのみ | 部分実装。保存済み＝現在有効とは限らない | 必須：履歴と現在有効性を分け、商品・資料・catalog・rule変更で対象判断を失効。A04/A05 |
| C09：本書、BETA_APPLICATION | `app.py` routing、PH/SG Mapper UI、`app_sg_candidate.py:render_sg_continuous`／`test_beta_application.py` | Token入力・PH固有group／Brand | SG開始・資料読込・個別確認、別offline作業UI | 部分実装。見出しは共通でも通常操作は異なる | 必須：下記共通操作表で同じシナリオを通す。A01〜A05＋画面比較 |
| C10：DEC-0022/0023、本書 | PH/SG Mapper UI、`app.py` Resolver tabs、`sg_beta_workbench_ui.py`／UI tests | Token常設、旧版名、診断・補助タブあり | 開発検証表記、詳細予算、重複した画像確認導線 | 部分実装。利用者が設定と作業を混同 | 必須：下記分類どおり整理、停止・復旧を隠さない。A01/A06 |
| C11：DEC-0128/0135、本書 | `beta_runtime_paths.py`、`category_mapper_store.py`、SG runtime/store／`test_beta_application.py`、`test_sg_initial_beta.py`、`test_sls_category_protected.py` | 既存PH保存／認証を保護 | strict SG保存／shop結合、offline DBはSG固定 | 部分実装。共通化で他市場ID・記録が混ざる危険 | 必須：共有するのは手順・検証契約。ID・catalog・rule・credential・DBを市場adapterで分離。A04/A06 |
| C12：SG_CONTINUOUS_OPERATION、PH_SG_BETA_ACCEPTANCE_PLAN | 上記コード・offline testsは準備証拠 | 旧PH受入あり、新しい共通操作の受入なし | Step8の旧受入あり、通常2商品群と新共通操作の受入なし | 未検証。日常運用成立を断定不可 | 必須：別承認後に両市場の少量反復受入。A01〜A07 |

## 画面監査と整理対象

実画面確認は外部通信を禁止した隔離ローカル起動で行った。
PH／SGの国選択と4タブ、PH MapperのACCESS_TOKEN常設とCSV入力を確認。
設定未注入のSG Mapperは「SGの利用設定を接続してください」で停止した。
認証済み通常SGの全操作は実画面未検証。以下のSG詳細はコード・mock AppTestによる確認である。
実API・実商品・production保存先・稼働releaseには接続していない。

| 分類 | PH現状／SG現状 | 変更対象と受入条件 |
|---|---|---|
| 通常必須 | 両国の候補取得、全ショップCSV、Gate停止理由、Category検索・候補、Brand、出力 | 共通の「作業開始→候補→確認待ち→準備済み→出品状態」。同じ選択・確認・取消・保存・出力ボタンと日本語状態名を使う |
| 国別必須 | PH SLS・catalog／SG SLS・本体除外・strict Brand等 | 共通画面内に市場名・shop・国別理由を表示。国別の追加必須属性・発送条件は差分として明示 |
| 管理設定 | PH Token常設／SG policy接続・catalog設定・API枠 | 認証、保存先、catalog更新、予算設定は管理画面へ。通常画面には接続状況・残枠警告・復旧入口を残す |
| 開発・診断 | Product Finder診断、Resolver Evidence Batch、Shadow比較／SG開発検証資料・mock JSON・生履歴payload | 通常は非表示。管理／診断入口で明示利用。Safety判定に必要な商品資料の入力は通常側へ残す |
| 重複・不要 | 旧版名・内部schema説明／画像一括・個別操作の重複説明、API内部詳細の常時表示 | 同じ操作を二重表示せず、対象・未実施・疑義・停止理由が見える一つの一覧へ。個別復旧は残す |
| 保護対象 | 「保留」の意味や保存状態が画面ごとに異なる | 保留は永続的な確認待ちとして実際に作用する。PHの現`st.button("保留")`は保存操作に接続されていないため表示だけを完成扱いしない |

受入では同一シナリオのPH／SG画面を並べ、操作順、必須入力、ボタン、状態・件数を比較する。
市場切替で一時選択を破棄しても、各市場の保存履歴と予算を失わないことを確認する。
SLS停止、認証切れ、catalog取得失敗、結果不明lockの解決手段は通常画面から到達できること。
UIの一括作り直しはせず、既存の検証・出力部品を接続する範囲に限定する。

## 最小実装順序

以下は後続実装の作業単位。概算は1人による実装・offline回帰の目安で、外部待ちや実務受入を含まない。
根拠は既存SG部品の再利用量とPH adapter／通常接続の不足であり、納期確約ではない。

| 順 | 最小作業・依存 | 終了条件 | 概算・優先理由 |
|---|---|---|---|
| P1 | 共通の準備有効性契約と市場adapter。既存validatorを使用し、対象自身のFact・市場/shop・catalog/rule版・全ショップ重複との結合を揃える | PH／SGの古い・別市場・欠損資料から出力不可。既存BLOCK等を弱めない。正式Brandの完全性と更新契約を明示 | 2〜4人日。誤出力防止を先行。新規汎用Fact基盤は作らない |
| P2 | P1→既存SG作業storeをPHにも適用できる境界へ分離。市場別の新規保存先・履歴・準備pool・5状態 | 再起動、A→B追加、取消、結果不明・二重操作・保存失敗が両国で安全。既存DBの無断移行なし | 3〜5人日。日常継続作業の不足を解消 |
| P3 | P1/P2→Category／Brand検索・候補・限定AUTO_RULE・人間採用・任意部分集合を通常経路へ接続 | 既存の限定ruleだけ、適用根拠・authority可視化。対象外は保留。公式資料更新で再確認 | 2〜4人日。全商品自動分類やrule大量追加を避ける |
| P4 | P2/P3→共通通常画面、管理設定分離、診断整理、共通CSV／TXT出力・状態操作 | 上記画面比較とA01〜A06のoffline再生が両国で一致 | 2〜4人日。見出しだけの統一を終える |
| F | 価格・評価の取得後フィルター（DEC-0138のBeta前MUST）。P1のFact契約と候補CSV互換を利用 | 別紙F01〜F08。P1〜P4を優先し、F1/F2完成後にP5へ進む | 両機能合計2〜4人日目安。Finder最適化は別1〜2人日でBeta後推奨 |
| P5 | P1〜P4とF1/F2完成→両市場の少量実商品・実画面受入 | A01〜A07の証拠とOwner実務受入。実API／設置／費用等は事前の別承認 | 実施1〜2日目安＋承認・失敗修正待ち。offline成功で代替しない |

P1の共通契約・PH／SG offline出力回帰は[実装契約](PREPARATION_VALIDITY_P1.md)を参照する（DEC-0139）。
P2の両市場offline backendは[長期保存・作業状態契約](PERSISTENCE_P2.md)を参照する（DEC-0140）。
P3の[共通分類操作・現在根拠搬送](CLASSIFICATION_P3.md)は両市場の最小通常接続をoffline検証する（DEC-0141）。
P4の[共通日常操作](PRACTICAL_UI_P4.md)は、明示した新規保存先で通常操作・管理／診断分離・
共通CSV／TXT・pool・5状態・予約復旧をoffline接続する（DEC-0142）。次の単一作業はF1/F2。
上の差分表は監査時点の状態を保持し、P4のoffline成功を実API・実商品受入へ繰り上げない。
P1の公式Brand有効性は「開始時の公式完全取得＋明示更新／変更・取得失敗時の失効」を最小案とする。
固定24時間TTLや永続的な最新保証を導入せず、長時間作業・再起動時の再取得条件と費用を実務受入前に確定する。
条件付き自動確定の運用はその根拠が揃うまで閉じ、人間確認を用いる。人間確認経路だけでC04全体の完成とはしない。

Beta後は、Finderでの先行フィルター最適化、精度の網羅的改善、追加rule、診断の装飾、Research CSVの他市場対応等の微改善候補に限定する。
MY／TW／TH追加は共通Beta受入後の国別工程。新市場のSafety・SLS・catalog・税務確認は省略しない。
主要な保存・5状態・共通UI・限定自動確定をBeta後へ送って完成と宣言しない。
