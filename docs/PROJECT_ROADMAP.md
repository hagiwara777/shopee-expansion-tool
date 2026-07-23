# PROJECT ROADMAP

## 正式完成済み

- PH Category Mapper Ver0.1
- Shopee Research CSV Import Adapter Ver0.1
- ASIN Resolverの不正URL耐性修正

## 実験中

- PH Category Mapper AI Shadow Ver0.2.1
- branch: `feature/ph-category-mapper-ai-shadow-v0.2.1`

## 現在の工程

1. Resolver不正URL修正をmainへ正式化
2. 固定30件のResolver・Keepa確認
3. FOUND商品をPrelisting Gateへ投入
4. Gate ELIGIBLEだけAI Shadowを先に実行
5. AI結果を見ずに人がCategoryを確定
6. 保存済みAI predictionを再評価
7. AIの追加価値と実務ボトルネックを判定

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
