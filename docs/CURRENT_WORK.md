# CURRENT WORK

この文書は、現在実行中の作業、再開地点、停止条件の正本です。コードと正式履歴は
Git、重要判断の理由は `docs/DECISION_LOG.md`、長期工程は
`docs/PROJECT_ROADMAP.md` を確認してください。

## 更新ルール

- 実作業の事実、進捗、次の単一作業、停止条件が変わった場合だけ更新する。
- 重要な方針変更は、この文書に理由を重複記載せず `DECISION_LOG.md` に追記する。
- 商品名、CSV本文、秘密情報、長大な日次ログは記録しない。
- Git外成果物は、Handoff Contractで定めた最小索引だけを記録する。

## 現在作業

- current_work_type: `PH ASIN Resolver固定30件・再評価準備`
- current_phase: `再現可能固定30件基準実行設計承認済み・Resolver証拠永続化実装前`
- working_branch: `再開時にGit状態を確認して確定`
- next_action: 承認済み設計に基づき、JPH→R source map、Evidence Manifest、成果物SHA、batch中断・再開情報を永続化するResolver改修と、実行記録テンプレートの最小補強を実装・検証する。

PH固定30件評価は完了し、集計結果はオーナー受入済みです。評価完了は、Resolverの
成功または完成の宣言ではありません。Handoff Contract v1の同期ゲートが一致した場合だけ、
次の作業を開始します。

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

実物が必要な場合は、非コミットBriefでstorage aliasを解決するか、ChatGPTへ再添付する。

## 未完了事項

- Resolver証拠永続化改修
- Evidence Manifest schema・生成・検証
- source mapの30/30保存
- batch中断・再開契約
- テンプレートとGuideの最小補強
- 実装後の単体・結合テスト
- オーナーによる実画面受入
- 外部AI・Keepa・実データ実行の別途決裁
- 新規固定30件基準実行
- 新batchで再検索対象となった商品の再評価バッチ準備以降の未完了工程

## 次の単一作業

承認済み設計に基づき、JPH→R source map、Evidence Manifest、成果物SHA、batch中断・再開情報を永続化するResolver改修と、実行記録テンプレートの最小補強を実装・検証する。

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
- Resolver改修とテスト完了前に新規固定30件を実行しない。
- Evidence Manifestとsource mapを保存できない状態で実行しない。
- 回収TSVを歴史的初回exportへ接続しない。
- 外部AI、Keepa、実データ、新batchの再検索対象商品の再評価は別途明示許可前に実行しない。
- 検索精度改善や商品同一性ロジックを今回の証拠永続化改修へ混在させない。
- Excelだけを全成果物証拠台帳の正本にしない。
- 実画面受入前に改修完了扱いにしない。
- 新batchの再検索対象商品の再評価前に実行記録フォーマットを使用する。
- 初回検索、再検索、Resolver解析、Keepa確認、同一性判定を混在させない。
- 成功基準は新batchの再検索対象を含む工程別証拠がそろう前に決定しない。
- Handoff Contractの同期ゲート不一致時は作業しない。

## 成功判定の状態

- 評価完了とResolverの成功判定は別です。
- 成功基準は現時点で未決定です。
- 評価完了だけでResolverの成功や完成を宣言しません。
- 新batchの再検索対象を含む工程別証拠がそろうまで、成功基準は未確認のままです。

## 既知の文書不整合

- `README.md` にはPrelisting Gateが「現在SGのみ対応」と記載されています。
- 一方、この文書にはユーザー確認済み結果として「PH Prelisting Gateで13候補すべて
  `ELIGIBLE`」を記録しています。
- 今回のPH評価では、この不整合の原因調査、README修正、PH対応のコード上の確認を
  行いません。PH対応のコード上の事実は未確認です。

## 情報の根拠・確認レベル

| 情報 | 根拠・確認レベル |
| --- | --- |
| 現在作業、次の単一作業、停止条件、Git外成果物索引 | この文書とオーナー承認済みBriefで確認済み |
| テンプレートv0.1.1 finalの正本SHA | オーナー一次記録と読み取り専用監査で確認済み |
| 30件、9件の候補あり元商品、21件の候補なし元商品、13候補、判定区分、Keepa確認、PH Gate結果 | ユーザー確認済みかつオーナー受入済みの実運用結果。Git・テスト・CIでの再確認は未実施 |
| 候補なし21件の停止工程 | 過去成果物の証拠からは復元不能とする監査結果 |
| 回収TSVのファイル名、完全SHA、30件構成、producer chain | 読み取り専用監査で確認済み |
| 歴史的初回exportとの対応と正式実行入力としての同一性 | 未証明 |
| JPH→R行順仮説 | タイトル照合0/30 |
| 設計ゲートと必要性分類 | コード・テスト・3成果物の読み取り照合済み。`RESOLVER_CHANGE_REQUIRED` |
| 回収TSVの今後の正式基準入力としての採用 | 新規基準入力専用としてオーナー受入済み |
| Resolver改修、テスト、実画面、実データ | 未確認 |
| PH対応のコード上の事実 | 未確認 |
| 新batchで確定する再検索対象件数・source_id、再評価の実行日・担当者・使用外部AI、Resolver成功基準、改善対象と改善方法 | 未確認 |

## 最終更新日

2026-07-29
