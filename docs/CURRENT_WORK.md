# CURRENT WORK

この文書は再開案内であり、構造化された現在状態の正本ではありません。長寿命の承認済み状態は
`governance/state.json`、branch・HEAD・差分・PR・checksはGitHubとGit、タスク固有状態はrepo外Task Contextを参照します。

## 現在状態

- status: `WAITING_OWNER_ACCEPTANCE`
- work: `SLS Shared Battery Fail-Safe v0.1をformal-main候補として成立させる`
- scope: `PH / SG runtime、safety.shared、Prelisting Gate互換、governance、offline tests`
- external_operation: `Draft PR #76を作成済み。mandatory CI Evidenceとread-only reviewを現在headへbindingし、formal mainへのmergeは行わずOwner Acceptanceで停止する。`

## 確認済みの移行根拠

- Community NGのPR #75はGitHub上でmerge済みであり、旧`WAITING_APPROVAL`工程は完了している。
- 2026-09-21以降、SLSで発送するバッテリーを含む全商品は事前登録が必要である。
- SLSで発送可能なBattery分類はUN3481 / PI966 / Section II、UN3481 / PI967 / Section II、UN3091 / PI969 / Section II、UN3091 / PI970 / Section IIに限られ、発送前に分類確認、G-form事前登録、有効なSDS、指定ラベルが必要である。
- 現行Candidate / Keepa / Amazon情報だけでは上記要件を安全に確定できないため、バッテリーを含む、または明確に疑う候補を自動`ELIGIBLE`にしない。

## 再開手順

1. `git status`、`git branch --show-current`、`git log -1 --oneline`、`origin/main`を確認する。
2. `governance/state.json`、`governance/manifest.json`、repo外Trust AnchorとTask Contextを検証する。
3. shared Battery asset、PH / SG runtime接続、`BLOCK > REVIEW > SAFE`、Prelisting Gate非`ELIGIBLE`、fail-closedの差分とtestsを確認する。
4. PH `ph.beta.operation`とSG `sg.safety.baseline`のProtected Capability Gate、全offline tests、Governance Verifierを確認する。
5. Draft PRと最終headへbindingしたmandatory CI Evidenceを確認し、Owner Acceptance Summaryを準備して停止する。

## 次の単一作業

Draft PR #76の現在headにbindingしたmandatory CI Evidence、Governance Verifier、read-only reviewを確認し、すべて成立後もmergeせず、オーナーの明示的なOwner Acceptanceまたは差戻しを待つ。head、tree、scopeが変わった場合は受入前に全bindingを再検証する。

## 停止条件

- 既存のPH Battery BLOCK、SG Battery REVIEW、Community NG、own penalty、SG Safety Baseline、PH Safetyを削除・移管・緩和しない。
- `BLOCK > REVIEW > SAFE`を維持し、既存BLOCKをREVIEWまたはSAFEへ降格しない。
- Candidate schema、Prelisting Gateの公開status / enum、Category IDを変更しない。
- SG Category Mapper / Brand / Handoff、SLS Category Matrix runtime統合、MY / TH / TW / VN製品runtimeへ進まない。
- OpenAI、Keepa、Shopeeその他live API、自動出品、G-form自動提出、SDS自動生成、Battery type AI自動確定を実行しない。
- `governance/state.json`へactive task、branch、HEAD、test resultを書かない。
- Task ContextでGlobal Stateまたはmandatory gateを弱めない。
- formal mainへのmerge、deploy、GitHub設定変更、Trust Anchor変更、credential / secret操作、force pushを実行しない。
- Governance VerifierのHOLD / HARD_STOP、Protected Capability Gate、mandatory technical gateを通常開発承認で無効化または迂回しない。
- mandatory CI Evidence recordが不足する間はOwner Acceptanceを要求せず、formal mainへmergeしない。

## Rollback

SLS Shared Battery Fail-Safe差分は通常のrevert PRで戻す。shared asset、loader、Guardrail接続、governance ownership、testsを同じ変更単位として扱い、既存の市場別Battery ruleはrollback対象に含めない。force pushやdirty worktreeのresetを標準手順にしない。
