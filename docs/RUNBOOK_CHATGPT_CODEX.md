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

### PR authorとOwnerが同一の場合のGitHub Owner証跡

GitHubはPR author自身のApprove reviewを受け付けない。OwnerのPR Conversationコメントを正式な
`GITHUB_OWNER` Evidenceとして扱う場合は、repo外Trust Anchor v1.1.0の
`owner_evidence_public_key`と、それに対応するProvider専用Ed25519秘密鍵を先にOwner管理下で設定する。
公開鍵をrepo内の自己申告から採用しない。秘密鍵をGit、Task Context、ログ、Evidence、コマンド引数へ
書き出さない。鍵未設定・不一致ならHOLDとし、手製JSONや旧形式のOwner Evidenceで代替しない。

technical gates完了後、Owner Acceptance Summaryを生成し、Ownerへ9項目と対象PR・事業scopeを提示して
`WAITING_APPROVAL`で停止する。Ownerが現在対象のformal main採用を明示的に最終承認した場合だけ、
Codexは承認された一行の事業scopeと現在のPR・head・Verify・Summaryから次のコメントを決定論的に生成・投稿する。
OwnerへSHA・hash・bindingのコピーを要求しない。Owner silence、CI PASS、Codex判断、Summary生成だけでは承認しない。
コメントは承認後のmachine-readable target binding / transport Evidenceであり、Owner本人によるGitHub UI手入力の
独立証明ではない。CodexがOwner GitHub認証で投稿できる環境では、その区別をGitHub APIから証明できない。
これは既存Trustモデルの限界として明示し、独立human-origin proofは別Security工程とする。

`SCOPE`はOwnerが承認した事業範囲を一行で固定する。head、verification input、Summary binding、scope、
主要リスク、protected capabilityへの影響のいずれかが変われば、現在対象のSummaryを再提示して再承認を得る。
以下の値は例であり、実際は現在の値を使う。

```text
OWNER_ACCEPTANCE: APPROVED
PR: #<number>
HEAD: <full 40-character SHA>
VERIFICATION_INPUT_HASH: <current verification input hash>
SUMMARY_BINDING: <current Owner Acceptance Summary binding>
SCOPE: <approved scope>
```

明示承認後、現在のSummaryを渡したformal-acceptance technical Verifyが`owner_acceptance_ready=true`、
停止理由が`OWNER_ACCEPTANCE_REQUIRED`だけであることを確認する。formal mainへ正式採用済みのhelperから
次を実行する。`--scope`はOwnerが明示承認した一行の範囲をそのまま渡す。helperは現在のrepo / PR / head、
Summary binding、Owner actorを照合し、同じ最新の未編集コメントがあれば重複投稿しない。投稿結果だけを
formal Verifyの代わりにせず、必ずProviderでGitHubから再取得する。

```powershell
python -m governance.owner_acceptance_transport --context outputs/governance/context.json `
  --verification outputs/governance/verification.json `
  --summary outputs/governance/owner-summary.json --scope '<Ownerが承認した一行の事業範囲>'
```

この移行PR自身は旧方式で受入する。OwnerがGitHub PR Conversationへ上記の完全形式を投稿し、
既存Provider / formal Verifyで確認する。新helperはその版がformal mainに採用されるまで起動を拒否する。
helperを迂回した代理投稿や、このPRへの新方式による自己承認をしない。

GitHub取得は`python -m governance.owner_comment_provider`だけが行い、GeneratorとVerifierは外部fetchを
行わない。ProviderはGitHub APIでrepository・PR・Owner numeric actor ID・head・コメント本文・編集状態・
撤回を観測し、完全一致した場合だけ署名付きEvidenceをGit管理外へ出力する。Provider秘密鍵は
`GOVERNANCE_OWNER_EVIDENCE_PRIVATE_KEY`（base64の32-byte Ed25519 seed）から読む。

```powershell
python -m governance.owner_comment_provider --context outputs/governance/context.json `
  --verification outputs/governance/verification.json `
  --summary outputs/governance/owner-summary.json --output-dir outputs/governance/owner-evidence
.\scripts\Verify-ContextSnapshot.ps1 -Profile formal-acceptance `
  -ContextPath outputs/governance/context.json -Provider outputs/governance/provider.json `
  -OwnerSummary outputs/governance/owner-summary.json -Evidence <CI Evidence paths>,<Owner Evidence path>
```

Verifierはrepo外Trust Anchorの公開鍵でProvider receiptをoffline検証し、現在のPR番号、完全head、
`verification_input_hash`、Summaryの再計算済み`summary_binding`との一致を要求する。
receiptは5分で失効する。merge直前にProviderを再実行してGitHubの最新コメントとheadを確認し、
fresh EvidenceでVerifyを再実行する。承認コメントの編集・削除、後続の
`OWNER_ACCEPTANCE: REVOKED`コメント、head・binding変更ではProviderがHOLDし、既存receiptも
5分で失効する。offline Verifierだけでは取得後のGitHub状態変化を即時検知できないため、
Provider再観測とVerifyからmergeまでを連続して行う。GitHub API・Provider・投稿の失敗、Owner actor不一致、
scope変更もHOLDとして再承認または復旧を待つ。承認コメントはGitHubでの後続`OWNER_ACCEPTANCE: REVOKED`投稿で
撤回できる。撤回後の再承認は新しい明示判断と新コメントを要する。

### v1.0 → v1.1 Trust Anchorの一回限りのbootstrap（PR #96）

この節はPR #96のGovernance移行だけに適用する。通常のOwner Acceptance、technical gates、
formal Verify、merge直前のOwner最終承認を免除しない。PR headまたはSummary bindingが変われば、
現在対象への説明・Owner承認・Evidenceを取り直す。対象PRと値を固定する記録はTask Contextと
Owner Acceptance Summaryに置き、ここへ変動SHAを恒久値として埋め込まない。

1. 既存の本番v1.0 Anchorを読み取り、そのbytes digestを記録し、Owner承認の下で保護されたbackupを作る。
   merge前に本番Anchorをv1.1へ置換しない。`bootstrap_formal_commit`は初回Ver2のbootstrap起点を
   表す履歴値であり、今回のPR headやmerge commitへ書き換えない。
2. 本番とは分離した`%LOCALAPPDATA%\ShopeeGovernance\bootstrap\pr-96\`の下に、Owner承認の下で
   Ed25519鍵を生成する。秘密鍵seedはWindows CurrentUser DPAPIで暗号化し、当該ユーザーだけが読める
   `private\owner-evidence.seed.dpapi`へ保存する。v1.0 Anchorをコピーしてversionと公開鍵だけを加えた
   v1.1 test Anchorを`appdata\ShopeeGovernance\trust\1296080967.json`へ置く。本番trust directoryと
   Gitへtest鍵・Anchorを置かない。秘密鍵はProvider起動中だけprocess environmentへ復号する。
3. 分離したprocessでは`LOCALAPPDATA`を上記`appdata`へ向け、
   `GOVERNANCE_TRUST_ANCHOR_JSON`を解除する。候補PR headとCI Evidenceでformal snapshot、
   technical Verify、9項目Summaryを再生成する。Owner本人が現在head・verification input hash・
   Summary binding・scopeを明記したPR #96 Conversationコメントを投稿する。
4. candidate ProviderがGitHubからそのコメントを再取得し、分離鍵で署名する。candidate offline Verifierが
   signed Evidenceと正しいSummaryで`CONTINUE`、改変したEvidenceやbindingで`HOLD`を返すことを確認する。
   Providerは旧v1.0 Verifierが読む3つの`source` binding fieldも署名済みreceiptと同値で出力し、
   candidate Verifierはその同値性を検証する。これをPR #96の一回限りの互換契約とする。
5. 本番v1.0 Anchorのdigestが開始時と一致することを確認する。現行formal mainのv1.0 Verifierを
   **同じ**PR head・context・CI Evidence・GitHubから実取得したOwner Evidenceに対して実行し、
   `CONTINUE`を確認する。candidate v1.1 Verifyとv1.0 Verifyの両方が`CONTINUE`で、Ownerがその
   headとSummaryを最終承認した場合だけPR #96をmerge候補とする。手製Evidenceで代用しない。
6. merge後、PRのMERGED状態とformal main SHAを確認してから、Owner承認の下で本番Anchorを原子的に
   v1.1へ切り替える。元のidentityと`bootstrap_formal_commit`を維持し、test時に確認した公開鍵だけを
   加える。新formal mainのValidate・snapshot・read-only Verify、Trust Anchor一致、SG INACTIVEを確認する。
   問題時は保護backupの同一bytesを原子的に復元し、GovernanceをHOLDとして報告する。
   暗号化秘密鍵を紛失・漏洩した場合は使用を停止し、Owner管理下で鍵交換する。

offline Verifierは取得後のGitHub編集・削除を即時検出できない。step 4と5およびmerge直前は5分以内の
fresh receiptで連続実施し、head・comment・CI状態を再観測する。どれかが変わったら一回限りの手順も
再承認待ちに戻す。PR #95はこのbootstrapに含めず、PR #96採用後の新mainへ追従させて別途受入する。

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
