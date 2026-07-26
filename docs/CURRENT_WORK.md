# CURRENT WORK

この文書は、現在実行中の作業、再開地点、停止条件の正本です。コードと正式履歴は
Git、重要判断の理由は `docs/DECISION_LOG.md`、長期工程は
`docs/PROJECT_ROADMAP.md` を確認してください。

## 更新ルール

- 実作業の事実、進捗、次の単一作業、停止条件が変わった場合だけ更新する。
- 重要な方針変更は、この文書に理由を重複記載せず `DECISION_LOG.md` に追記する。
- 商品名、CSV本文、秘密情報、長大な日次ログは記録しない。

## 正式版と関連ブランチ

- 正式版の基準: `main` / `origin/main` の
  `052dab573eb617ae78e4035024518a8ff5905f8d`
- 関連するAI実験ブランチ:
  `feature/ph-category-mapper-ai-shadow-v0.2.1`
- AI実験ブランチの確認済みHEAD:
  `69a1d22c7ff4212d82ca088d09a66b8f4a465e58`
- 上記のGit refは2026-07-26に確認した情報であり、実作業の進捗そのものではない。

## 現在実行中の作業

- current_work_type: `management-foundation`
- current_phase: 管理基盤Ver1 第1・第2段階の実装完了、統合検収・受入・正式化前
- working_branch: `chore/management-foundation-v1`
- next_management_action: 第1・第2段階の差分と安全性の統合検収
- commit / push: 未実施

現在実行中なのは管理基盤Ver1の整備です。PH固定30件評価は、管理基盤Ver1の
受入・正式化が完了するまで一時停止中であり、現在の実行対象ではありません。

## 管理基盤Ver1整備中の作業範囲

- 管理文書と引継ぎ方法だけを整備する。
- 機能コード、固定30件評価、外部API、Category Mapper / AI Shadowの実行・評価・
  仕様変更は行わない。
- CONTEXT_SNAPSHOTは生成スクリプトで再生成する派生物であり、手動編集・commitはしない。

## 一時停止中の実作業

- marketplace: `PH`
- module: `ASIN Resolver`
- phase: 固定30件評価
- 固定評価コホート: 元Shopee商品30件
- Amazon候補を取得できた元Shopee商品: 9件
- Amazon候補: 13件
- Keepa確認: 13候補すべて確認済み
- PH Prelisting Gate: 13候補すべて `ELIGIBLE`

上記はユーザー確認済みの実運用結果として現在地点に採用します。Git、
テストレポート、CI成果物で再確認された事実ではなく、コード機能の対応市場を
証明する情報としても扱いません。

## 未完了事項

- 13件のAmazon候補を、対応する9件の元Shopee商品と照合する同一性監査
- 固定30件全体の候補取得状況と判定区分の集計
- 集計結果の記録

## 管理基盤Ver1完了後の次の単一作業

管理基盤Ver1の受入・正式化完了後、13件のAmazon候補を、対応する9件の
元Shopee商品と照合する同一性監査を行います。各候補は次の4区分のいずれかに
分類します。

| 区分 | 意味 |
|---|---|
| `MATCH` | 同一商品・同一仕様 |
| `VARIANT_MATCH` | 同一シリーズだが、色・容量・数量・サイズなどが異なる |
| `UNCERTAIN` | 情報不足 |
| `MISMATCH` | 別商品 |

完全一致は `MATCH` だけで数えます。`VARIANT_MATCH` は別集計とし、完全一致率に
含めません。候補なしは、固定30件のうちAmazon候補を取得できなかった元Shopee商品
として別集計します。

## 停止条件

- 同一性監査が未完了の候補を、Category Mapper / AI Shadowへ渡さない。
- 固定30件評価の結果が記録されるまで、大機能を追加しない。
- SG / MY / THの資料、規則、Category情報を今回のPH作業へ使用しない。
- 外部APIは、作業票またはCodex指示で許可されたAPI・目的・最大件数・再試行条件の
  範囲内だけ実行する。許可範囲が明記されていない場合は実行せず停止する。
- Shopee商品系書込APIと自動出品は、明示許可がない限り禁止する。
- 固定30件評価の完了、集計結果のユーザー確認、ユーザーの明示承認がそろうまで、
  Category Mapper / AI Shadowへ進まない。

## 評価完了条件

固定30件評価は、次のすべてが完了したときに完了とします。

1. 現在取得済みの13候補を4区分のいずれかに分類する。
2. 固定30件全体について候補取得状況を集計する。
3. `MATCH`、`VARIANT_MATCH`、`UNCERTAIN`、`MISMATCH`、候補なしを別々に集計する。
4. 集計結果を管理文書または評価成果物に記録する。

## 成功判定の状態

- 評価完了とResolverの成功判定は別です。
- 成功基準は現時点で未決定です。
- 評価完了だけでResolverの成功や完成を宣言しません。
- 最後に成功したテスト結果は、根拠となるコミット済みレポートまたはCI成果物を
  確認できていないため、未確認です。

## 既知の文書不整合

- `README.md` にはPrelisting Gateが「現在SGのみ対応」と記載されています。
- 一方、この文書にはユーザー確認済み結果として「PH Prelisting Gateで13候補すべて
  `ELIGIBLE`」を記録しています。
- 管理基盤Ver1では、この不整合の原因調査、README修正、PH対応のコード上の確認を
  行いません。PH対応のコード上の事実は未確認です。

## 情報の根拠・確認レベル

| 情報 | 根拠・確認レベル |
|---|---|
| 正式版・関連ブランチのref | Gitで確認済み |
| 現在の管理基盤作業・working branch | Gitとこの作業票で確認済み |
| 30件、9元商品、13候補、Keepa確認、PH Gate結果 | ユーザー確認済みの実運用結果。Git・テスト・CIでの再確認は未実施 |
| PH対応のコード上の事実 | 未確認 |
| 最後に成功したテスト結果 | 未確認。コミット済みレポートまたはCI成果物を確認できていない |

<!-- CONTEXT_SNAPSHOT:START -->
## 引継ぎ要約

- 現在実行中: 管理基盤Ver1
- 第1・第2段階: 実装完了、統合検収・受入・正式化前
- 次の管理作業: 第1・第2段階の差分と安全性の統合検収
- 一時停止中の実作業: PH ASIN Resolver固定30件評価
- 元Shopee商品9件に対してAmazon候補13件。13候補はKeepa確認済みで、PH Prelisting
  Gateは13候補すべて `ELIGIBLE`。
- 次の実作業: 9件の元Shopee商品と13件のAmazon候補の同一性監査
  （`MATCH` / `VARIANT_MATCH` / `UNCERTAIN` / `MISMATCH`）。
- `VARIANT_MATCH` は完全一致率に含めない。Category Mapper / AI Shadowへはまだ進まない。
- SG / MY / THは今回のPH作業の対象外。
<!-- CONTEXT_SNAPSHOT:END -->

## 最終更新日

2026-07-26
