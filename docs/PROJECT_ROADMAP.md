# PROJECT ROADMAP

## 正式完成済み

- PH Category Mapper Ver0.1
- Shopee Research CSV Import Adapter Ver0.1
- ASIN Resolverの不正URL耐性修正

## 実験中

- PH Category Mapper AI Shadow Ver0.2.1
- branch: `feature/ph-category-mapper-ai-shadow-v0.2.1`

## 現在の工程

1. PH固定30件評価を継続する
2. 現在取得済みの9件の元Shopee商品と13件のAmazon候補について同一性監査を行う
3. 各候補を`MATCH`、`VARIANT_MATCH`、`UNCERTAIN`、`MISMATCH`に分類する
4. `VARIANT_MATCH`は完全一致率に含めない
5. 固定30件全体の評価を完了し、結果を記録する
6. 評価結果をユーザーが確認する
7. ユーザーが明示的に開始を承認した後にだけCategory Mapper / AI Shadowへ進める。Prelisting Gateの`ELIGIBLE`だけでは開始しない

## 保留

- AI候補の1クリック採用 Ver0.3
- wrong category蓄積 Ver0.4
- Workflow層
- SG / MY / TH展開
- Category自動確定
- 自動出品

## 判断方針

- 固定30件の評価結果が出るまで大機能を追加しない
- AIの追加価値が弱い場合は、ルール・確認履歴・wrong category中心へ寄せる
- Resolver、Gate、Mapperの責務を広げすぎない
- 工程間連携は将来のWorkflow層へ分離する
