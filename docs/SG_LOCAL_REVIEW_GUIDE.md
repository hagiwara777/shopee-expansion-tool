# SG機能統一の開発版を確認する

SGの追加機能を通常PH環境から切り離して操作確認する入口は `app_sg_candidate.py`。
外部APIに接続しない再生モードで、通常のDB・cache・認証・ショートカットを使用しない。
これはSGの正式版・出品用ファイルの提供ではない。

## 起動

Repository rootで次を実行する。`PythonPath`はStreamlitを導入済みのPythonを指定する。
通常PHの8501と別の8502を使い、localhostのみで待ち受ける。

```powershell
.\scripts\Start-SGCandidate.ps1 -PythonPath <python.exeのパス>
```

`-CheckOnly`は依存関係とimportだけを確認する。アプリやAPIを起動しない。
デスクトップのPH Betaショートカットは今回変更しない。

## 合成資料で一連の操作を確認する

Versioned source fixtureは `tests/fixtures/browser_e2e/sg_candidate/`。
実商品・実APIの結果ではない。画像とAI回答も合成であり、精度評価や出品へ使わない。
Chromeで扱う作業用コピーが必要な場合は既存Browser E2E手順に従い
`Documents\ShopeeE2E`へ作成する。ダウンロードをsource fixtureへ戻さない。

1. `replay.json`を「SG接続確認用の再生資料」へ読み込み、「隔離した確認環境を作る」を押す。
2. 設定を開き、`catalog.csv`を読込・検証して取り込む。
3. `prelisting_gate_eligible_sg_expansion.csv`を商品CSVへ読み込む。
4. 確認資料の欄へ `candidate.csv`、`product_text.csv`、`raw_images.json`を読み込み、
   「確認資料を読み込む」を押す。元CSVとの対応・商品情報・国を検証する。
5. 「Category確認を開始」→「AI Category候補を作成」→候補を確認して採用。
   合成例はSG Category `100869`。候補表示だけでは採用済みにならない。
6. Brand候補を取得し、`7 | Example Brand`を商品と照合して明示採用する。
   `99 | No Brand`も独立した選択肢であり、自動fallbackではない。
7. 属性を取得する。合成例の0件は「取得済み0件」で、未取得とは区別する。
8. 「武器・武器形状の画像検査（開発検証）」を開き、「武器画像検査の対象を判定」を押す。
   対象がある場合だけ「対象商品の画像疑義をまとめて確認」を押す。
   商品ごとの欄から同じ対象判定・武器画像検査を行うこともできる。
   対象外と検査完了・疑義なしでは追加の人間確認は不要。武器疑義あり・判断不能だけ画像を確認し、
   画像確認のチェックと判断の根拠を入力して「画像の人間判断を記録」を押す。説明の確認チェックはない。
9. 開発用の出品準備候補CSV / TXTを取得する。全件 `listing_ready=FALSE`。
   合成例・画像AIの疑義なし結果は商品全体の安全保証ではない。

新しい確認環境ごとに `outputs/sg-candidate/<実行識別子>/candidate.sqlite3`を作る。
既存DBの上書き・複製・移行を行わない。再生資料の変更・削除・再初期化は、
表示結果・確認記録・確認チェックを破棄する。確認環境を開き直すとcatalogの取込も必要。
通常の画面再描画だけではAPI問い合わせも確認資料の自動採用も行わない。

## 再生接続の契約

`SG_OFFLINE_REPLAY_V2`は末端全件比較方式を明示選択する形式。
合成確認には同じfixtureフォルダの`replay_leaf_v2.json`を使用できる。
商品CSV・catalog・商品説明・画像等の他の合成資料と手順はV1例と共通。
同じ資料構造で各Category回答へ`product_understood` booleanを追加し、
回答の`prompt_version`は`CATEGORY_LEAF_SEARCH_V2`とする。欠落は停止する。
選んだ大分類の専用末端全件を最大80件ずつ比較し、該当なしなら関連する別大分類を探索する。
最大3大分類の上限へ達した場合は探索完了とせず保留する。専用候補があればOthersを比較しない。
商品理解・関連分類の探索完了が成立した場合だけ、親pathの適合するOthersを候補にできる。
結果は人間の採用を必要とし、Safety・Brand・SLSや準備完了条件を解除しない。
実APIのV2確認は`scripts/sg_category_diagnostic.py --leaf-search --execute-live`の
明示CLIと別のOwner API承認だけで実行し、通常画面からは接続しない。

`SG_OFFLINE_REPLAY_V1`はSGのshop ID、Catalog raw response、Category予測、
画像素材・画像API raw responseを持つ開発用形式。API tokenを含めない。
最大10MB、重複key・市場不一致・不正画像URLを拒否する。
BrandはCategory / offset / shop、AttributeはCategory / shop、Category AIは商品・
候補catalog・request profile、画像AIは同じrequest payloadへ結合する。
対応する応答がなければ失敗し、ネットワークや架空のNo Brandにfallbackしない。
既存のCatalog・Category AI・PH画像transportの検証をそのまま通す。
画像素材は再生資料としてsession内に保持するが、画像評価結果やDBには保存しない。
アップロード資料の真正性や現在のserver内容は証明しない。

## 今回の到達点と次の境界

| 項目 | ローカルで確認できる状態 | 正式利用に残る事項 |
| --- | --- | --- |
| 操作・Category AI | 同じ順序、候補提示、人間採用、グループ確認 | SG実API・実商品での確認 |
| Brand / 属性 | 当該SG ID、保存・再検証、取得失敗で停止 | SG live取得と通常DBへの採用 |
| 商品資料 | 既存Candidate・説明・未評価画像から読込 | 普段の環境での資料受渡し確認 |
| 画像 | SG対象の選択、明示一括実行、人間確認 | 実接続と実精度・費用の確認 |
| CSV / TXT | PH共通の組立、SG条件の再検証、開発用出力 | SG出口開放の採用・正式出力 |
| 起動 | PHと別の入口・新規隔離DB・合成確認資料 | 通常の起動先切替・既存データ統合 |

SG画像の対象は、現在のSG Gate ELIGIBLE・SAFEとKeepa資料が揃う商品から国別root設定で選ぶ。
PH / SGの初期対象は4 rootとroot不明。その他rootは対象外・AI未実行と表示する（DEC-0123）。
武器画像検査対象の資料不足・既存Safety停止は解除しない。対象外では画像の有無で停止せず、説明・画像の人間確認を要求しない（DEC-0125）。
MY / THの初期設定は同じ共通selectorで使用できるが、市場runtimeと実運用接続は後続工程とする。

## 実環境採用を判断する際の説明

別の少量実接続確認は`scripts/sg_live_smoke.py`を使用する（DEC-0118）。
Ownerの明示承認済み対象だけを最大3商品、新規隔離保存先、OpenAI予約上限1米ドルで扱う。
既存Bridgeをprocess内で指定してAccess Token Sourceから読み取り、認証失敗時はKeepa / OpenAIへ進まない。
シートの共有設定・元管理シート・Refresh Token・通常の認証設定を書き換えない。
このCLIの確認範囲は現在のCategory取得・商品資料・画像・Category AIのtransportであり、
Brand / 属性のlive受入、人間確認を伴う一連操作、正式出力の受入は代替しない。
費用ledgerは問い合わせ前の上限予約であり、実請求額ではない。
結果と未解決事項はGit外Evidence / repo外Task Contextへ保存する。

1. 対象：固定PH Betaを基準にしたSG追加機能。
2. 変更：共通操作・検索・候補表示・資料確認・CSV / TXT組立とSG adapter。
3. 対象外：自動出品、MY / TH実装、新しい禁止ルールの推測。
4. 既存運用：通常PHと通常SGの停止状態を今回維持する。
5. リスク：再生検証では実APIの認証・catalog現況・AI精度・実費を証明しない。
6. 確認済み事項：offline / AppTestの結果はrepo外Task Contextを参照する。
7. 制約：SG operation INACTIVE、正式出口CLOSED、live・移行・起動先変更は未実施。
8. 承認後の意味：少量live検証、正式採用、環境切替は個別の対象と影響を提示して判断する。
9. 戻し方：現在のPH環境を保ち、隔離入口の利用を停止できる。

この説明はformal Owner Acceptance Summaryやmandatory checksを代替しない。


## 承認枠付きの隔離実接続画面

実API確認を承認した後だけ、`-LiveGrantPath`で当該run設定JSONを指定して起動する。
この追加modeの実装・合成test成功を、実API実行または正式採用の承認に読み替えない。
設定は`allowed_asins`（最大3件）、`shop_id`、`bridge_spreadsheet_id`、
`brand_category_ids`（最大3件）、`brand_page_limit`（各最大50）、
`catalog_request_limit`と`attribute_request_limit`（各最大10）、
`openai_limit_usd`（文字列0〜1）、`authorization_ref`（Owner承認の参照）を含む。
API key / Access Tokenは設定JSONへ含めず、既存の認証環境を使う。

「承認枠で隔離した確認環境を開く」はlocal初期化だけ。
「SGの最新カテゴリー一覧を取得」を明示実行した後、通常と同じ商品CSV・確認資料を読み込み、
Category / Brand / 属性 / 安全資料 / 対象商品の武器画像検査 / 開発用CSV・TXTへ進む。
同じgrantは同じrunに結合され、再起動で消費枠を増やさない。記録不正・欠落は停止する。
OpenAI枠0ではAIを実行しない。画像対象の商品は追加承認なしに検査を省略して準備完了にできない。
正式出口は閉じたままで、商品ごとの不足手順と開発用準備の確認完了を表示する。


既存OpenAI設定がprocess環境にない場合は`-ApiEnvPath <既存設定ファイル>`を指定する。
既存Google readerは既に設定された環境を優先し、未設定なら既存のローカルShopee readerを
子processだけで指定する。別の既存readerは`-GoogleCredentialsPath`で指定できる。
キー・tokenをrun設定へ転記せず、credentialファイルやWindowsの恒久設定を書き換えない。
