# PH・SG共通の準備有効性（P1）

DEC-0139の共通契約。P1は実務Beta全体の完成ではない。
`modules/preparation_validity.py`が有効性を扱い、既存の分類・Safety validatorを呼ぶ。
新しい作業DB、汎用Fact基盤、Workflowは追加しない。

## 確認と停止

1. `PreparationSession`をPHまたはSGと対象shopへ固定して開始する。
2. 現在の検証済みCategory catalogと取得参照、rule／alias版を渡す。完全hierarchy、ID、path、leafを既存validatorで検査する。
3. 現在の全ショップCSVを既存parserで読み、対象shopを含む期待shop集合・市場・今回確認へ結合する。件数だけの一致を根拠にしない。
4. 商品自身のJP Factを項目別に読み込む。旧cacheの暗黙JP、seed値、UNKNOWNは証明としない。
5. Categoryを採用してから、そのCategoryの完全なBrand一覧の実ID／名前／区分を明示採用する。
6. 準備情報・CSV／TXTを返す直前にGate・重複・現在Safety・市場別SLS・必要な本体／画像確認と各根拠を再検証する。

任意項目の空欄を架空のFactで埋めない。存在する項目の出所・対象ASIN・取得市場と時刻を検査する。
商品文章とCandidate、Factの文章、画像選択rootを照合し、欠損や矛盾は停止理由を返す。
Category／Brand採用はSafety処分を変更しない。No Brandは一覧の明示選択に限る。

## 更新契約

`begin_catalog_refresh`、`begin_brand_refresh`、`begin_inventory_refresh`、`begin_fact_refresh`を
更新試行の前に呼ぶ。取得開始時点で対象旧根拠を失効し、失敗後も旧成功を復活させない。
新しい分類資料・rule／alias版は旧Category／Brand判断を失効する。
再起動・市場／shop切替は新session。保存時刻や過去SUCCESSからreceiptを復元しない。
固定24時間TTL、永続的な最新保証、自動更新APIは設けない。
長時間利用・再起動時の実際の再取得費用と鮮度条件はP5前に確認する。

`acquire_brand`は明示注入された既存共通Clientのstrict検査を使い、終端まで最大10ページを取得する。
途中失敗、raw不正、重複矛盾、反復page、offset異常、上限到達は未完了として停止する。
Client側の認証・有限API枠の責務を維持し、この部品はcredentialを探索・保存しない。
今回のtestsはfake APIだけであり、実Shopeeを取得した証拠ではない。
保存した公式一覧は比較資料であり、JSONのsource名やcomplete/currentフラグだけで通常出力を許可しない。

## 入口・正常出力・制約

PHの`build_mapper_exports`は`preparation_session`とASIN別`preparation_records`を検査する。
SGの既存workflowは同じ2項目を準備判定と両出力へ渡す。未搬送なら再確認理由を表示し、旧確認フラグへfallbackしない。
通常UIのproducer全面接続はP3／P4へ引き継ぐため、この版で根拠未搬送の商品は準備出力が停止する。
既存固定release・実運用DBは更新しない。

正常な現在根拠を注入したPH／SGの合成回帰は、従来のgroup・列・手動準備CSV／TXTを維持する。
`PreparationSession.output()`の既定はoffline用（FALSE／PH_SG_P1_OFFLINE）。
通常手動準備用のTRUEは、今回のstrict公式取得receiptとHUMAN確認が成立する場合だけ扱う。
OFFLINE_ONLYのAUTO_RULEを運用へ昇格せず、SGの有効化gateも出力前後に維持する。
FALSEのoffline出力や模擬Brandを実商品受入へ昇格しない。
型付きClientや資料のhashは、外部サーバー内部の誤応答や入力者の虚偽を暗号学的に保証しない。
Brand APIの市場／Category echo欠如、全ショップCSVの真正性は既存の制約として残る。

## 後続工程

P2はこの検証結果を現在状態の根拠として用い、保存履歴と現在有効性を分離する。
保存した過去のvalidフラグ・receiptを出力権限へ復元しない。新規保存先・5状態はP2で扱う。
P3／P4は対象自身のJP証明・市場別catalog／全ショップ根拠を通常入口から搬送し、具体的ruleの運用適用を別途判断する。
P1〜P4とF1/F2完成後のP5で、別承認を得て両国の少量実商品反復受入を行う。

主な回帰は`test_preparation_validity.py`、`test_preparation_exit_contract.py`と既存PH／SG・Safety・protected tests。
実行結果はGit外Evidenceと現在対象のCIで確認する。
