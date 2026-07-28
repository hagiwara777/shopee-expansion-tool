# PROJECT ROADMAP

## 当面の全体目標

PHにおいて、ASIN候補取得から同一性確認までの工程を証拠付きで評価し、改善投資と
継続・保留・打ち切りを判断できる状態にする。Resolver、Gate、Mapperの責務は分離し、
自動出品は明示承認なしに行わない。

## 正式完成済み

- PH Category Mapper Ver0.1
- Shopee Research CSV Import Adapter Ver0.1
- ASIN Resolverの不正URL耐性修正
- PH固定30件評価とオーナー受入

## 実験中・未承認

- PH Category Mapper AI Shadow Ver0.2.1
- branch: `feature/ph-category-mapper-ai-shadow-v0.2.1`
- 実行開始はオーナー明示承認まで保留

## 現在から先の工程

1. 固定30件の完全な元入力を回収する。
2. 受入済み実行記録フォーマットで再評価バッチを準備する。
3. 候補なし21件を再評価する。
4. 初回検索、再検索、Resolver解析、Keepa、同一性判定を工程別に集計する。
5. 停止原因ごとに改善可能性を整理する。
6. 改善案と投資量を比較する。
7. 事業上の成功基準を決定する。
8. 継続・保留・打ち切りを判断する。
9. オーナー明示承認後にだけCategory Mapper / AI Shadowへ進む。

## 保留

- AI候補の1クリック採用 Ver0.3
- wrong category蓄積 Ver0.4
- Workflow層
- SG / MY / TH展開
- Category自動確定
- 自動出品

## 判断方針

- 21件の工程別証拠がそろうまでResolverの成功基準を決定しない。
- Resolver、Gate、Mapperの責務を広げすぎない。
- 工程間連携は将来のWorkflow層へ分離する。
- Category Mapper / AI Shadowと自動出品は、明示承認なしに開始しない。
