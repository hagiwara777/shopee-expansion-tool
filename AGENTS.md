# Codex Repository Rules

## Repository source of truth

- Treat `hagiwara777/shopee-expansion-tool` and its current clone as the source of truth.
- Do not work in older project or temporary work folders.

## Before making changes

- Identify the files in scope before editing.
- Run these commands at the start of work:

  ```powershell
  git status
  git rev-parse --show-toplevel
  git log -1 --oneline
  ```

- If a task changes behavior or scope, report the proposed differences before editing.

## Codex開始前チェック

作業開始時は、会話履歴だけに依存せず、次を確認してください。

1. 正式リポジトリのルート、remote、現在ブランチ、HEAD、working treeの
   clean / dirty を確認する。
2. この `AGENTS.md` と、適用対象の下位 `AGENTS.md` があれば全文を読む。
3. `docs/CURRENT_WORK.md`、`docs/DECISION_LOG.md`、
   `docs/PROJECT_ROADMAP.md` を読む。利用方法や機能仕様が関係する場合だけ
   `README.md` も読む。
4. ユーザー提示情報、Gitで確認済みの事実、テストで確認済みの事実、
   未確認情報を区別する。推測を確認済み事実として扱わない。
5. 今回の変更対象と変更禁止範囲を特定し、`CURRENT_WORK.md` の現在作業と
   停止条件に反しないことを確認する。
6. 作業票と `CURRENT_WORK.md` の marketplace、module、phase、working branch が
   不一致の場合は、推測で進めず停止する。

安全規則:

- dirtyなworktreeでは、ユーザーの変更や未追跡ファイルを無断で整理、破棄、
  上書きしない。dirtyな状態のまま別ブランチへ切り替えない。
- 正式ブランチ、一時コピー、古いフォルダを推測で判断しない。Gitのルートと
  remoteを確認する。
- 現在の作業、停止条件、次の再開地点は `docs/CURRENT_WORK.md` を正本とする。
- 方針変更の理由は `docs/DECISION_LOG.md` に追記し、長期工程は
  `docs/PROJECT_ROADMAP.md` を正本とする。READMEを現在進捗の正本にしない。
- `CONTEXT_SNAPSHOT` は正本文書とGit状態から生成する派生情報として扱い、単独で
  正本にしない。手動編集・commitを行わない。

## Git and sensitive data

- Do not commit or push unless the user explicitly authorizes it.
- Force push with `--force` or `--force-with-lease` is prohibited by default. Make an exception only when the user explicitly authorizes the target branch and exact operation; do not automatically perform ordinary pushes or formalization beyond the requested scope.
- Never add the following to Git: `.env`, `.env.*`, cache databases, `outputs/`,
  `.venv/`, `__pycache__/`, `.pytest_cache/`, `.pytest_tmp/`, `.agents/`,
  `.codex/`, or `work/`.
- Do not hard-code API keys, tokens, or passwords in source code, README files, or tests.

## FORMAL作業単位とGPTチャット切替

- FORMAL work unitは、同じ目的の設計、実装、修正、検証、技術検収、PR、main統合、
  統合後確認までを一つにした作業単位とする。
- PR-backed FORMAL work unit（PRを伴うFORMAL作業）は、Git管理対象の変更を成果とする作業とする。次の3条件がすべて
  成立した時点だけを、PRを伴うFORMAL作業の正式な閉鎖とする。
  1. 対象PRがmainへ統合済みである。
  2. ChatGPTが統合後のformal main commitをGitHubから直接確認済みである。
  3. docs/CURRENT_WORK.mdが統合後の現在地と次の単一作業へ更新済みである。
- no-PR FORMAL work unit（PRを伴わないFORMAL作業）は、読み取り専用監査、BRIEF_GATE: STOP、EVIDENCE_PACKAGE: STOP、
  Git変更を成果としない技術検収、またはGit外成果物だけの正式検収とする。読み取り専用作業の
  ために空commitまたは形式だけのPRを作成しない。次の3条件がすべて成立した時点だけを、
  PRを伴わないFORMAL作業の正式な閉鎖とする。
  1. ChatGPTが対象作業の基準となるformal main commitをGitHubから直接確認済みである。
  2. ChatGPTが読み取り専用結果またはSTOP結果を、完了した正式な技術結果として受入済みである。
  3. docs/CURRENT_WORK.mdが作業後の現在地と次の単一作業へ更新済みである。実作業の状態、
     次の単一作業、停止条件に変化がなく更新不要な場合は、ChatGPTによる
     CURRENT_WORK更新不要時の正式確認をこの条件の代替とする。
- PRを伴うFORMAL作業、PRを伴わないFORMAL作業のどちらも、実装、修正、検収、PR、merge、
  統合後確認または結果受入の途中では、GPTチャットを
  切り替えない。3条件の成立後、次のFORMAL作業を開始する前に新しいGPTチャットへ切り替える。
- チャットの長さ、体感的な重さ、日付変更、module変更、新しいCodexタスクの作成だけでは、
  GPTチャットを切り替えない。
- 現在のGPTチャットで作業不能となる技術的障害がある場合だけ、例外的な途中切替を許可する。
  この例外はFORMAL作業単位の閉鎖を意味せず、同じ作業を新しい現在チャットで継続する。
- WORK_BRIEFでは次のcanonical fieldをすべて確認する。
  - GPT chat disposition: CONTINUE_CURRENT_CHAT / CREATE_NEW_CHAT
  - result target GPT project:
  - result target GPT chat:
  - FORMAL_WORK_UNIT_CLOSED: YES / NO
  - CHAT_HANDOFF_GATE: PASS / STOP
- canonical fieldの欠落、空欄、不正値、矛盾する組合せ、またはCHAT_HANDOFF_GATE: STOPを
  検出した場合、Codexは編集、commit、pushを行わずBRIEF_GATE: STOPとして読み取り結果だけを
  報告する。GPTチャット切替とCodexタスク切替は別の判断として扱う。

## Validation

- Run `pytest` after changes whenever practical.
- Use the real Keepa API only when the user explicitly authorizes that verification.

## 作業終了・handoff

- 実作業の状態が変わった場合だけ `docs/CURRENT_WORK.md` を更新する。
- 重要判断が変わった場合だけ `docs/DECISION_LOG.md` に新しいIDで追記する。
  既存エントリは書き換えない。
- 工程順や長期方針が変わった場合だけ `docs/PROJECT_ROADMAP.md` を更新する。
  同じ内容を複数文書へ詳細に複製しない。
- 実行していないテストを成功扱いしない。モックテスト、実API確認、実データ確認、
  ユーザー受入確認を区別する。
- 未完了事項、次の単一作業、停止条件を明確に残す。
- 管理文書に `.env`、APIキー、認証情報、商品CSV本文、個人情報を含めない。
- `CURRENT_WORK.md` または `DECISION_LOG.md` を更新した場合は、
  `scripts/Update-ContextSnapshot.ps1` でsnapshotを再生成する。生成に失敗した場合は
  作業完了扱いにしない。
- commit前に変更ファイル、未追跡ファイル、秘密情報の混入を確認する。
  commit・pushの許可がない場合は実行しない。

## Component boundaries

- Keep Product Finder, Guardrail, and ASIN Resolver responsibilities separate.
- Do not combine or extend their responsibilities without an approved scope change.

## Browser E2E

- Keep versioned source fixtures under `tests/fixtures/browser_e2e`.
- Generate Chrome-operation files only under `Documents\ShopeeE2E`; do not hand-edit them as source fixtures.
- Treat upload confirmation and decision execution as separate steps.
- Run E2E suites that use external APIs only with explicit approval.
- Never add downloaded E2E outputs to Git.
