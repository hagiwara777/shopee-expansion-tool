# SG初期Beta Ver1.0 — offline機能と受入境界

## 目的と適用範囲

Ownerの2026-10-13実装依頼と、初期Beta要件定義書Ver1.0案のSG初回MUSTを対象とする。
要件PDFは基本設計の入力であり、既存の正式Beta受入を置き換える資料ではない。
この実装の入口は既存`app_beta.py`への任意追加。通常PH／SG入口と稼働releaseは従来どおりである。
SGの1ショップを最初の対象とし、新しい巨大アプリ・API管理基盤・自動出品は作らない。

## 商品Factと条件付き自動確定

`sg_beta_facts.py`はtitle、brand、model、category tree、商品文章、成分を項目ごとに保存する。
値、OWN_PRODUCT／SEED_FALLBACK／UNKNOWN／MISSING、元ASIN、取得市場、資料参照、取得時刻を区別する。
raw Keepa記録の明示`domainId=5`だけをJP取得市場の証明として扱う。
旧cacheの暗黙JP default、ファイル名、JPらしい日本語商品名をJP証明にしない。
cacheで項目別出所が記録されていなければUNKNOWNとする。

Category ruleは人間承認参照、version、対象leaf ID／path、JP側末端名、正の条件と反例を持つ。
対象商品自身のJP Factだけが正の条件を満たせる。補完値・不明出所は使わず、矛盾した文章は拒否する。
複数ruleの競合、現行leaf不一致、入力不足ではCategory確認待ちとなる。
同梱物・多用途・他のleafに範囲を自動拡張しない。

新規ASINへの実証用ruleはSG 100578の有線audio例に限定する。
`OFFLINE_ONLY`は模擬再生の適用範囲であり、具体的ruleの実運用適用承認ではない。
Bluetooth／wireless／充電／battery、交換部品等の反例を拒否する。
反例が見つからないことをBattery不存在の証明にしない。

BrandはCategoryの有効性が成立した後にだけ確定する。
対象Category・shopへ結合した完全な現行一覧と、人間確認済みaliasのID／名前／区分が一致する場合だけAUTO_RULEとなる。
同名ID競合、alias競合、失効、未取得、空欄、未登録ではBrand確認待ちとなる。
No Brandの自動fallbackは存在しない。No Brandは現行一覧中の実ID／名前を人間が明示選択した商品に限る。
保存した旧公式一覧はSAVED_COMPARISONであり、currentな一覧へ自動昇格しない。
24時間TTLは導入しない。有効期間・更新契約が確定していない実運用一覧は停止を維持する。

## 共通の有効性契約

Category／Brandの監査種別はHUMANとAUTO_RULE。混在したCSV行はMIXEDとし、個別列も保持する。
AUTO_RULEをUSER_CONFIRMEDへ変換しない。既存の人間確認moduleは変更せず、新しい契約の中でSLS evaluatorを共用する。
Fact、Category catalog、rule、Brand catalog、aliasの変更と取消は保存済み判断を失効させる。
取消済みCategory ruleやBrandは、新商品群の受付だけでは再採用されない。
再確認の履歴は削除しない。

`assess()`を確認待ち・準備判定・CSV／TXT・コピー確認で共用する。
現在の全ショップCSVから既存Gateを再実行し、現在Guardrail、SLS、SG本体確認、武器画像の既存validatorを使う。
BLOCK／REVIEW／EXCLUDE、Battery／SLS停止を分類確定や人間メモで解除しない。
確認済み本体・実同梱の除外履歴は新資料でも維持する。
画像確認資料がない場合は、画像対象外と推定して通過させない。
未知・破損・未確認は確認待ちとなり、選択商品の出力直前に再検証する。

## 長期SG作業DB

`sg_beta_work_store.py`はSQLiteの既存手法を用い、SG／shop／専用schema markerへ結合する。
新規DB作成は明示操作かつ新規ファイル限定。既存DBを初期化・schema修復・移行しない。
商品Fact、元Candidate／Safety資料、判断根拠、確認・取消メモ、状態、全操作履歴を保存する。
商品の保存先はAPI operation、Policy、Grant、ledger、claimの保存先から分離する。
operation参照が切り替わっても同じ長期DBの記録は残る。消費記録を移行・resetしない。

Safety、Category、Brandの確認待ちは区別して保存し、理由別のCSVへ出せる。
商品群を横断して出品待ちを蓄積する。類似商品をグループ表示し、任意のASINだけを選択して一括採用できる。
Category採用だけではBrandを採用しない。未解決商品があっても、完成した別の商品だけを出力できる。
BEGIN IMMEDIATE、全件transaction、revision照合、checksumで、二重操作・古い選択・保存失敗・部分更新を止める。
保存成功のcommitより先にCSV／TXTや成功表示を返さない。DB欠落・破損は再作成せず停止する。
checksumは取り違え・破損検出であり、悪意あるDB改変への電子署名ではない。

## 出品作業の5状態

| 状態 | 操作と条件 |
| --- | --- |
| 出品待ち | 準備有効・コピー予約なし。選択して出力可能。 |
| 出品確認待ち | 人間がコピー成功を明示確認。次のコピー対象から除外。 |
| 出品済み | 現在のSG全ショップCSVのParent SKUまたはSKUで一致。 |
| 出品エラー | 外部ツールでの失敗を人間が確認し、コピー確認済みASINを一括登録。 |
| 再確認必要 | 判断根拠・資料が失効、分類未解決、Safety停止等。再評価なしに出力しない。 |

準備の有効性と出品作業状態を分離する。既出品の履歴は資料変更でも失わない。
CSVに見つからないだけでは出品エラー・出品待ちへ戻さない。
エラー・確認待ち・再確認必要から戻す場合は、人間の明示操作と現在の準備再検証を要する。

コピー準備は永続PENDING予約を作り、そのASINを新しいコピー操作からロックする。
人間確認のSUCCESSだけが出品確認待ちへ進む。UNKNOWNは再起動後もロックを維持する。
FAILED／CANCELLEDは明示確認で予約を閉じる。取消前の操作と根拠は履歴に残る。
資料変更後の古いコピー予約はSUCCESSにできない。結果を確認し、明示取消等で回復する。
CSV／TXTダウンロードだけではコピー・出品状態を更新しない。
コピーはSeller Centerへの出品成功を意味しない。

CSVは既存先頭11列を維持し、末尾にcategory_authority／brand_authority／output_scopeを追加する。
各ASIN自身のverification_statusを保持する。先頭商品の値を他の行へ複製しない。
CSV／TXTはいずれもUTF-8 BOM。国×leaf Category ID×Brand ID別のグループとASIN一覧を出す。
同じ必須属性値を使えるかは人間が選別し、全属性推定や自動分割は実装しない。
初期接続はOFFLINE限定で、listing_ready=FALSE、output_scope=SG_INITIAL_BETA_OFFLINEと表示する。

## offline画面の再生

検証用の新しい保存先と`synthetic-shop`を明示し、既存app_betaへ追加画面を表示できる。
8503へ反映せず、サーバーを起動する場合は空いている開発用ポートを別指定する。

```powershell
python -m streamlit run app_beta.py --server.port 8510 -- --sg-work-db outputs/demo-work.sqlite3 --sg-work-shop synthetic-shop
```

1. 対象国SGを選び、追加画面で新しい保存先を作る。
2. `tests/fixtures/browser_e2e/sg_initial_beta/context.json`と`SG_inventory.csv`を読み、今回のCSVを明示確認する。
3. 同じfixtureのcandidate.csv、facts.json、product_text.csv、weapon.jsonを新しい候補群として保存する。
4. グループと任意ASINを選び、Category／Brand採用、確認メモ、取消、出力、コピー結果を操作する。
5. アプリを再起動し、同じ保存先を開く。現在catalog／既出品資料を再度確認して再開する。

全fixtureは人工商品。Brandの7・0等も模擬IDであり、現行公式一覧ではない。
Chrome操作ファイルをこのsource fixtureへ保存しない。AppTestはブラウザ・サーバー・APIを使わない。

## 実商品Evidenceと残る実務受入

指定4ASINの保存cacheをread-onlyで検査した。全4件に取得市場domainIdと項目別出所が記録されておらず、
JPかつOWN_PRODUCTであることを証明できなかった。原記録へJPやOWN_PRODUCTを補記しない。
この資料のままでは全4件のCategory／Brand自動確定を拒否する。
ATH-M20xの正例成立や現在の公式Brand有効性を実証済みとは扱わない。
Bluetooth反例の文章がある記録も、出品安全性受入とは区別する。

少量実務受入前に、対象商品自身のJP取得市場・項目別出所を証明できるFactと、現在有効な公式Brandの更新契約を整える。
限定rule／aliasの実運用適用、長期保存先の設置、必要なAPI枠、release更新、少量実商品の確認は別の明示承認を要する。
OwnerのSG通常継続利用タスクは少量実務受入が未完了であり、このoffline実装によって完了扱いにしない。
実Shopee／Keepa／OpenAI API、実出品、credential、8503反映、旧DB移行、main mergeは本作業の実行対象外。
GPT-6 Luna移行、Shampoo大量Brand取得、MY／TW／TH、外部ツール自動操作は別scope。
