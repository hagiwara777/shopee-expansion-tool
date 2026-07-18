# Browser E2E Test Kit

Browser E2Eは、Git管理する正本fixtureと、Chromeで選ぶためだけの作業用コピーを分ける二層構造です。これにより、Chromeのファイル選択画面で古いCSVや別suiteのCSVを選ぶ事故を防ぎながら、期待値と入力データをコードレビュー・履歴管理できます。

## フォルダの役割

- 正本: `tests/fixtures/browser_e2e/<suite>/<version>/`。入力CSVと `expected.json` をGit管理します。
- Chrome用: WindowsのDocumentsフォルダ配下の `ShopeeE2E\current\input`。`prepare_browser_e2e.ps1` が毎回生成する使い捨てコピーです。ここを正本として手編集しません。
- 出力: WindowsのDocumentsフォルダ配下の `ShopeeE2E\current\output`。Chromeや手順で得た作業中の出力を置く場所です。Gitには追加しません。
- archive: prepare時点の `current\output` と `logs` をWindowsのDocumentsフォルダ配下の `ShopeeE2E\archive\<timestamp>` に移します。

`prelisting_gate/v1` はSG、1ショップ（`SG_E2E_SHOP_1`）、候補4件のローカルfixtureです。外部APIを呼ぶテストではありません。

## 実行前

1. 正式リポジトリ `C:\Users\user\Documents\Codex\shopee-expansion-tool` にいることを確認します。
2. 既存の未コミット変更はそのままにし、E2E出力やDocuments配下の `ShopeeE2E` をGitへ追加しません。
3. Chrome拡張がローカルファイルの選択を許可されていることを確認します。Chromeの拡張機能ページで対象拡張の詳細を開き、必要なファイルURL／ローカルファイルアクセスの許可を有効化してください。拡張側の画面で権限名が異なる場合は、その画面の案内を優先します。

## Chrome用入力の準備

リポジトリ直下で実行します。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\e2e\prepare_browser_e2e.ps1 -Suite prelisting_gate
```

このスクリプトは、最初にfixture契約テストを通し、古い `current\output` と `logs` をarchiveし、入力フォルダを空にしてから正本CSVをコピーします。準備後、Chromeで選択する固定フォルダは次です。

`<Windows Documents>\ShopeeE2E\current\input`

スクリプトはWindowsのDocuments既知フォルダを使うため、OneDriveリダイレクト環境ではその実パスを使います。この環境では `C:\Users\user\OneDrive\ドキュメント\ShopeeE2E\current\input` です。Chromeでは、`READY.txt` に記録された絶対パスを選択してください。

このフォルダには次のCSV 2件だけが存在します。

- `01_candidates_EXPECT_4.csv`
- `02_existing_SG_SHOP_1_EXPECT_1.csv`

`expected.json` と `READY.txt` は `current` 直下にあり、`input` には置かれません。`READY.txt` にsuite、fixture version、ショップ情報、各入力ファイルの絶対パス・行数・SHA-256・期待件数が記録され、成功時だけ生成されます。

## Streamlitの起動と停止

```powershell
powershell -ExecutionPolicy Bypass -File scripts\e2e\start_streamlit_e2e.ps1
```

このスクリプトは正式な `.venv` のPythonで `app.py` を `127.0.0.1:8771`、headlessモードで起動します。既に `/_stcore/health` がHTTP 200かつ `ok` なら二重起動せず、E2E管理対象であることを確認したPIDをDocuments配下の `ShopeeE2E\state\streamlit.pid` に保存します。標準出力・標準エラーはDocuments配下の `ShopeeE2E\logs` に保存されます。

終了は次です。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\e2e\stop_streamlit_e2e.ps1
```

stopスクリプトはPIDファイルに記録されたプロセスだけを対象にし、そのコマンドラインと8771番ポートの所有を確認してから停止します。別のPythonプロセスは終了しません。

## 画面テストの進め方

1. `READY.txt` を開き、suiteが `prelisting_gate`、`shop_label` が `SG_E2E_SHOP_1`、候補4件であることを確認します。
2. Streamlit画面のアップロード操作だけを1ターンとして実施します。候補CSVと既出品CSVを正しい欄へ選び、画面上のファイル名・行数・ショップラベル・事前確認表示を確認します。
3. アップロード確認が完了した後、判定実行は別ターンで行います。アップロードと判定を同時に進めず、確認結果を記録してから実行してください。
4. ダウンロードする監査用CSVはChromeの通常のダウンロード先へ保存します。ダウンロード結果をリポジトリや正本fixtureへコピーしません。

## ダウンロード照合

監査用CSVのファイルまたはダウンロードフォルダを指定します。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\e2e\verify_browser_downloads.ps1 -DownloadPath "$env:USERPROFILE\Downloads\prelisting_gate_audit.csv"
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\e2e\verify_browser_downloads.ps1 -DownloadPath "$env:USERPROFILE\Downloads"
```

フォルダ指定では、4行の監査用CSVを一意に特定できる必要があります。検証はUTF-8 BOM、固定列と列順、行数、ELIGIBLE／REVIEW／EXCLUDE件数、ASIN重複・混入、入力fixtureとの対応、ASINごとの最終判定・Guardrail判定・既出品判定を確認し、差分付きで `PASS` または `FAIL` を出します。

## fixtureを更新するとき

`v1` は上書きしません。入力形式・期待値・判定根拠を変更する必要がある場合は、`tests/fixtures/browser_e2e/prelisting_gate/v2/` を新設し、対応する契約テストを更新・追加します。外部APIを使うE2Eは別suiteに分け、明示承認がある場合だけ実行します。

## トラブルシューティング

- `READY.txt` がない: prepareが途中で失敗しています。エラーを解決してからprepareを再実行します。READYなしの入力フォルダは使いません。
- Chromeに別のCSVが見える: `READY.txt` 記載の `ShopeeE2E\current\input` 以外を選ばず、prepareを再実行します。inputフォルダにはCSV 2件のみが正しい状態です。
- 8771が使用中: startは停止・上書きしません。`streamlit.pid` がある場合はstopスクリプトを使い、PIDがない場合は既存プロセスの所有者を確認します。
- health checkが失敗する: Documents配下の `ShopeeE2E\logs` の直近のstdout／stderrを確認します。
- ダウンロード照合が複数候補で失敗する: Chromeダウンロードフォルダを整理せず、ダウンロードした監査CSVのファイルパスを直接 `-DownloadPath` に指定します。
