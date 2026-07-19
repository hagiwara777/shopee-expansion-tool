# 変更検証ループ Ver1

`scripts/verify_change.ps1` は、機能実装後の技術検証を同じ順序で実行するための入口です。商品選定、Guardrail 判定、Expansion、Resolver、外部API、Shopee上での事業判断は検証しません。自動テストの結果と、実商品・事業上の妥当性を混同しないでください。

検証レポートはリポジトリ外の Temp に UTF-8 で保存されます。レポートには fixture のローカル絶対パス、CSV内容、認証情報を記録しません。

## 前提

- 正式リポジトリのルートから実行する。
- リポジトリの `.venv` が存在する。
- 外部APIは呼ばない。Browser E2E は Git 管理済みの合成 fixture だけを使う。
- `scripts/e2e` と `tests/fixtures/browser_e2e` を正本とし、Chrome操作用の `ShopeeE2E` 作業コピーを直接編集しない。

開始時と終了時に Git 状態をレポートします。未コミット変更の有無は監査対象であり、それだけを失敗理由にはしません。`git diff --check`、追跡対象の不要生成物、追加差分中の明白な秘密情報パターンは失敗にします。

## 実行方法

PowerShell から、リポジトリの `.venv` を使う既存スクリプトとして実行します。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_change.ps1 -Mode Quick
```

Quick は、指定対象テスト、Python/PowerShell構文、`git diff --check`、変更ファイル・秘密情報監査を実行します。既定の対象テストは今回の検証ループ契約、Browser fixture契約、Streamlit AppTestです。機能に応じて対象テストを追加または置換できます。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_change.ps1 -Mode Quick `
  -TargetTest tests\test_prelisting_gate.py,tests\test_prelisting_gate_csv.py
```

Full は完全非対話です。Quick に加え、fixture契約、全回帰、Streamlit AppTest、既存 `start_streamlit_e2e.ps1` を使う health/root HTTP 200 スモーク、専用プロセスの停止を実行します。Computer Use、CSVアップロード、Chromeダウンロード、ユーザー入力を待ちません。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_change.ps1 -Mode Full
```

Python構文検査は `scripts/check_python_syntax.py` を使います。ソースをメモリ内で `compile` するだけなので、`compileall` や `py_compile` と異なり `pyc` を作りません。PowerShell構文検査は `Parser.ParseFile` だけを使い、対象スクリプトを実行しません。

各外部プロセスは専用の上限時間を持ちます。標準出力・標準エラーとステージごとの開始時刻、終了時刻、所要時間、終了コード、PASS / FAIL / SKIPPED はリポジトリ外のTempに保存します。タイムアウト時は対象プロセスを停止してFAILに記録し、既存の `stop_streamlit_e2e.ps1` によるPID・ポート清掃を続けてから統合レポートを出力します。

## Browser E2E

PowerShell は Computer Use を実行しません。Computer Useに接続できないことをアプリ不具合と断定しないためです。Browser モードは既存の Browser E2E Kit を使い、次の二段階で Codex/操作担当へ明示的に引き継ぎます。

### 1. 準備

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_change.ps1 -Mode Browser `
  -BrowserStage Prepare -FixtureVersion v2
```

これは Full 検証を実行した後に、既存の `prepare_browser_e2e.ps1` で PH v2（または SG v1）の合成CSVを準備し、既存の `start_streamlit_e2e.ps1` で専用ポートを起動して health/root を確認します。成功時は E2E-managed Streamlit プロセスを残し、URL、PID、`READY.txt` の入力パスと期待値を出力して `BROWSER_READY` としてCodexエージェントへ制御を返します。PowerShellは操作完了を待ちません。

スクリプトが示した同じ `-ReportPath` を控えます。`READY.txt` にある固定の Chrome 用入力フォルダ以外のCSVを選んではいけません。

### 2. Computer Useでの実画面操作

操作担当は既存の [Browser E2E Test Kit](browser_e2e.md) に従い、次を別々の確認として実施します。

1. `READY.txt` の marketplace、shop label、候補件数を確認する。v1 は SG / 4件、v2 は PH / 3件。
2. 候補CSVと既出品CSVをアップロードし、ファイル名、行数、ショップラベル、入力準備表示を確認する。このアップロード確認と実行ボタン押下は同じ操作にしない。
3. 「出品前チェックを実行」を押し、例外表示がなく、fixtureの `expected.json` に一致する件数を確認する。v2 は ELIGIBLE=1、REVIEW=1、EXCLUDE=1。
4. 「全件監査CSVをダウンロード」を押す。ダウンロード先はリポジトリ外にする。
5. 既出品CSVまたはショップ数を意図的に不整合にして再実行し、前回の結果とダウンロード操作が残らず、入力エラー表示になることを確認する。これが stale 結果の確認である。
6. Chrome DevTools の Console にアプリ起因の error がないことを確認する。Computer Use接続初期化に失敗した場合はここで停止し、`BROWSER_UNAVAILABLE` として報告する。推測でアプリコードを変更しない。

### 3. ダウンロード照合と清掃

ダウンロードした監査CSVの完全なパスを渡します。`-BrowserUiChecksPassed` は上の実画面観察を完了した場合だけ付けます。`-RemoveDownloadedCsv` は照合成功後に、その指定された合成監査CSVだけを削除します。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_change.ps1 -Mode Browser `
  -BrowserStage Verify `
  -ReportPath '<準備時に表示されたTempのレポート>' `
  -DownloadPath '<ダウンロードした監査CSV>' `
  -BrowserUiChecksPassed `
  -RemoveDownloadedCsv
```

この段階は既存の `verify_browser_downloads.ps1` に委譲し、`expected.json` と監査CSVのファイル名、BOM、列順、件数、ASIN、判定、reason code、既出品根拠を照合します。その後、既存の `stop_streamlit_e2e.ps1` が PID とポート所有を確認してから専用プロセスを停止します。他のPythonプロセスは停止しません。

単発で次を実行すると、準備後に操作待ちとして `BROWSER_UNAVAILABLE` を記録し、専用プロセスを清掃します。実画面操作は実施されません。Computer Useの初期化・接続に失敗した場合も、Codexエージェントは `BROWSER_UNAVAILABLE` としてこの清掃経路を使い、アプリ不具合とは断定しません。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_change.ps1 -Mode Browser
```

## レポートと判定

すべてのモードで以下の章を固定順に出力します。

- 総合判定（`PASS` / `CONDITIONAL_PASS` / `FAIL` / `BROWSER_UNAVAILABLE`）
- Git開始状態、変更ファイル、対象テスト、全回帰、構文・diff検査、セキュリティ監査
- AppTest、Browser E2E、ダウンロードCSV検証、清掃結果、未確認事項、Git終了状態

`BROWSER_UNAVAILABLE` は Browser接続・操作が未実施または利用不能であることを表すだけです。AppTest、HTTP、fixture契約、ダウンロードCSV照合の結果とは分けて読みます。`CONDITIONAL_PASS` は、選択しなかったモードまたは操作担当の目視確認など、技術的な失敗ではない未確認事項が残る状態です。

## 自動修正ループと停止条件

本スクリプトの失敗が検証ループ自身の明白な不具合（テスト対象の指定、構文、レポート、fixture参照、清掃）であり、許可範囲内なら修正して再実行できます。今回の作業では最大2回までです。

次の場合は変更を増やさず停止します。

- 商品機能、Guardrail、Expansion、Resolver、UI本体、fixture契約の変更が必要
- 実API、実商品CSV、実顧客データ、Shopee上の実データが必要
- Computer Use基盤の不在をアプリ不具合として扱う必要がある
- 許可範囲外の変更または大規模リファクタリングが必要
- 2回の限定修正後も green にならない

検証ループは Skill ではありません。将来、実行結果と手順が安定してから、リポジトリに管理可能なSkill形式が明確な環境でのみ Skill 化を検討してください。
