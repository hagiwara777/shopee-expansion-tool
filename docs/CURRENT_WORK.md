# CURRENT WORK

この文書は再開案内であり、構造化された現在状態の正本ではありません。長寿命の承認済み状態は
`governance/state.json`、branch・HEAD・差分・PR・checksはGitHubとGit、タスク固有状態はrepo外Task Contextを参照します。

## 現在状態

- status: `FORMAL_MAIN_ACCEPTED`
- completed_work: `SLS Shared Battery Fail-Safe v0.1`
- formal_main: `e6a5f94b33448ee2a8a47f4ed756649790ead60b`
- merged_pr: `#76`
- accepted_head: `c4f507ed4a1efc24a154ff0ac7455769c2e15392`
- owner_acceptance_summary_binding: `d66d9cbff33c6a97e57b4354497c620c36356633e4f413902a3ef7c180c3a869`
- next_task: `SLS Market Category Rules（新規Codexタスクで開始）`

## 正式化済みの状態

- SLS Shared Battery Fail-Safe v0.1はPR #76でformal mainへ統合済みである。
- `guardrails/sls_shared/battery_review_rules.csv`のBattery明示11語を、PH / SG runtimeの共通`REVIEW` signalとして使用する。
- 共有signalはSLS Battery要件を人間確認するまで自動`ELIGIBLE`へ進めないためのもので、禁止確定を意味しない。
- 既存の`BLOCK > REVIEW > SAFE`を維持し、PHのpower bank等の既存BLOCK、SG既存Battery REVIEW、Community NG、own penalty、PH Safety、SG Safety Baselineを緩和しない。
- Candidate schemaとPrelisting Gateの公開status / enumは変更していない。
- UN / PI分類、Battery商品事前登録G-form、有効なSDS、指定ラベルの確認は、引き続き人間作業である。

## 次の単一作業

`SLS Market Category Rules`

今回確認済みのSLS Category Matrixを、Category Mapper後に利用する市場別SLS出品可否の正式データ資産として設計する。次工程はこの正本化作業と分離し、新規Codexタスクで開始する。

次工程で扱う予定の範囲:

- SLS Category Matrixの正式data asset化
- Shopee Unique Category IDをキーとする市場別可否
- `YES` / `NO` / `Shopeeと要確認`の意味とruntime action設計
- Category Mapper後の判定責務
- PH既存Betaとの互換
- SG等の将来runtime再利用

## 次工程の開始境界

- SLS Market Category Rulesのコード実装、data asset作成、runtime接続はこの正本化タスクでは開始しない。
- SG Category Mapper / Brand / Handoffを開始しない。
- MY / TH / TW / VN製品runtimeを開始しない。
- Category IDを推測しない。
- live Shopee / Keepa / OpenAI API、自動出品、Battery type AI確定、G-form自動提出、SDS自動生成を実行しない。
- 次工程ではformal main、正本文書、SLS Category Matrix一次資料を再確認し、設計境界を確定してから実装可否を判断する。

## 再開手順

1. 新規Codexタスクで`git status`、repo root、remote、branch、HEAD、`origin/main`を確認する。
2. `AGENTS.md`、`docs/RUNBOOK_CHATGPT_CODEX.md`、本書、`docs/DECISION_LOG.md`、`docs/PROJECT_ROADMAP.md`、Governance State / Configを読む。
3. formal mainが`e6a5f94b33448ee2a8a47f4ed756649790ead60b`以降で、PR #76の成果を含むことを確認する。
4. SLS Category Matrixのsource identity、列、件数、市場、値域、Shopee Unique Category IDを読み取り専用で監査する。
5. data asset契約、YES / NO / 要確認のaction、Category Mapper後の責務、PH互換、将来市場のdata / runtime分離を設計する。

## Rollback

SLS Shared Battery Fail-Safe v0.1は通常のrevert PRで戻す。shared asset、loader、Guardrail接続、governance ownership、testsを同じ変更単位として扱い、既存の市場別Battery ruleはrollback対象に含めない。force pushやdirty worktreeのresetを標準手順にしない。
