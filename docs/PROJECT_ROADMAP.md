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

1. 新規固定30件基準入力と設計判断を正式化する。
2. Resolverへsource map、Evidence Manifest、SHA、batch再開情報を実装する。
3. 実行記録テンプレートとGuideを最小補強する。
4. 単体・結合テストと、外部APIを使わないローカル検証を行う。
5. オーナーが実画面を確認する。
6. 外部AI・Keepa・実データ実行を別途決裁する。
7. 承認後、新しい固定30件基準実行を行う。
8. 新batchの結果から再検索対象を確定し、その対象の再評価バッチを準備・実行する。
9. 工程別停止原因を集計し、改善案と投資量を比較する。
10. Resolver成功基準と続行・保留・打ち切りを決定する。
11. オーナー明示承認後にだけCategory Mapper / AI Shadowへ進む。

## 保留

- AI候補の1クリック採用 Ver0.3
- wrong category蓄積 Ver0.4
- Workflow層
- SG / MY / TH展開
- Category自動確定
- 自動出品

## 判断方針

- 新batchの再検索対象を含む工程別証拠がそろうまでResolverの成功基準を決定しない。
- Resolver、Gate、Mapperの責務を広げすぎない。
- 工程間連携は将来のWorkflow層へ分離する。
- Category Mapper / AI Shadowと自動出品は、明示承認なしに開始しない。
