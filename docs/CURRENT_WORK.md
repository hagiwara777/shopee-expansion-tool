# CURRENT WORK

この文書は再開案内であり、構造化された現在状態の正本ではありません。長寿命の承認済み状態は
`governance/state.json`、branch・HEAD・差分はGit、タスク固有状態はrepo外Task Contextを参照します。

## 現在状態

- status: `WAITING_APPROVAL`
- work: `管理基盤Ver2 Revision 1 + Revision 2の実装`
- branch: `codex/governance-v2`
- base_formal_main: `136958a1bf2493983b4413f7d231ee5adbd913bf`
- scope: `governance / management scripts / tests / formal documentation only`
- external_operation: `未実施（push、PR、merge、GitHub設定、live APIなし）`

## 再開手順

1. `git status`、`git branch --show-current`、`git log -1 --oneline`を確認する。
2. `governance/state.json`と`governance/manifest.json`を検証する。
3. repo外Trust AnchorとTask Contextを用意し、GeneratorとVerifierを実行する。
4. Owner Acceptanceを要求する前にmandatory technical gateをすべて満たす。

## 次の単一作業

オーナー承認後、現在のlocal commitをpushしてDraft PRを作成する。push、PR、merge、branch protection、
GitHub Actions secret/variable、実OS Trust Anchorの設定は別承認とする。

## 停止条件

- PH Beta運用を停止・変更しない。
- SG Category / Brand / Handoff、MY / TH製品開発へ進まない。
- OpenAI、Keepa、Shopeeその他live APIを実行しない。
- `governance/state.json`へactive task、branch、HEAD、test resultを書かない。
- Task ContextでGlobal Stateまたはmandatory gateを弱めない。
- push / PR / merge / deploy / GitHub設定変更は明示承認まで行わない。

## Rollback

pre-Ver2 formal main `136958a1bf2493983b4413f7d231ee5adbd913bf`のVer2対象pathへ戻すrevert PRを作る。
force pushやdirty worktreeのresetは標準手順にしない。rollback後はVer1の既知問題も復帰する。
