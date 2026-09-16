# 管理基盤Ver2 Runbook

## 正本

- Git: branch、commit、tree、差分。
- `governance/state.json`: 長寿命の承認済み市場・capability・停止条件。
- `governance/manifest.json`以下: versioned Governance Configとschema。
- repo外Task Context: タスクUUID単位の作業状態。Global Stateは更新しない。
- `docs/DECISION_LOG.md`: 判断理由。
- `docs/PROJECT_ROADMAP.md`: 長期工程。
- `docs/CURRENT_WORK.md`: 再開案内のみ。

`outputs/governance/`はGit管理外の派生出力であり、正本ではありません。

## Trust Anchor

唯一のbootstrap期待値はowner受入済みのrepo外recordです。ローカルは
`%LOCALAPPDATA%\ShopeeGovernance\trust\1296080967.json`、CIは
`GOVERNANCE_TRUST_ANCHOR_JSON`を使用します。repo内の値から生成・上書きせず、
`--expected-repo`等の本番overrideを設けません。欠落はHOLD、不正・競合・identity不一致はHARD_STOPです。

## Task Context

`%LOCALAPPDATA%\ShopeeGovernance\tasks\<repository-id>\<task-uuid>\context.json`へ保存します。
schemaは`governance/schemas/task-context.schema.json`です。追加gateと追加停止条件だけを許し、
既存mandatory gate、Global State、保護capabilityを削除・緩和できません。

## 実行

```powershell
.\scripts\Invoke-GovernanceV2.ps1 -Mode Validate
.\scripts\Update-ContextSnapshot.ps1 -TaskContext <repo外context.json>
.\scripts\Verify-ContextSnapshot.ps1 -Profile local-validation -ContextPath outputs\governance\context.json
```

Pythonは`-PythonPath`、`GOVERNANCE_PYTHON`、PATHの順に解決します。PowerShell 5.1と7で同じPython共通実装を呼びます。
Generatorは観測だけを行い、fetch、checkout、branch、index、Stateを変更しません。Verifierは既存contextを評価し、
Generatorを暗黙実行せず、snapshotを削除しません。

Exit codeは`0=CONTINUE`、`10=HOLD`、`20=HARD_STOP`、`64=usage`、`70=internal`です。

## Evidence

- local Evidenceは一時的で、CIまたはowner証跡へ自動昇格しません。
- CI artifactはworkflow/job/actor/対象commit/resultを照合します。
- 永続Evidence recordは`governance/evidence/<canonical-sha256>.json`です。
- code Evidenceの再利用は日付でなくcommit/tree/config/gate/profile/test plan bindingで決めます。
- legacy migrationは`LEGACY_ACCEPTANCE`とし、実行していないVer2 TESTを捏造しません。
- overrideとOwner Acceptanceはexact target bindingが変われば失効します。

## Formal acceptance

Governance mandatory checksはbranch protectionと独立して評価します。provider欠落、check欠落、pending、
skipped、neutral、古いheadはformal acceptanceを満たしません。mandatory technical gate完了前はOwner Acceptanceを要求しません。

Owner Acceptance Summaryは、採用対象、変更、非対象、既存運用影響、主要リスク、確認済みEvidence、既知制約、
承認後の意味、rollbackの9項目を事業用語で説明します。オーナーへhash、SHA、schema等の技術判断を要求しません。

## Shareable output

## 軽量開発運用v1との互換契約

通常のローカル作業は引き続き小さく可逆に進める。読み取り、ローカル編集、ローカルテスト、
ローカルcommitは、ユーザー変更や秘密情報を上書き・収録しない範囲で実行できる。

操作境界として、有料API、外部書込み、復元不能削除、大幅なscope変更、push、Draft PR、merge、deployは
明示承認を要する。Ver2 GovernanceのHOLD/HARD_STOPはこの境界を緩和しない。

WORK_BRIEFを使う条件は、目的・責務・満足条件・外部操作が複雑で、短い依頼だけでは安全な実装範囲を
固定できない場合に限る。すべての作業開始条件にはしない。

GPTは必須の伝言役または承認者ではない。技術的整合性はVerifier、tests、CI、Codexが検証する。

`context.json/.md`と`verification.json/.md`にはrepo相対path、repository ID、reason codeだけを出します。
絶対path、username、hostname、credential、raw exception、raw command output、認証付きURLを含めません。

## Rollback

targetは`136958a1bf2493983b4413f7d231ee5adbd913bf`です。通常のrevert PR、または後続変更を保持した復旧差分で
Ver2対象pathをpre-Ver2内容へ戻します。force pushとdirty resetは行いません。Ver1へ戻すと既知問題も復帰します。
