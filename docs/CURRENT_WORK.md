# CURRENT WORK

この文書は再開案内であり、構造化された現在状態の正本ではありません。長寿命の承認済み状態は
`governance/state.json`、branch・HEAD・差分・PR・checksはGitHubとGit、タスク固有状態はrepo外Task Contextを参照します。

## 現在状態

- status: `WAITING_APPROVAL`
- work: `Community NG ASIN / ブランドを国別共通Safety資産として正本化する`
- scope: `SG / PH runtime、MY / TH / TW / VN data-only資産、shared safety / SG rules / gate / governance / tests`
- external_operation: `Draft PR #75とCI / checks確認は完了。最終headへbindingした6 mandatory CI EvidenceがPASSし、Owner Acceptance Summaryを準備済み。formal main採用の最終承認を待つ。`

## 再開手順

1. `git status`、`git branch --show-current`、`git log -1 --oneline`、対象PRとCI / checksを確認する。
2. `governance/state.json`、`governance/manifest.json`、repo外Trust AnchorとTask Contextを検証する。
3. Draft PR #75のhead、全check、6 mandatory CI Evidenceが同じhead / treeへbindingしていることを確認する。
4. Community NG資産件数、市場境界、既存Safety保護、主要リスクを含むOwner Acceptance Summaryを確認し、オーナーのformal main採用判断を得る。

## 次の単一作業

Draft PR #75の最終head、bound CI Evidence、Owner Acceptance Summaryを添えて、オーナーのformal main採用可否を待つ。最終承認が得られるまでmergeしない。

## 停止条件

- PH Beta運用を停止・変更しない。
- SG Category / Brand / Handoff、MY / TH / TW / VN製品runtime開発へ進まない。
- OpenAI、Keepa、Shopeeその他live APIを実行しない。
- `governance/state.json`へactive task、branch、HEAD、test resultを書かない。
- Task ContextでGlobal Stateまたはmandatory gateを弱めない。
- 承認済みCommunity NG scope外の変更、formal mainへのmerge、deploy、GitHub設定変更、Trust Anchor変更、credential / secret操作、force pushを実行しない。
- Governance VerifierのHOLD / HARD_STOP、Protected Capability Gate、mandatory technical gateを通常開発承認で無効化または迂回しない。
- mandatory CI Evidence recordが不足する間は、Owner Acceptance Summaryを生成・要求せず、formal mainへmergeしない。

## Rollback

このCommunity NG差分は通常のrevert PRで戻す。revert時は共通資産loader、資産、旧辞書移管、Evidence workflowを同じ変更単位として扱い、force pushやdirty worktreeのresetを標準手順にしない。
