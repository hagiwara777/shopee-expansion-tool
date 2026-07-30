# PROJECT ROADMAP

## 当面の全体目標

PHにおいて、候補生成から既存出品ツールへの受け渡し準備までを段階別に検証できる状態にする。
Resolverの成功は、英字商品名から正しいASINへの到達性能で判断する。Resolver、Expansion、
Gate、Mapperの責務を分離し、外部出品ツール契約、自動Workflow、自動出品は別設計・別承認とする。

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

## 事業全体フロー

### 1. 候補生成

- 英字商品名 → Resolver → ASIN候補
- 既知ASIN → Expansion Tool → 関連ASIN候補

### 2. 候補選別

- Guardrail／出品前保安ゲート
- `ELIGIBLE` / `REVIEW` / `EXCLUDE`
- 現在の市場対応範囲は別途コード・仕様監査が必要

### 3. 出品準備

- Category Mapper
- Category ID
- Brand ID
- 必須属性情報
- 人間確認
- 既存出品ツール向け受け渡し準備

### 4. 出品

- 既存出品ツールを使用
- 正式入力契約は未確認
- 自動接続・自動出品は未承認

## 現在から先の工程

1. 事業全体フローとロードマップの正本正式化
2. 既存出品ツールの正式入力契約と、PH工程間接続の読み取り専用監査
3. Resolver／Expansion、Gate、Mapper間の接続設計ゲート
4. 外部AI・Keepa・新規固定30件基準実行の別決裁
5. 承認後、新規固定30件基準実行
6. 初回検索、再検索、Resolver解析、Keepa確認、商品同一性の工程別集計
7. 英字商品名から正しいASINへの到達性能評価
8. Resolverの続行・改善投資・保留・打ち切り判断
9. PHで候補生成から既存出品ツール受け渡しまでの端から端の受入
10. PH成立後、SG・MY展開の市場別設計
11. SG・MYの着手順を事業判断
12. THの優先順位を別途判断
13. Category Mapper AI Shadowはオーナー明示承認後だけ実施

## 保留

- Workflow層
- Resolver／ExpansionからGateへの自動投入
- GateからCategory Mapperへの自動投入
- 既存出品ツールへの自動投入
- Category自動確定
- 自動出品
- SG／MY／THの実装
- AI候補の1クリック採用 Ver0.3
- wrong category蓄積 Ver0.4

## 判断方針

- 証拠保存機能の完成だけでResolver成功を宣言しない。
- Resolver成功は英字商品名から正しいASINへの到達性能で判断する。
- 未確認の既存出品ツール契約を実装済みとして扱わない。
- PHで成立確認後にSG／MYへ進む。
- SG／MYの順序は証拠と事業判断なしに固定しない。
- 工程間連携は別設計ゲートを通す。
- Category Mapper AI Shadowと自動出品は、明示承認なしに開始しない。
