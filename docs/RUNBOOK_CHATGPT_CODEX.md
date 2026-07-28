# 二層運用キット v1

## 目的と適用範囲

ChatGPTとCodexの役割を分け、会話の長期化や貼り先の迷いを減らします。
このRunbookは `AGENTS.md` を置き換えません。矛盾した場合は、Codexの安全規則として
`AGENTS.md` を優先します。

個別の `WORK_BRIEF`、会話ログ、商品データ、認証情報はGitに保存しません。

## 情報の正本

確認したい事実に応じて、次の正本を使います。単一の上下順位で解決しません。

| 確認したい事実 | 正本 |
| --- | --- |
| branch・commit・差分・実ファイル | Git |
| Codexの作業規則・安全制約 | `AGENTS.md` |
| 現在地・次の単一作業・停止条件 | `docs/CURRENT_WORK.md` |
| 承認済み判断と理由 | `docs/DECISION_LOG.md` |
| 中長期の工程順 | `docs/PROJECT_ROADMAP.md` |

`docs/CONTEXT_SNAPSHOT.md` は再生成可能な読み取り用の派生物です。正本として編集・
commitせず、正本と矛盾したときは利用しません。

## 標準フロー

1. ChatGPTが目的、理由、対象外、完了条件を `WORK_BRIEF` に整理する。
2. ユーザーがBriefを指定されたCodexタスクへ渡す。
3. CodexがGit状態と正本を確認し、必要ならPlan Modeで計画を合意してから実装・検証する。
4. Codexが5項目の完了報告を返す。
5. ChatGPTが検収し、必要な判断と次の単一作業を決める。

ChatGPTは何を・なぜ行うかを決めます。Codexは現状確認、Plan、実装、検証、Git確認を
担当します。ユーザーはBriefの受け渡し、結果の戻し、事業判断または実画面の受入を行います。

## タスクの選択

同じ成果・目的、同じmodule、同じbranch / worktree、同じ役割の範囲では、監査・修正・
再テストを同じCodexタスクで継続します。

次のいずれかが変わる場合だけ、新しいCodexタスクを作成します。

- 成果物または目的
- worktreeまたはbranch
- module
- 計画・実装から正式化への役割
- 現在のタスクが重くなり、混乱が発生した場合

貼り先の既存タスク名を確定できない場合は、既存タスクを推測せず新規Codexタスクにします。
完了したタスクは削除せずアーカイブし、ユーザーが今操作する主Codexタスクは原則1件にします。
保留中の実験branchやworktreeは、明示的に保留と分かる状態で残せます。

## Plan Modeを使う条件

読み取り専用の小監査と、原因・変更範囲が明確な軽微修正ではPlan Modeを必須にしません。
ただし、次のいずれかに当てはまる場合は、見た目が軽微でもPlan Modeから始めます。

- 原因不明
- 外部APIを使用する
- Git・CI・認証を変更する
- moduleの責務境界に触れる
- 複数ファイルへ広がる可能性がある

## Gitとworktreeの安全規則

- 着手時に、正式リポジトリ、remote、branch、HEAD、clean / dirtyと適用文書を確認する。
- dirtyなworktreeではbranchを切り替えず、ユーザーの変更を整理・破棄・上書きしない。
- プロダクトコード、テスト、仕様、恒久ルールの変更はfeature branchで行う。
- `CURRENT_WORK.md` だけの小さな状態更新は、対象の現在作業branch、または短命の
  `codex/ops-<topic>` branchで行う。対象branchを確定できない場合は停止して確認する。
- mainへの直接pushは原則行わない。commit・push・mainへの統合は、ユーザーの明示許可が
  ある場合だけ行う。
- force pushは、対象branchと操作について明示許可がある場合を除き行わない。
- commit前に差分、秘密情報、リスク相応の検証を確認する。
- 実験は正式版から分離し、`.env`、実商品CSV、SQLite、出力物をGitへ追加しない。

## Codexの完了報告

以下の5項目だけを、見出し付きで報告します。長いテストログや全コマンドは、失敗・
異常・判断に必要な場合だけ補足します。

## 実施内容

## 検証済み事実

## 未確認事項

## ChatGPT／オーナーに判断してほしいこと

## 次の単一作業

検証済み事実には、Git、テスト、実運用、ユーザー受入のどの根拠かを区別して記載します。

## v1の試行と見直し

最初の3つの適格な作業で、このフローを手作業で試します。各作業の5項目報告をChatGPTで
確認し、次を評価します。

- ユーザーの避けられない操作が原則4回以内
- 貼り先についてユーザーが質問した回数が0回
- marketplace・moduleの混同が0回
- 正本にある事実の再入力が0回
- ユーザーが今操作する主Codexタスクが原則1件

3回の評価前には、Skill、Scheduled task、Control Plane、追加の作業票体系、複数の
ChatGPTプロジェクト、Environment承認、Work IDごとのAPIキーを導入しません。
評価後に実際の摩擦が確認された部分だけを、削る・維持する・最小限にSkill化するか判断します。

## Handoff Contract v1

### FORMALとEXPLORATION

- EXPLORATION: 一般論、仮説、論点整理。正式提案、KPI、次の単一作業、WORK_BRIEFとして扱わない。
- FORMAL: リポジトリ固有の判断、KPI、成功基準、次の単一作業、WORK_BRIEF、commit・PR・merge判断。
- FORMALにはEvidence Gateを必須とする。GateのないFORMAL提案は無効とする。
- Evidence Gate: PASSは、提案に必要な根拠を確認できたことを示す。実装成功・受入成功は保証しない。

### チャット切替条件

新しいChatGPTチャットへ切り替える前に、次をすべて満たす。

1. `CURRENT_WORK.md` が最新である。
2. 必要な判断を `DECISION_LOG.md` へ追記している。
3. 工程順が変わった場合は `PROJECT_ROADMAP.md` を更新している。
4. Git外成果物の最小索引を `CURRENT_WORK.md` へ記録している。
5. 変更がmainへmerge済みであり、merge後のformal main commitを確定している。
6. 次の単一作業と停止条件を確定している。
7. 次のCodexタスクを既存継続か新規作成か明記している。
8. 古いBriefを失効扱いにしている。

### Codex開始時同期ゲート

新規・継続を問わず、FORMAL Briefの開始時に次を独立確認する。

- fetch後のorigin/main、Briefのformal commit、remote、repo root、branch、HEAD、clean / dirty
- marketplace、module、phase、対象外、Git・APIの許可範囲
- 必要なGit外成果物へのアクセス

不一致なら `BRIEF_GATE: STOP` とする。formal main照合にはlocal mainではなく、fetch後の
origin/mainを使う。

### task dispositionと古いBrief

WORK_BRIEFには必ず `CONTINUE_EXISTING_TASK` または `CREATE_NEW_TASK`、Codexタスク名、
対象worktreeを指定する。formal main commit、CURRENT_WORKのmarketplace・module・phase、
次の単一作業、停止条件、対象worktree、APIまたはGit許可範囲のいずれかが変わったBriefは
自動的に失効する。古いBriefを推測で修正して実行しない。

### Git外成果物

mainにはartifact_id、種別・版、ファイル名、SHA-256、producer taskまたはproducer commit、
受入状態、storage alias、用途だけを記録できる。絶対パス、商品本文、AI回答本文、URL一覧、
ASIN一覧、認証情報、APIキー、個人情報は記録しない。

実物が必要な場合は、非コミットBriefでstorage aliasを絶対パスへ解決するか、ChatGPTへ
再添付する。SHA-256、版、producer、用途が一致し、`OWNER_ACCEPTED`かつ差分がなく、次作業が
記録済み結論だけに依存する場合は再検収を省略できる。生データ判断、未受入、SHA不一致、版変更が
ある場合は再検収する。

### 新チャット標準開始文

「GitHubの最新mainを基準に、AGENTS.md、CURRENT_WORK.md、DECISION_LOG.md、
PROJECT_ROADMAP.md、RUNBOOK_CHATGPT_CODEX.mdを確認し、全体目標、現在地、次の単一作業、
停止条件、Git外成果物索引を報告してください。FORMALな判断またはWORK_BRIEFを作る場合は
Evidence Gateを表示してください。正本を確認できない場合はGITHUB_UNAVAILABLEとして停止してください。」
