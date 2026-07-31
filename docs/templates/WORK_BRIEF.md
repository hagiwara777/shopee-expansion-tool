# WORK BRIEF テンプレート

このファイルは、ChatGPTからCodexへ渡す依頼のテンプレートです。個別のBrief、会話全文、
商品データ、認証情報はこのリポジトリに保存・commitしません。

## ユーザー操作

### Codex側

- プロジェクト:
- 新規タスク / 既存タスク:
- タスク名:
- 対象フォルダ:
- 開始モード:

### 結果の戻し先

- canonical fieldはHandoff Contractに記入する。

### 今回行わない操作

-

貼り先の既存タスク名を確認できない場合は推測せず、`CREATE_NEW_TASK`を指定します。

## Handoff Contract

- task disposition: `CONTINUE_EXISTING_TASK` / `CREATE_NEW_TASK`
- Codexタスク名:
- 対象worktree:
- expected remote:
- formal main commit:
- marketplace:
- module:
- phase:
- GPT chat disposition: CONTINUE_CURRENT_CHAT / CREATE_NEW_CHAT
- result target GPT project:
- result target GPT chat:
- FORMAL_WORK_UNIT_CLOSED: YES / NO
- CHAT_HANDOFF_GATE: PASS / STOP

## Evidence Gate

### 確認済み事実と根拠

| 事実 | 根拠の種類 | 参照先 |
| --- | --- | --- |
|  | Git確認済み / テスト確認済み / ユーザー確認済み |  |

### 未確認事項

-

### Gate判定

- Evidence Gate: `PASS` / `STOP`
- PASSの意味: 提案に必要な根拠を確認できたこと。実装成功・受入成功は保証しない。

### Git外成果物参照

| artifact_id | ファイル名・版 | SHA-256 | 受入状態 | storage alias | 用途 | 実物アクセス要否 |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  | 必要 / 不要 |

絶対パス、商品本文、AI回答本文、URL一覧、ASIN一覧、認証情報、APIキー、個人情報は記録しない。

## 作業契約

### 目的

-

### 理由・優先順位

-

### 対象範囲

-

### 対象外

-

### 完了条件

-

## 許可範囲

| 項目 | 許可内容 |
| --- | --- |
| Git操作 |  |
| 外部API |  |
| APIの目的 |  |
| 最大件数 |  |
| 再試行条件 |  |
| 禁止操作 |  |

## BRIEF_GATE

次のいずれかでは、編集・commit・pushを行わず `BRIEF_GATE: STOP` として読み取り結果だけを報告する。

- formal commit不一致
- remote不一致
- 対象worktree不一致
- dirty状態を安全に扱えない
- marketplace・module・phase不一致
- 必要な成果物へアクセス不能
- API・Git許可が不足
- GPT chat dispositionが許容値以外
- result target GPT projectまたはresult target GPT chatが空欄・未確定
- FORMAL_WORK_UNIT_CLOSEDが許容値以外
- CHAT_HANDOFF_GATEが許容値以外またはSTOP
- CREATE_NEW_CHATなのにresult target GPT chatが未確定
- CREATE_NEW_CHATなのにFORMAL_WORK_UNIT_CLOSEDがNO
- 不正な組合せなのにCHAT_HANDOFF_GATEがPASS
- CHAT_HANDOFF_GATE: STOPなのに編集、commitまたはpushを許可している
- READMEや会話だけでコード仕様を断定している
- 古いBriefが最新CURRENT_WORKと矛盾

## Codexへの依頼

- `AGENTS.md` と適用対象の管理文書を確認してから着手する。
- FORMALな判断またはWORK_BRIEFではEvidence Gateを表示する。GateのないFORMAL提案は無効とする。
- 新規・継続を問わず、fetch後のorigin/main、formal commit、remote、repo root、branch、HEAD、
  clean / dirty、marketplace、module、phase、対象外、Git・API許可、必要なGit外成果物を独立確認する。
- GPT chat disposition、result target GPT project、result target GPT chat、
  FORMAL_WORK_UNIT_CLOSED、CHAT_HANDOFF_GATEも独立確認する。
- 同期ゲートに不一致があれば、古いBriefを推測で修正せず `BRIEF_GATE: STOP` とする。
- 原因不明、外部API、Git・CI・認証、責務境界、複数ファイルへ広がる可能性がある場合は、
  Plan Modeから始める。
- 実装・検証の終了時は、`docs/RUNBOOK_CHATGPT_CODEX.md` の5項目形式で報告する。
