# PH・SG共通の長期保存・作業状態（P2）

DEC-0140のoffline backend契約。P2だけでは実務Beta完成ではない。
`beta_work_store.py`は既存SG storeのSQLite・transaction・revision・予約を共通化し、
`beta_workbench.py`は[P1](PREPARATION_VALIDITY_P1.md)の現在根拠検証を利用する。
通常画面、分類の限定自動確定、公式資料の取得producerはP3／P4へ引き継ぐ。

## 保存と市場・shopの分離

`BetaWorkStore.create(path, marketplace='PH'または'SG', shop_id=...)`は明示操作で新規ファイルだけを作る。
開く操作はファイルを作成しない。既存ファイルの初期化・修復・移行・resetは提供しない。
各DBは一市場・一shop・`PH_SG_BETA_WORK_V2`・固有store IDへ固定する。
誤った市場／shop／schema、開いた後の別DBへの差替えは停止する。
PH既存保存先、旧SG `SG_INITIAL_BETA_WORK_V1`、通常DB・Policy・ledger・claimは自動接続しない。
旧`SGWorkStore`のAPIとschemaは互換wrapperで保持し、旧入口は従来のSG限定のままとする。

ASIN、商品群参照とCandidate出所、項目別Fact・取得根拠、Candidate／文章／成分／本体／画像確認資料、
Category／Brand判断と根拠、取消、Safety確認待ち・理由・人間メモ、準備状態、出品作業状態、
全操作のrevision付き履歴、投入予約を保存する。画像本体・認証・API消費記録はこのDBの責務に含めない。
同一ASINは現在の商品行を更新し、出所と過去の判断・操作を履歴に残す。別ASINや別商品群は削除しない。

## 再開・準備pool

`BetaWorkBench(store, PreparationSession(marketplace, shop_id))`を新しいsessionで開始する。
保存済みvalid／SUCCESS・Category／Brand・catalog・API結果をsessionへ読み戻さない。
再開直後の古い判断は比較用履歴として保持し、準備は再確認必要となる。
現在の検証済みcatalog・完全Brand一覧・全ショップCSV・対象自身のFactをP1へ明示搬送し、
現在の選択商品をCategory→Brandの順で人間再確認する。P2は自動再採用を提供しない。
APIを自動実行せず、不足や失敗は停止する。P1の固定TTLなし・取得失敗時失効・公式receipt条件を保つ。

商品群Aを途中保存して再起動し、Bを追加できる。Aの過去履歴は残る。
現在根拠の再確認を済ませたA・Bの完成分は同じ市場／shopの`prepared_pool()`へ蓄積する。
同じsessionの変更のない商品は判断を保持できるが、追加受付や古いvalidだけで有効とはしない。
商品／Fact／Safety資料変更時は対象Category／Brandを未確認へ戻す。
取消した判断は商品群の追加で自動再確定しない。分類の採用・メモはSafety停止を解除しない。

## 5状態と投入予約

| 表示状態／内部値 | 条件と動作 |
|---|---|
| 出品待ち／WAITING | P1の現在準備が有効で、投入進行もWAITING。未解決予約があれば出力対象から除外 |
| 出品確認待ち／AWAITING_LISTING | 永続予約した投入について、人間が外部ツールへの成功を明示確認した場合だけ進む |
| 出品済み／LISTED | 今回確認した対象市場の全ショップCSVのParent SKUまたはSKUで一致した場合だけ進む |
| 出品エラー／ERROR | 投入成功履歴のある商品について人間が外部ツールのエラーを確認した場合に進む |
| 再確認必要／RECHECK | 未確認、取消、根拠不足・失効、Safety停止。準備の再確認を要する |

準備状態と投入進行を別々に保存する。出品確認待ちの商品が再確認必要になっても、
投入成功履歴を保持する。分類を再確認しただけで新しい投入対象には戻らない。
ERRORや出品確認待ちから出品待ちへ戻すには、現在準備の成立と理由付きの明示RETURNを必要とする。
最新CSVに存在しないだけで出品済みを解除しない。出品済み商品は出力・RETURNを拒否する。
CSV／TXTダウンロードは出品確認待ち・出品済みへの遷移ではない。

外部ツールへ投入・コピーする前に、`output(selection, reserve_copy=True)`でPENDING予約をcommitする。
selectionは全対象ASINと現在revisionの組。出力bytesは保存成功後にだけ返す。
`finish_copy(operation_id, selection, outcome=..., human_confirmed=True, note=...)`で予約全件を解決する。
UNKNOWNはロックを保持し、再起動・再分類でも二重投入を拒否する。
古いsession・revision・準備根拠の予約をSUCCESSにしない。現在のCSVで反映を確認するか、
人間が結果を確認してFAILED／CANCELLEDで閉じる。UNKNOWNの単なる待機・再起動は取消を意味しない。
同sessionの根拠・revisionが一致するUNKNOWNは、明示SUCCESSで解決できる。
外部ツールを実際に操作する機能は含まない。

## 障害時と検証

BEGIN IMMEDIATE、全件transaction、revision、商品・履歴・予約checksum、履歴総件数とロックの整合照合を使う。
途中更新・commit失敗では全件rollbackし、出力成功を返さない。選択変更、DB欠落・破損、
履歴・予約・ロック欠落では停止し、DBを再作成しない。未解決予約を削除して復旧しない。
保存中や出力生成中のP1更新開始も検出し、古い準備出力を返さない。
commit後に根拠の失効が判明した場合も出力を返さず、作成済み予約は未解決のまま残して明示解決する。
checksumは破損・取り違え検出であり、悪意ある全DB巻戻しへの署名保証ではない。
クラウド保存・backup管理・実運用DB復旧UIは含まない。

`tests/test_beta_workbench_p2.py`はPH／SGそれぞれで再起動、A→B、再登場、取消、失効、5状態、
結果不明・同時予約、全ショップ照合、欠損・破損・保存失敗・P1停止を合成資料で検証する。
既存P1、SG初期Beta、Guardrail／Gate／SLS、PH／SG protected回帰も維持する。
実API・実商品・保存先設置・固定release変更・deploy・実出品の受入証拠にはしない。

P3の[分類操作・現在根拠搬送](CLASSIFICATION_P3.md)は、新規保存先を明示した通常Mapperタブから、
共通確認・限定offline AUTO_RULE・任意部分集合をこのbackendへ接続する。旧DBは接続・移行しない。
通常画面全体の操作統一と管理／診断整理はP4。F1/F2完成後にP5の両市場実商品受入へ進む。
