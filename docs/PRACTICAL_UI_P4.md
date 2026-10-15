# PH・SG共通の日常操作（P4）

P1準備有効性、P2長期保存、P3分類確認を同じ `app_beta.py` へ接続する。
この入口はoffline操作検証専用。模擬catalog・Brand・限定AUTO_RULEを公式取得済みとは表示しない。
出力は常に `listing_ready=FALSE` / `output_scope=PH_SG_P1_OFFLINE`。
実出品可能な準備出力、実API、稼働release反映、既存保存先の移行を許可する入口ではない。
P4だけでは[実務Beta完成条件](PRACTICAL_BETA_COMPLETION.md)C01〜C12の実務受入は成立しない。

## 起動と保存先

PH・SGの新しいP2作業保存先とshopを明示する。未指定時は従来のPH／SG経路を維持する。
旧SG専用offline入口、分類P3の起動引数も維持する。通常設定やショートカットを変更しない。

```powershell
python -m streamlit run app_beta.py --server.port 8510 -- --ph-practical-db outputs/p4-ph.sqlite3 --ph-practical-shop synthetic-shop --sg-practical-db outputs/p4-sg.sqlite3 --sg-practical-shop synthetic-shop
```

画面で「新しい作業保存先を作成」を押すと、新規ファイルだけを明示作成する。
再起動後は同じ引数で開く。既存ファイルの初期化・修復・移行は行わない。
市場・shop・`PH_SG_BETA_WORK_V2` schema・store identityが一致しない場合は停止する。
保存先とshopは常に画面上部へ表示する。市場／shop切替では一時入力・確認・資料・出力を破棄し、履歴は保持する。

## 共通の操作

1. **候補受付**：ExpansionとResolverの既存入口・固定15列Candidateを使う。
   P4起動では実APIボタンを停止し、保存した合成CandidateとSafety資料で再生する。
   管理・診断の「合成商品根拠」には対象国の項目別Fact・未評価画像情報を読み込める。
   これは出所の申告であり、公式取得receiptや実商品の証明へ昇格しない。
2. **Safety・重複確認**：元Candidate・商品文章・必要な成分／画像／SG本体資料、全ショップCSVを入力する。
   受付と「出品前チェックを実行」は別操作。市場固有の停止理由は同じ場所へ表示する。
   Gate未実行、資料欠損・不一致・削除では分類への現在根拠を搬送しない。
3. **現在根拠の保存**：管理・分類資料設定で今回の模擬catalog／Brandを指定する。
   全ショップCSVそれぞれと実shop IDの対応を入力し、今回の最新資料であることを確認して保存する。
   保存済み履歴や内部shop labelを実shopの証明にしない。
4. **分類・確認待ち**：Safety／Category／Brandの待ちを別々に選べる。
   グループと任意ASINを選び、現在leaf Categoryと対応Brand／No Brandを独立確認する。
   確認者・判断根拠・今回の確認を入力して保存する。10商品から3商品だけ採用した場合、残り7商品は保留。
   HUMAN／AUTO_RULEは項目別に表示し、失効した旧判断には「要再確認」を付ける。
   未承認AUTO_RULEの運用許可をUI・JSON・環境変数から作らない。
5. **準備pool・CSV／TXT**：商品群を横断した現在有効分から、市場×leaf Category ID×Brand IDのグループと任意ASINを選ぶ。
   P1・P2の既存validator／formatterを出力前と返却前に使い、保存失敗・途中失効ではbytesを返さない。
   CSV先頭11列、末尾の項目別authority／scope、UTF-8 BOM、TXTのグループ・ASIN集合を維持する。
   ファイルは作成操作の実行時だけ表示し、再描画後の古いdownload cacheを作らない。
6. **出品作業・履歴**：確認待ちを保留しながら、5状態と投入進行・根拠・予約lockを確認する。
   メモ・保留・除外・出品エラー・明示RETURNを任意ASINへ保存する。
   履歴では確認・取消・失効・投入結果と理由を確認できる。

通常操作と管理・診断は別のexpanderへ分ける。通常側に保存先、現在資料、停止理由、必要な復旧操作を残す。
Product Finder診断、Resolver Evidence Batch、Shadow比較は明示した診断表示をONにしたときだけ表示する。
P4用設定を指定しない既存経路は、従来のAPI承認枠・認証・表示を使用する。

## 再起動・A→B・取得世代

Aの途中保存後に再起動してBを追加できる。Expansion／Resolverの出所・商品群参照はP2履歴へ残る。
同sessionの無関係な新B群は、現在有効なA群を消さない。
再起動後のA群は履歴だけを保持し、現在のA資料を再受付してCategory→Brandを再確認する。
再確認したAとBの完成分は同じpoolへ蓄積する。

分類資料／商品根拠の明示再読込、資料変更・削除・読込失敗は、対象の旧確認を先に失効する。
同じ内容の資料を再取得しただけで旧Category／Brandを復活させない。
通常の再描画だけでは新しい取得世代を作らない。失効履歴を削除せず、人間再確認を要求する。
現在資料が未読込でも、出品作業・履歴から未解決予約の結果確認・取消へ到達できる。

## 5状態・永続予約

| 状態 | 操作・根拠 |
|---|---|
| 出品待ち | 現在のP1準備が有効、投入進行WAITING、未解決予約なし。P4ではoffline準備有効を意味する |
| 出品確認待ち | 模擬投入前に永続予約し、本人が予約全件の成功を明示確認した場合だけ進む |
| 出品済み | 今回の対象市場・全ショップCSVのParent SKU／SKUに一致した場合だけ進む。合成CSVの再生結果を実出品の証拠にしない |
| 出品エラー | 成功確認済みの投入に対し、本人がエラーを確認して登録する |
| 再確認必要 | 未確認・取消・資料不足・失効・Safety停止。分類再確認だけで投入成功履歴を消さない |

「offline CSV／TXTを作成」は投入予約を作らず、ダウンロードだけでは状態を進めない。
「模擬投入前の永続予約を作成」はP2のPENDINGをcommitしてからファイルを返す。
UNKNOWNはlockを保持し、再起動・再分類でも二重投入を拒否する。
結果は予約全件を選び、根拠・本人確認とともにSUCCESS／UNKNOWN／FAILED／CANCELLEDで保存する。
古いsession・revision・準備根拠のSUCCESSは拒否する。反映を現在CSVで照合するか、結果を本人が確認して失敗・取消で解決する。
エラー・出品確認待ちから戻す場合は現在準備と理由付きRETURNを要求する。出品済みを不在CSVだけで戻さない。
外部ツールのコピー・投入・出品を自動操作する機能はない。

## 武器画像と停止時の復旧

国別rootによる対象選択と既存validatorを使い、対象外には追加の人間確認を要求しない。
画像対象は共通の「武器画像の対象・疑義・復旧」で、現在商品・文章・画像・市場に結合した模擬検査を読み込める。
JSONは `PH_SG_P4_WEAPON_OFFLINE_V1`、市場・ASIN・現在source binding・既存weapon captureを持つ。
他市場の評価、別商品・別画像・古いbinding、JSONに含まれた人間の準備継続判断は拒否する。
検査資料の更新・削除は先に旧検査と分類確認を失効する。失効の保存失敗では対象Factも停止する。
疑義なしでは追加の人間確認を要求せず、疑義あり・判断不能だけ対象画像への明示判断を保存する。
人間判断は画像疑義だけを扱い、Guardrail／Battery／SLS／SG本体・実同梱等の既存停止は解除しない。
実画像の取得・実APIは接続しない。模擬検査も公式評価・実運用出力へ昇格しない。

資料不足・取得失敗では必要な再受付／再確認を表示する。認証切れ・公式取得失敗の実接続復旧は既存の承認済み経路を使う。
保存先不一致・破損・書込失敗では出力と成功表示を停止し、DBの再作成・初期化で直さない。
旧PH／SG DB、Policy／Grant、API ledger／claim、credential、固定releaseはこの入口から変更しない。

## 検証資料と次工程

`tests/fixtures/browser_e2e/ph_sg_practical_p4/{PH,SG}` は人工商品だけを含む。
AはExpansion 10商品、BはResolver 2商品。既存P3の各国 `*_context.json` と組み合わせる。
Chrome用コピーは `Documents/ShopeeE2E` の専用ディレクトリへ生成し、source fixtureを操作用に書き換えない。
`tests/test_practical_beta_p4_ui.py` は両市場のA01〜A06の主要操作、現在根拠・Safety停止・失敗・復旧をAppTestで検証する。
P1/P2/P3とPH／SG protected testsを併用する。正確な実行結果はGit外Evidenceと対象headのCIを参照する。
AppTest、実Chromeの表示・読込確認、実API、実商品、Owner実務受入を別々に記録する。

次の独立工程はF1/F2（Beta前MUST）。その後のP5で両市場の少量実商品反復受入を別承認する。
分類精度、公式Brandのlive完全性・更新頻度と費用、SG本体・画像の実商品証明、長時間運用をoffline成功で受入済みにしない。
新しいBeta MUSTを自動追加しない。
