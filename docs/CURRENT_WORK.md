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

- current_work_type: `出品支援ツール完成定義・設計ゲート`
- current_phase: `リサーチツール整合監査完了・出品支援ツール完成定義案作成準備`
- working_branch: `再開時にGit状態を確認して確定`
- marketplace: `PH`
- module: `事業ポートフォリオ・出品支援ツール`
- next_action: Codexが、監査結果を基に、出品支援ツールの完成定義、利用者シナリオ、受入条件、残課題、対象外の推奨案を作成する。

三つの独立ツール構成と出品支援ツール優先順位はmain上で受入済みです。開発運用は軽量開発運用v1へ移行し、GPTを必須の伝言役または承認者にしません。リサーチツール定義、現行正本、実装、テストソース、PH Guardrail辞書の読み取り専用整合監査は完了しました。現在は、出品支援ツールの完成定義、残課題、利用者シナリオ、受入条件を整理する設計ゲートの途中です。次はCodexが監査結果を基に推奨案を作成します。完成定義、受入条件、現行実装との差分は未確定であり、出品支援ツールを完成済みとは扱いません。

## 完了・受入済み

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

実物が必要な場合は、必要時だけ軽量WORK_BRIEFでstorage aliasを解決するか、オーナーが現在のCodexタスクへ再添付する。

## 未完了事項

- 出品支援ツールの完成定義
- 出品支援ツールの残課題一覧
- 出品支援ツールの利用者シナリオ
- 出品支援ツールの受入条件
- PH Guardrailテスト用基準辞書v1
- 完成定義と現行実装の差分監査
- ASIN到達性能の評価
- Expansion・Resolverの実商品テスト
- Shopee Category ID・Shopee Brand ID確認工程の受入
- オーナーによるPHでの実画面・実業務受入
- 出品後商品改善ツールの将来優先順位判断
- Amazon仕入れ支援ツールの将来優先順位判断
- 外部既存出品ツールの正式入力テンプレートまたは仕様書の読み取り専用証拠回収（自動投入またはE2E接続を検討する場合）
- 外部出品ツールの正式ヘッダー順序、エンコーディング、必須値、カテゴリ・ブランド・属性、バリエーション・SKU・在庫契約の確認（同上）
- Gate eligible CSVのgate_schema_version再検証設計・修正要否の判断
- 出品支援ツール内部工程の接続設計ゲート（必要な場合）
- 外部AI・Keepa・実データ実行の別決裁
- 新規固定30件基準実行
- Resolver成功基準と続行・保留・打ち切り判断
- SG／MY市場展開設計
- TH優先順位判断

## 次の単一作業

Codexが、監査結果を基に、出品支援ツールの完成定義、利用者シナリオ、受入条件、残課題、対象外の推奨案を作成する。

## 停止条件

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
- READMEのPrelisting Gate対応市場記載の修正要否を判断するまで、READMEをPH対応の正本として扱わない。
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

- `README.md` にはPrelisting Gateが「現在SGのみ対応」と記載されています。
- 一方、読み取り専用監査では、実装、PH Guardrail辞書、PH v2 fixture、テストソースにより
  SG／PH対応を確認しました。テストは実行していません。
- README修正は未承認であり、修正要否は後続判断とします。

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
| 実データ | 未確認 |
| PH対応のコード上の事実 | 読み取り専用監査で実装、PH Guardrail辞書、PH v2 fixture、テストソースを確認。テストは未実行 |
| 新batchで確定する再検索対象件数・source_id、再評価の実行日・担当者・使用外部AI、Resolver成功基準、改善対象と改善方法 | 未確認 |

## 最終更新日

2026-08-02
