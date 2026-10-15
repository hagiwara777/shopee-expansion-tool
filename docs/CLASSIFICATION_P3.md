# PH・SG共通の分類確認・現在根拠搬送（P3）

DEC-0141のoffline実装契約。P3は実務Beta全体の完成ではない。
既存`PreparationSession`、`BetaWorkBench`、Category／Brand validator・検索、限定rule／aliasを再利用する。
判断・操作を共通化し、catalog・ID・shop・保存先・Safety・認証は市場別に保持する。

## 共通操作と保存

1. 既存Expansion／Resolver応答から、対象自身のJP取得・項目別FactをCandidate・Safety資料と結合する。
2. 現在の市場別catalog・rule／alias版と、対象shopを含む全ショップCSVをP1へ明示搬送する。
3. Categoryを検索・候補提示し、選択ASINだけHUMAN採用または限定AUTO_RULEを適用する。
4. その商品の現在Categoryが有効な場合だけBrand候補を出し、別操作で採用する。
5. P1を再検証し、判断根拠・項目別authority・確認者・メモをP2履歴へtransaction保存する。

`ClassificationSelection`は市場・shop・session・資料revision・ASIN別保存revisionを保持する。
10商品から3商品を採用しても、未選択7商品のCategory／Brandは変わらない。
古い選択、競合、資料変更、途中保存失敗は全件停止・rollbackとなる。新しいB群の追加でA群の履歴を削除しない。
Category変更・取消ではBrandも失効する。Brand取消はCategoryを自動取消しない。
取消を商品群追加で自動再採用せず、再起動後の過去判断は履歴としてのみ使用する。
catalog・模擬Brandは取込世代も結合し、同じ内容の再読込で失敗前の判断を復活させない。
対象Factの現在根拠を失った後の再受付も、内容が同じでもCategory／Brandを再確認へ戻す。

## 根拠と限定AUTO_RULEの境界

Keepaの既存取得応答へ項目別`ProductFacts`を追加搬送する。追加API要求やcache schema移行はない。
応答自身の明示`domainId=5`とASINだけをJP・商品所有根拠に使う。seed補完、旧cacheの暗黙JP、
取得市場不明、CSVの文字列からOWN_PRODUCTを作らない。Candidate時刻はその商品の取得時刻へ揃える。
古い資料を今回搬送しただけでは準備許可にならず、現在の資料照合・確認をP1で再実行する。
内容hashと出所記録はAPI応答・CSVの真正性を暗号学的に証明するものではない。

AUTO_RULEは既存の有限Category ruleとBrand aliasだけを使用する。新しい運用ruleは追加していない。
一意の正の根拠、対象自身のJP Fact、市場・shop・session、現在leaf・path、rule／alias版、
完全なcurrent BrandのID・名前・区分を要求する。競合・不明・部分取得は保留する。
Brandが見つからない場合のNo Brand fallbackはなく、No Brandは候補の実IDを人間が明示採用する。
CategoryとBrandのauthorityを個別保持し、HUMAN／AUTO_RULE混在をMIXEDとして出力する。

P1運用出力のAUTO_RULE拒否は既定で維持する。単なる`OPERATION_APPROVED`記載では許可されない。
将来の承認済みadapter用に`AutoRuleApproval`の最小照合契約を設けた。
市場・shop・session、項目種別、rule／alias定義全体のhash、catalog binding、承認参照を完全一致で要求し、
CategoryとBrandの各AUTO_RULEへ別々に照合する。catalog更新開始で許可を破棄し、
出力前後に再検証する。公式Brandの今回strict取得receiptと既存SG operation gateも維持する。
これはOwner承認を証明・生成する機構ではなく、承認済み範囲を正確に運ぶための契約である。
UI、JSON、環境変数、DBからこの許可を作るloaderはない。P3の通常adapterは許可を注入せず、
既存SG例もOFFLINE_ONLYのまま。個別ruleの実運用採用とadapter設定には別承認が必要である。

## 通常アプリ内の最小接続

同じ`app_beta.py`・対象国・Category Mapperタブで、両市場に同じ分類操作を表示できる。
市場ごとに新規P2保存先とshopを明示する。既存PH／SG保存先へ自動接続・移行しない。

```powershell
python -m streamlit run app_beta.py --server.port 8510 -- --ph-classification-db outputs/p3-ph.sqlite3 --ph-classification-shop synthetic-shop --sg-classification-db outputs/p3-sg.sqlite3 --sg-classification-shop synthetic-shop
```

この例は別のoffline確認用起動で、稼働release・既存起動先の変更指示ではない。
`tests/fixtures/browser_e2e/ph_sg_classification_p3/PH_context.json`／`SG_context.json`は人工catalog・模擬Brand資料。
通常タブで保存先を明示作成し、対象国の分類資料を読み込む。Gateで今回のCandidate・Safety・全ショップCSVを検証する。
分類画面でCSVと実shopの対応を明示し、全ショップの最新資料を確認して保存する。
新規取得や公式一覧の取得を起動・再描画で自動実行しない。
Gate入力の削除・失敗で今回のinventory根拠を失効させ、変更した商品根拠は新規保存操作より先に失効させる。
この新規P3画面は模擬資料の明示確認を目的とし、実APIのcatalog取得UIは接続していない。
通常の検証済みcatalog producerは共通`ClassificationWorkflow.supply_catalog`へ、承認済みClientは
`acquire_brand`へ注入できる。P1のstrict完全取得・最大10ページ・失敗時失効と既存Clientの有限枠を維持する。

## 準備poolと保護・残作業

現在P1が有効な商品だけP2準備poolへ入る。Safety／Battery／SLS、SG本体・実同梱、画像疑義を
分類採用・AUTO_RULE・確認メモで解除しない。画像の他市場評価をコピーせず、対象画像検査が未搬送なら保留する。
P2の5状態・永続投入予約・結果不明lock・履歴は維持する。P3は通常画面から投入・出品状態を変更しない。

P3から後続のP4へ渡した通常画面・管理／診断・画像確認の搬送・共通CSV／TXT・準備pool・5状態の操作と復旧は、
[P4共通日常操作](PRACTICAL_UI_P4.md)で新規保存先を明示してoffline接続する。
本P3の通常接続は、明示した新規保存先でのoffline根拠搬送・分類操作まで。
P1〜P4とF1/F2の後、P5で両市場の実API・実商品反復受入を別承認で行う。
公式Brandのlive完全性、長時間作業・再取得条件と費用、個別ruleの実商品精度はoffline成功だけで成立しない。
実API・有料API・実商品・credential・DB移行・固定release・deploy・実出品は未実行である。

主な回帰は`test_classification_p3.py`、`test_classification_p3_ui.py`、P1/P2・既存PH/SG protected tests。
正常系・失効・競合・3/10選択・rollbackと、実際の統一アプリ→Gate→P1/P2を合成資料で確認する。
実行結果の正本はGit外Evidenceと対象headのCIとする。
