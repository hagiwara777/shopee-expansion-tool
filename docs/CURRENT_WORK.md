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
- current_phase: `Handoff Contract v1適用済み・固定30件元入力未発見・回収可能性監査前`
- working_branch: `再開時にGit状態を確認して確定`
- next_action: 固定30件の完全な元入力について、追加の限定探索と後続証跡からの損失なし再構築可否を分けて、読み取り専用で回収可能性を監査する。

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

実物が必要な場合は、非コミットBriefでstorage aliasを解決するか、ChatGPTへ再添付する。

## 未完了事項

- 固定30件元入力の実物回収または回収不能判定
- 固定30件証跡パッケージ監査
- 21件再評価バッチ準備
- 21件再評価
- 工程別停止原因集計
- 改善方法選定
- Resolver成功基準決定
- Category Mapper / AI Shadow開始判断

## 次の単一作業

固定30件の完全な元入力について、追加の限定探索と後続証跡からの損失なし再構築可否を分けて、読み取り専用で回収可能性を監査する。

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
- 元入力の実物と完全SHAを確認できない限り、再構築データを元入力実物と同一視せず、21件再評価バッチを作成しない。
- 21件再評価前に実行記録フォーマットを使用する。
- 初回検索、再検索、Resolver解析、Keepa確認、同一性判定を混在させない。
- 成功基準は21件の工程別証拠がそろう前に決定しない。
- Handoff Contractの同期ゲート不一致時は作業しない。

## 成功判定の状態

- 評価完了とResolverの成功判定は別です。
- 成功基準は現時点で未決定です。
- 評価完了だけでResolverの成功や完成を宣言しません。
- 21件の工程別証拠がそろうまで、成功基準は未確認のままです。

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
| 固定30件の完全な元入力 | 限定探索で未発見。存在しないことや回収不能までは未確認 |
| PH対応のコード上の事実 | 未確認 |
| 固定30件の完全な元入力、21件のsource_id・元商品名、再評価の実行日・担当者・使用外部AI、Resolver成功基準、改善対象と改善方法 | 未確認 |

## 最終更新日

2026-07-29
