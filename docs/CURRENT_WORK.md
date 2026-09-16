# CURRENT WORK

この文書は再開案内であり、構造化された現在状態の正本ではありません。長寿命の承認済み状態は
`governance/state.json`、branch・HEAD・差分・PR・checksはGitHubとGit、タスク固有状態はrepo外Task Contextを参照します。

## 現在状態

- status: `STOP`
- work: `通常開発承認とformal main最終受入を二段階へ分離するGovernance-only正本化`
- scope: `governance / management scripts / tests / formal documentation only`
- external_operation: `Draft PRとCI / checks確認は完了。formal Verifierはbranch protection非依存となったが、bound CI Evidence recordが未投入のためHOLDであり、mergeとOwner Acceptance Summary生成は停止する。`

## 再開手順

1. `git status`、`git branch --show-current`、`git log -1 --oneline`、対象PRとCI / checksを確認する。
2. `governance/state.json`、`governance/manifest.json`、repo外Trust AnchorとTask Contextを検証する。
3. 通常開発承認の目的とscopeから外れていないことを確認し、Draft PRとCI / checksを確認する。formal acceptanceでは、対象head/tree等にbindingしたCI Evidence recordが別途必要である。
4. mandatory technical gateがEvidence recordでPASSとなった後、現在のhead・scope・主要リスク・protected capabilityへの影響にbindingしたOwner Acceptance Summaryを提示して、オーナーの最終承認を得る。

## 次の単一作業

別承認のGovernance作業として、CI結果を対象head/tree・workflow/job・provenanceへbindingしたEvidence recordとして検証・供給する経路を設計する。それまではOwner Acceptance Summaryを生成・要求せず、mergeしない。

## 停止条件

- PH Beta運用を停止・変更しない。
- SG Category / Brand / Handoff、MY / TH製品開発へ進まない。
- OpenAI、Keepa、Shopeeその他live APIを実行しない。
- `governance/state.json`へactive task、branch、HEAD、test resultを書かない。
- Task ContextでGlobal Stateまたはmandatory gateを弱めない。
- 通常開発承認のscope外のpushまたはDraft PR、formal mainへのmerge、deploy、GitHub設定変更、Trust Anchor変更、credential / secret操作、force pushを実行しない。
- Governance VerifierのHOLD / HARD_STOP、Protected Capability Gate、mandatory technical gateを通常開発承認で無効化または迂回しない。
- mandatory CI Evidence recordが不足する間は、Owner Acceptance Summaryを生成・要求せず、formal mainへmergeしない。

## Rollback

このGovernance-only差分は通常のrevert PRで戻す。force pushやdirty worktreeのresetは標準手順にしない。
