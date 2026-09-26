# 管理基盤Ver2 Runbook

毎タスクのmandatory原則は[AGENTS.md](../AGENTS.md)、本書はその詳細手順とする。
AGENTSが指定する実行時点で該当節を必ず読み、適用する。参照化で手順・承認・gateを任意化しない。
DEC-0087に基づく配置とDEC-0088のDecision読込手順を適用し、DEC-0072 / DEC-0073の管理・承認契約を変更しない。

## 正本

- Git: branch、commit、tree、差分。
- `governance/state.json`: 長寿命の承認済み市場・capability・停止条件。
- `governance/manifest.json`以下: versioned Governance Configとschema。
- repo外Task Context: タスクUUID単位の作業状態。Global Stateは更新しない。
- `docs/DECISION_LOG.md`: 完全な判断履歴のappend-only正本。過去DECを削除・分割・書換えしない。
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

## 開始・実行

開始時は正式repoのroot、remote、branch、HEAD、main、origin/main、clean / dirtyを観測する。
AGENTSと適用下位AGENTSを全文読み、CURRENT_WORK、PROJECT_ROADMAPを読む。
DECISION_LOGは次節「Decision読込」の手順で選択して本文を読み、
利用方法・機能仕様に関係する場合だけREADMEも読む。CURRENT_WORKは再開案内であり、
branch / HEAD / tree / 差分はGit、タスク固有状態はTask Contextと照合する。
作業票のmarketplace / module / phase / 作業対象と食い違う場合は、推測で進めない。

開始時に次のValidateとsnapshot生成を実行する。CURRENT_WORKまたはDECISION_LOG更新後も
snapshotを再生成し、対象作業のprofileで検証する。生成・検証の失敗を完了扱いにしない。
local-validationの例は次のとおり。必要なEvidenceを「Evidence」に従って渡す。

```powershell
.\scripts\Invoke-GovernanceV2.ps1 -Mode Validate
.\scripts\Update-ContextSnapshot.ps1 -TaskContext <repo外context.json>
.\scripts\Verify-ContextSnapshot.ps1 -Profile local-validation -ContextPath outputs\governance\context.json
```

Pythonは`-PythonPath`、`GOVERNANCE_PYTHON`、PATHの順に解決します。PowerShell 5.1と7で同じPython共通実装を呼びます。
Generatorは観測だけを行い、fetch、checkout、branch、index、Stateを変更しません。Verifierは既存contextを評価し、
Generatorを暗黙実行せず、snapshotを削除しません。Generatorはoptional観測不足だけで失敗させません。
派生出力は既定のGit管理外 `outputs/governance/` に生成します。手編集・commitはしません。

Exit codeは`0=CONTINUE`、`10=HOLD`、`20=HARD_STOP`、`64=usage`、`70=internal`です。

## Decision読込

通常タスクでDECISION_LOG全文の再読込は必須にしない。次の順で必要な判断根拠を確認する。
これは読込方法の変更であり、未読DECの制約失効、作業許可、承認・Governance gateの代替を意味しない。

1. AGENTS / 適用下位AGENTS、CURRENT_WORK、PROJECT_ROADMAPから今回のmarketplace / module / phase、対象・禁止範囲を確認する。
2. `rg "^## DEC-" docs/DECISION_LOG.md` で全Decision見出し一覧を確認する。Required Decisionsにない関連候補も拾う。見出しだけで判断内容・有効性を確定しない。
3. CURRENT_WORKのRequired Decisionsに列挙された各DECの本文全体（当該見出しから次のDEC見出し直前まで、末尾DECはEOFまで）を読む。途中省略・出力切捨てがあれば分割して読み切る。
4. 見出し一覧から今回のmarketplace / module / phase、変更対象・禁止範囲に直接関係するDECを追加で読む。選択した本文の根拠・前提・置換元として必要な参照DECも読む。選択IDを本文全体から検索し、そのIDを参照する後続DECも確認する。数字の新しさだけで旧決定全体が失効したと推測せず、置換された範囲を確認する。
5. 判断根拠が不足、競合・置換関係が不明、shared core / Governance / approval boundaryに影響、またはRequired Decisionsの漏れが疑われる場合は、本文全体を対象に関連語・IDで検索範囲を広げ、ヒットしたDECを全文読む。Required Decisionsの欠落・空欄・存在しないID、見出しだけでは関連性が判断できない場合も同じ扱いとする。Governance・承認に関係する場合はDEC-0072 / DEC-0073と関連する後続DECを必ず確認する。
6. 検索・参照追跡後も必要な根拠と適用範囲を判断できない場合だけDECISION_LOG全文を読む。それでも矛盾・承認・停止条件を解消できなければ、依存する作業を停止し、不明点を報告する。全文読込自体を許可の根拠にしない。

たとえば `rg -n -C 2 'DEC-0087|読込|正本|承認|Governance' docs/DECISION_LOG.md` は候補発見用であり、検索結果の数行だけで本文確認を済ませない。`rg`が使えない場合はPowerShellの`Select-String`等で同じ検索を行う。
選択ID、追加検索した理由、解消した置換関係または未解決事項を作業報告かrepo外Task Contextへ短く残す。新しい必須台帳は作らない。

Required Decisionsは現在の単一作業に必要なIDと短い参照理由だけの再開案内とし、本文の複製、全履歴index、承認状態の正本にしない。
現在の単一作業・scope・phaseの変更時と終了・handoff時に見出し一覧と照合して更新する。欠落を発見した場合は根拠DECを確認して補正する。
新しい手動巨大indexは作らない。派生indexが必要になった場合も見出しから再生成可能な非正本に限り、DECISION_LOG本文との照合を省略しない。

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

## 軽量開発運用v1との互換契約

通常のローカル作業は小さく可逆に進める。通常開発承認の対象操作、別承認の操作、
formal mainへのmerge条件はAGENTS「軽量開発運用 v1・承認境界」を適用する。
push / Draft PRは検証可能な候補の公開であり、formal mainへの採用承認ではない。
GateのHOLD / HARD_STOPを承認範囲の拡大で回避しない。

Ownerは作りたいもの、理由、利用方法、満足条件、避けたい結果を事業用語で示す。
CodexはGit・正本の実測、曖昧な要望の具体化、技術設計、local編集、tests、平易な完了報告を担い、
Ownerへ技術方式、branch、テスト方式の選択を求めない。
GPTは必須の伝言役または承認者ではない。技術的整合性はVerifier、tests、CI、Codexが検証する。

WORK_BRIEFを使う条件は、目的が曖昧、複数module、責務変更、外部API、費用、データ移行、
復元不能操作等を伴い、短い依頼だけでは安全な実装範囲を固定できない場合とする。
`docs/templates/WORK_BRIEF.md`を使用し、すべての作業開始条件にはしない。
pushまたはPRだけを理由に必須化しない。project名、chat名、worktree絶対pathを安全gateにしない。

## タスク境界・正本化

同じ原因・同じ受入条件の問題は同じCodexタスクを継続できる。次の場合は分割の候補とする。

- 独立した問題が解決し、次の独立問題へ移る。
- 実装目的、受入条件、module、責務が変わる。
- 修正・テストの反復で会話、log、diffが大きく蓄積した。
- 同じ調査、ファイル読込、説明を繰り返し始めた。
- Context Compaction等が発生し、長大なタスクになった。

同一問題で修正・テストの反復が3回程度を超えたら、機械的に終了せず、
タスク分割または原因分析への立返りを一度見直す。

基本順序は `実装・修正 → テスト → 結果確認 → 正本化 → 前タスク終了 → handoff → 新規タスク開始`。
終了・handoff時は今回の変更範囲に応じて次を実施する。

1. 採用するコード・設定・テストを確定する。
2. 対象testと必要な回帰testの結果を確認する。mock、実API、実データ、Owner受入を分ける。
3. `git status`とdiffで、無関係な変更、未追跡ファイル、secret混入がないか確認する。
4. 実作業状態が変わった場合はCURRENT_WORKを更新する。Required Decisionsも「Decision読込」に従い見出し一覧と照合する。
5. 恒久判断が変わった場合だけDECISION_LOGへ新IDで追記し、既存entryを書き換えない。
6. 長期工程・順序が変わる場合だけPROJECT_ROADMAPを更新する。
7. 恒久ルールが変わる場合だけAGENTS等を更新する。詳細を複数文書に複製しない。
8. 正本文書更新時は必要なsnapshotを再生成する。CURRENT_WORKまたはDECISION_LOG更新時は必須。
   「開始・実行」に従い検証し、生成失敗・未解決の検証失敗を完了扱いにしない。
9. 関連検証、変更ファイル、未追跡ファイル、secret確認後、検証済み範囲だけlocal commitする。
   push / Draft PRは通常開発承認のscope内、merge / deployは別の承認規則に従う。

次のタスクが過去会話を読まずに正式状態、確認済み事項、未解決事項、次の単一作業と停止条件を
判断できることを完了条件とする。テスト失敗、無関係なdirty変更、snapshot生成失敗、正本矛盾で
正本化できない場合は阻害要因を示して停止する。handoff自体は正本の代替にしない。
handoffには完了内容、確認済みtests、未解決事項、次タスクの目的、最初に読む正本fileまたはcommitを記載する。

## Browser E2E

- versioned source fixtureは `tests/fixtures/browser_e2e` に保存する。
- Chrome操作用ファイルは `Documents\ShopeeE2E` のみに生成し、source fixtureとして手編集しない。
- upload確認とdecision実行は別段階として扱う。
- 外部APIを使うsuiteは明示承認なしに実行しない。
- ダウンロードしたE2E出力をGitへ追加しない。

## Shareable output

`context.json/.md`と`verification.json/.md`にはrepo相対path、repository ID、reason codeだけを出します。
絶対path、username、hostname、credential、raw exception、raw command output、認証付きURLを含めません。

## Rollback

targetは`136958a1bf2493983b4413f7d231ee5adbd913bf`です。通常のrevert PR、または後続変更を保持した復旧差分で
Ver2対象pathをpre-Ver2内容へ戻します。force pushとdirty resetは行いません。Ver1へ戻すと既知問題も復帰します。
