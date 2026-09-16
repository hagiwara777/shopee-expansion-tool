# CURRENT WORK

この文書は再開案内であり、構造化された現在状態の正本ではありません。長寿命の承認済み状態は
`governance/state.json`、branch・HEAD・差分・PR・checksはGitHubとGit、タスク固有状態はrepo外Task Contextを参照します。

## 現在状態

- status: `WAITING_APPROVAL`
- work: `通常開発承認とformal main最終受入を二段階へ分離するGovernance-only正本化`
- scope: `governance / management scripts / tests / formal documentation only`
- external_operation: `Draft PRとCI / checks確認は完了。formal mainへのmergeは未実施で、現在対象にbindingした最終Owner Acceptanceとmandatory technical gateを要する。`

## 再開手順

1. `git status`、`git branch --show-current`、`git log -1 --oneline`、対象PRとCI / checksを確認する。
2. `governance/state.json`、`governance/manifest.json`、repo外Trust AnchorとTask Contextを検証する。
3. 通常開発承認の目的とscopeから外れていないことを確認し、Draft PRとCI / checksをEvidenceとして確認する。
4. formal mainへのmerge前にmandatory technical gateを満たし、現在のhead・scope・主要リスク・protected capabilityへの影響にbindingしたOwner Acceptance Summaryを提示して、オーナーの最終承認を得る。

## 次の単一作業

現在のDraft PR headとCI / checksのEvidenceを添えて、オーナーへformal main採用可否のOwner Acceptance Summaryを提示する。最終承認が得られるまでmergeしない。

## 停止条件

- PH Beta運用を停止・変更しない。
- SG Category / Brand / Handoff、MY / TH製品開発へ進まない。
- OpenAI、Keepa、Shopeeその他live APIを実行しない。
- `governance/state.json`へactive task、branch、HEAD、test resultを書かない。
- Task ContextでGlobal Stateまたはmandatory gateを弱めない。
- 通常開発承認のscope外のpushまたはDraft PR、formal mainへのmerge、deploy、GitHub設定変更、Trust Anchor変更、credential / secret操作、force pushを実行しない。
- Governance VerifierのHOLD / HARD_STOP、Protected Capability Gate、mandatory technical gateを通常開発承認で無効化または迂回しない。

## Rollback

このGovernance-only差分は通常のrevert PRで戻す。force pushやdirty worktreeのresetは標準手順にしない。
