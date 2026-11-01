# 管理基盤Ver2 Runbook

毎タスクのmandatory原則は[AGENTS.md](../AGENTS.md)、本書はその詳細手順とする。
AGENTSが指定する実行時点で該当節を必ず読み、適用する。参照化で手順・承認・gateを任意化しない。
現行の入口はAGENTSと本書。DEC-0152は開始・停止範囲・参照方法を整理する。
DEC-0072 / DEC-0073の正式な信頼・承認契約、DEC-0150のfresh Verifyは維持する。

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
`GOVERNANCE_TRUST_ANCHOR_JSON`を使用し、実行前に
`GOVERNANCE_TRUST_ANCHOR_SOURCE=local-file`または`ci-env-json`を明示します。
CI方式はGitHub Actions内に限ります。`APPDATA` fallback、暗黙の優先順位、二重指定はありません。
選択元の欠落・方式未指定はHOLD、形式不正・二重指定・identity不一致はHARD_STOPです。
snapshotは参照方式とAnchorのcanonical JSON SHA-256を記録し、Verifyは選択元から現在の値を再解決します。
Anchorの配置・差替えはOwnerの別承認を要し、repo内の値から生成・上書きしません。
`--expected-repo`等の本番overrideも設けません。

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

### 操作別の開始・検証条件

| 操作 | 開始時と成果確認 | 正式受入との境界 |
| --- | --- | --- |
| 通常read-only調査（Git・コード・文書・非秘密の保存ログ） | 上記Git観測、AGENTS・再開案内・対象scope確認後に開始。関連箇所を読む | Validate、snapshot、Task Context新設、実Trust Anchorの読込は開始条件にしない。実API・実商品・secret読込は「read-only」という名称でも含まない |
| 通常のlocal編集 | 承認された目的・変更対象・禁止範囲、既存ユーザー差分、関連する現行契約を確認。継続タスクは既存Task Contextと照合 | 範囲内編集・修正のために正式VerifyのCONTINUEを要求しない。未承認の境界変更、停止中の実運用、別taskの差分混入は不可 |
| offline検証・commit・push・Draft PR | 関連tests、変更時のGovernance設定Validate、差分・secret確認。必要な既存CIを実行し、未実行・失敗を区別 | 合成fixture・mockは実受入の証拠にしない。snapshotを通常編集の度に作らない。検証済み候補の公開はDEC-0073の承認範囲内 |
| 正式受入・merge、および既存契約で正式検証を要求する設置 | repo外Task Context、承認された実Trust Anchor参照、現在対象のValidate→snapshot→fresh Verify。mandatory technical gates、Summary、Owner最終承認、fresh Owner Evidenceを確認 | HOLD / HARD_STOPを保持。実環境の鍵・Anchor操作、設置・live・deployはそれぞれ別承認。merge後のValidate・snapshot・read-only Verifyも維持 |

通常調査は既存Git・`rg`・ファイル読込で行い、新しい認可engineを設けない。
`Verify-ContextSnapshot.ps1 -Profile read-only`は**正式なsnapshotの検証profile**であり、
通常の読み取り調査を意味しない。既存の全Verify profileは従来どおりTrust Anchorとfresh bindingを要求する。
軽量作業の成功・policy checkerのPASSをformal VerifyのCONTINUEへ読み替えない。

Governance設定Validateは実Anchorや秘密鍵を使わず実行できる。

```powershell
.\scripts\Invoke-GovernanceV2.ps1 -Mode Validate
```

正式検証が必要なときだけ、承認された参照元とrepo外Task Contextを用いる。
以下の例は実Anchorの読込承認がある場合に限る。受入時は`formal-acceptance`と必要Evidenceを指定する。

```powershell
.\scripts\Update-ContextSnapshot.ps1 -TaskContext <repo外context.json> -TrustAnchorSource local-file
.\scripts\Verify-ContextSnapshot.ps1 -Profile local-validation -ContextPath outputs\governance\context.json `
  -TaskContext <repo外context.json> -TrustAnchorSource local-file
```

CURRENT_WORK・DECISION_LOG更新時は参照先・置換範囲・意味整合と関連docs testを確認する。
正式受入では文書変更も含め現在対象のsnapshotを生成し直す。合成Anchorを実Anchorの代わりに配置しない。
offline再現に必要なsnapshotはtestsの一時領域で生成し、正式Evidenceと明確に区別する。

Pythonは`-PythonPath`、`GOVERNANCE_PYTHON`、PATHの順に解決します。PowerShell 5.1と7で同じPython共通実装を呼びます。
Generatorは観測だけを行い、fetch、checkout、branch、index、Stateを変更しません。Verifierは既存contextを評価し、
Generatorを暗黙実行せず、snapshotを削除しません。Generatorはoptional観測不足だけで失敗させません。
派生出力は既定のGit管理外 `outputs/governance/` に生成します。手編集・commitはしません。

通常Verifyは常に`verification_mode=fresh`です。現在のHEAD/tree、Git working-tree差分、Governance設定hash、
Trust Anchor参照方式/hash、Task Context本文をsnapshotと再照合し、古いbindingはHOLDします。
Task Contextを含むcontextをVerifyするときは、同じrepo外ファイルを`-TaskContext`へ渡してください。
過去snapshotのhistorical replayは現行Verifyにありません。古い形式や現在のAnchor bindingを持たないsnapshotは
再利用せず、現在のAnchorとTask Contextからsnapshotを新規生成します。

Exit codeは`0=CONTINUE`、`10=HOLD`、`20=HARD_STOP`、`64=usage`、`70=internal`です。

## HOLDの適用範囲

停止理由、対象操作、依存先、再開条件を既存Task Contextのopen_itemsまたは作業報告へ短く残す。
新しい承認台帳や停止解除制度を作らない。判断不能な信頼・外部影響・復元不能性は停止側へ倒す。

| 停止の原因 | 停止を維持する操作 | 独立して継続できる承認済み作業 |
| --- | --- | --- |
| Anchor／署名鍵不足、Owner未承認、CI・Evidence不足／古いbinding | 正式受入・署名・merge、およびその成立を前提にする設置・live | コード・文書の原因調査、合成fixtureでの修正・tests、差分review、検証済み候補のDraft公開 |
| tests失敗、Config不正、protected gate失敗 | 失敗対象を検証済みとしてcommit／採用すること、依存する製品操作 | 該当原因の調査・最小修正・失敗testの再実行。gate削除や期待値の無根拠な変更は不可 |
| repository identity不一致、secret露出疑義、無関係dirty変更 | 当該信頼前提による書込み・公開・署名・実行。ユーザー差分の上書き | 読取診断、秘密を出さない範囲確認。独立した正しい対象を実測できるまでは依存する編集をしない |
| Safety／予算／商品／実運用の明示停止 | 当該商品・サービス・保存先と依存する操作 | 停止対象へ触れない、承認済みの文書・合成tests等。別task・別profileを名乗って同じ操作を再開しない |

HARD_STOPも解除しない。独立性を確認できない作業は停止対象に含める。
Ownerが全作業停止を明示した場合はそれを優先する。原因解消後は元のgateを現在対象で再評価し、
失敗記録や実行済み消費を消さない。正式VerifyがHOLDのままならformal採用完了とは報告しない。

## Decision読込

DEC-0152により、通常の実行手順はAGENTSと本書から特定する。
Decision Logは判断理由・変更履歴のappend-only正本であり、古い実行記録を毎回現行手順へ再構成しない。

1. CURRENT_WORK・PROJECT_ROADMAPで対象／禁止範囲を確認し、Required Decisionsのうち今回のmarketplace／module／phaseと変更する契約に関係する本文を読む。通常調査では無関係な市場・過去受入本文の一律読込を要求しない。
2. 契約を変更する場合は、その根拠DECと必要な前提・置換元、対象IDを参照する後続DECを検索して本文を確認する。Governance・承認変更ではDEC-0072 / DEC-0073と関連する後続DECを必須とする。番号の新しさだけで旧判断全体を失効させない。
3. 現行文書と履歴の矛盾、参照不足、対象不明、Required Decisionsの欠落・陳腐化を疑う場合は、`rg "^## DEC-" docs/DECISION_LOG.md`と本文全体の関連語／ID検索へ広げる。ヒットした本文は省略せず読む。解消しなければ全文へfallbackし、それでも不明な承認・停止条件に依存する操作は停止する。

通常の変更なし調査には全見出し読込・全後続履歴追跡を要求しないが、未読を制約なしとは扱わない。
現行文書から重要な制約が脱落している疑いがあれば、履歴を無視して進めず上記検索で解消する。
読込済みで内容が変わっていない本文は同じタスクで再読込不要。選択理由・解消した置換関係は既存の作業報告へ短く残せばよい。

Required Decisionsは次の単一作業に必要なIDと参照理由だけに保つ。
過去工程の全IDや本文を積み増さず、不要になった参照は再開案内から外せる。Decision本文と受入履歴は削除しない。
恒久契約の変更時はAGENTS／Runbookの該当手順と新Decisionを同一PRで整合させ、
新Decisionに置換する旧規則の範囲と維持する境界を明記する。巨大索引・新しい管理基盤は作らない。

## Evidence

- local Evidenceは一時的で、CIまたはowner証跡へ自動昇格しません。
- CI artifactはworkflow/job/actor/対象commit/resultを照合します。
- 永続Evidence recordは`governance/evidence/<canonical-sha256>.json`です。
- code Evidenceの再利用は日付でなくcommit/tree/config/gate/profile/test plan bindingで決めます。
- legacy migrationは`LEGACY_ACCEPTANCE`とし、実行していないVer2 TESTを捏造しません。
- overrideとOwner Acceptanceはexact target bindingが変われば失効します。

現行実装の限定offline再現では、snapshot生成時刻だけの更新と同一bindingのOwner receipt再取得は
Summaryの変更を要求しない。一方、同じHEAD・scopeでもCI再実行のrun attemptに伴うEvidence ID変更や
Provider観測情報の変更はverification input hashを変え、旧Summaryを無効にする。
単なるEvidence実行時刻変更と識別情報変更は同一ではない。再取得・再実行前後のbindingをCodexが照合し、
変更があれば現行の再提示・再承認を維持する。今回、技術再検証とOwner承認を分離する新方式は導入しない。

## Formal acceptance

Governance mandatory checksはbranch protectionと独立して評価します。provider欠落、check欠落、pending、
skipped、neutral、古いheadはformal acceptanceを満たしません。mandatory technical gate完了前はOwner Acceptanceを要求しません。

Owner Acceptance Summaryは、採用対象、変更、非対象、既存運用影響、主要リスク、確認済みEvidence、既知制約、
承認後の意味、rollbackの9項目を事業用語で説明します。オーナーへhash、SHA、schema等の技術判断を要求しません。

### 通常のOwner Acceptanceの入口

通常は本節から実施する。PR #96 bootstrapや過去PRの復旧記録は履歴であり、通常受入の手順ではない。
現在の鍵の所在・実環境の使用許可はOwner管理元の現在の指定を使い、過去のpathや成功記録から推定しない。

1. **権限と環境を確定**：現在の対象PR・scope、実Anchorの読込許可、既存鍵の限定利用許可を既存Task Context／Owner指示で照合する。採用承認だけから秘密鍵利用を推定しない。使用するPythonのversion・依存と、formal main採用済みのGovernance一式・実import元を確認する。WindowsではUTF-8で起動し、既存の保護鍵を扱える許可済みユーザー／実行環境を用いる。環境の再構築・権限変更を自動実行しない。
2. **現在のAnchorを確認**：許可された操作で「Trust Anchor」節の`local-file`（CI内だけ`ci-env-json`）を明示し、Owner管理元から指定された正本を解決する。欠落・二重指定・不一致時は停止する。履歴のbootstrap起点は現在HEADへ書き換えない。repo内の公開鍵・自己申告identityで代替しない。
3. **技術条件と説明を固定**：現在Task Context・Validate・snapshot・fresh VerifyとCI Evidenceを照合し、mandatory technical gatesとPost-Merge Stability確認後に9項目Summaryを提示する。Ownerの現在対象への明示的最終承認を待つ。鍵利用許可が未成立なら、必要な権限もこの時点で具体的に説明する。
4. **承認の搬送と署名**：下記方式Bを用いる。Owner指定の既存保護鍵だけを許可済みprocess内で一時解決する。DPAPI保護seedの場合はCurrentUserでメモリ内だけに復号し、Provider専用子processの`GOVERNANCE_OWNER_EVIDENCE_PRIVATE_KEY`へ渡す。親shellの恒久設定、コマンド引数、ログ、ファイルへ平文を置かない。Providerは入口で環境変数を除去し、派生公開鍵と現在Anchorの公開鍵を**GitHub取得・署名前**に照合する。不一致・鍵未設定はHOLD。子process終了とfinallyで一時環境を破棄する。子孫ghへ秘密鍵を渡さない。メモリの完全消去保証とは称さない。
5. **採用直前と終了**：同じ現在対象のOwnerコメントをProviderで再観測し、5分以内の署名Evidenceとformal Verify CONTINUEを連続して確認する。mergeには別途その対象の最終承認が必要。merge後は「Post-Merge Stability」の検証とTask Context CLOSEDを行う。失敗時は当該操作を止め、鍵の新規生成・探索・交換・Anchor変更へ自動移行しない。

現在の保護鍵参照を特定できない場合はOwner管理元へ参照情報を確認する。秘密本文の貼付けを求めず、
ディスク全体・過去backupを総当たりしない。参照が一度固定できれば既存Task Contextに非秘密の参照だけを保持できる。
実鍵／Anchorの確認を行っていないoffline作業では「現在有効な鍵を確認済み」と報告しない。

#### 統合準備A1：参照・権限・失敗診断

DEC-0156を適用する。統合予定のPRについてCIと並行して準備し、通常開発の開始条件にはしない。
Codexは現在のOwner原指定に結び付く鍵の非秘密参照と、今回PRの利用許可を別々に確認する。
過去の成功スクリプトは手掛かりであり、現在指定の証明ではない。CLOSED taskの利用許可を転用しない。
指定元を特定できなければ、最終採用承認を求める前に不足する非秘密記録を具体化して報告し、
実鍵操作を停止する。鍵本体・backupを探索せず、秘密本文の提示をOwnerへ求めない。
既存Task Contextのauthorization_refsは原指定・許可の索引であり、自由文や参照の一致だけで権限を認定しない。
`owner_acceptance_ready`は技術gateの成立を示し、現行鍵指定・利用許可まで揃った証明ではない。

`Test-OwnerEvidencePreparation.ps1`は`owner_evidence_preparation`による非秘密の入力整理だけを行う。
TaskContext・PythonPath・KeyPath・ReferenceSource・KeyUseAuthorizationRefを明示する。
KeyPathは参照文字列としてだけ扱い、現物の存在確認・読取・復号をしない。Anchor・Provider・GitHub・署名にも接続しない。
OPENの今回PR向けContextと、原指定・利用許可参照のauthorization_refsへの結合を確認し、不足をまとめて報告する。
追加gateがある場合はAdditionalGateReasonRefの入力と同じ索引への結合も要求する。参照一致は理由の妥当性を証明しない。
入力整理がCONTINUEでも`formal_acceptance_ready=false`、`key_checked=false`、
`requires_current_designation_review=true`を維持し、CodexによるOwner原指定の現在性確認を省略しない。
新たな承認制度・台帳・鍵解決機能・署名入口を設けない。

実際の照合は、別途許可された既存実行環境から通常Providerの`--check-key-only`を使う。
このmodeはformal-main起動制限と公開鍵比較を維持し、GitHub取得・署名・Owner Evidence生成を行わない。
通常の署名経路とV1 bindingは維持する。`--diagnostic-json`は安全な診断だけを追加し、
実鍵の解決や一時環境への注入を今回の準備補助へ移さない。

事前確認と、最終採用承認後の署名・同一bindingのreceipt更新・統合後Anchor確認を一度の説明に並べ、
各操作の許可、回数・期限・終了、停止・保全条件を既存票へ固定する。未許可操作を条件付き許可へ推定せず、
技術失敗を自動retryへ変換しない。許可内のoffline修正は継続する。
失敗時は安全なreason code・実行段階と、署名前の拒否／署名済み／成否不明を分けて保持する。
Evidenceの欠落だけで未署名と判断せず、秘密・raw exception・子process出力本文を共有しない。

A1のoffline検証・候補公開は、実鍵成功・実運用での中断削減の実測とは別である。
初回採用も現行方式の別承認と署名を要し、鍵参照が未解決なら正式統合は停止する。
A2のbinding／再承認条件変更、Bの署名省略経路、GitHub設定変更をA1完了から自動着手しない。

#### 別個の決裁をまとめて提示する

PR正式採用と、指定済み保護鍵・実Anchorの限定利用は別の明示決裁として、一度の説明に並べて提示できる。
「承認集約・自律継続ルール v1」の票項目に従い、各項目の許可／未許可を個別に判別できる回答を得る。
採用だけの承認から鍵利用を、鍵利用だけの承認からmergeを推定しない。曖昧なら未確定項目だけを確認する。
DEC-0152の未採択提案にあった、採用承認から鍵利用まで含めたものと扱う恒久的権限変更は採用しない。
本ルールの文書PR採用自体も、今回または将来の鍵利用を許可しない。

鍵利用票では既存の指定済み参照、現在PR・Summary・scope、読込／メモリ内復号／公開鍵一致確認／
Provider署名、同一bindingの5分receipt更新の条件・最大回数・期限・停止条件を固定する。
新鍵生成・探索・交換、秘密export、恒久環境設定、Anchor変更、GitHub設定、deploy、商品APIを含めない。
同一agentが搬送と署名を担う既存trust modelと、GitHub actorが独立した人間操作証明ではない限界を説明する。
許可不足でも、鍵を使わない技術準備・offline検証は「HOLDの適用範囲」に従い継続できる。

### PR authorとOwnerが同一の場合のGitHub Owner証跡

GitHubはPR author自身のApprove reviewを受け付けない。OwnerのPR Conversationコメントを正式な
`GITHUB_OWNER` Evidenceとして扱う場合は、repo外Trust Anchor v1.1.0の
`owner_evidence_public_key`と、それに対応するProvider専用Ed25519秘密鍵を先にOwner管理下で設定する。
公開鍵をrepo内の自己申告から採用しない。秘密鍵をGit、Task Context、ログ、Evidence、コマンド引数へ
書き出さない。鍵未設定・不一致ならHOLDとし、手製JSONや旧形式のOwner Evidenceで代替しない。

technical gates完了後、下記「Post-Merge Stability」の反実仮想merge確認がPASSとなった場合だけOwner Acceptance Summaryを生成し、Ownerへ9項目と対象PR・事業scopeを提示して
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

明示承認後、現在のSummaryを渡したformal-acceptance fresh Verifyが`owner_acceptance_ready=true`、
停止理由が`OWNER_ACCEPTANCE_REQUIRED`だけであることを確認する。formal mainへ正式採用済みのhelperから
次を実行する。`--scope`はOwnerが明示承認した一行の範囲をそのまま渡す。helperは現在のrepo / PR / head、
Summary binding、Owner actorを照合し、同じ最新の未編集コメントがあれば重複投稿しない。投稿結果だけを
formal Verifyの代わりにせず、必ずProviderでGitHubから再取得する。

```powershell
python -m governance.owner_acceptance_transport --context outputs/governance/context.json `
  --verification outputs/governance/verification.json `
  --summary outputs/governance/owner-summary.json --scope '<Ownerが承認した一行の事業範囲>'
```

Owner Acceptance Provider / Transportは`verification_mode=fresh`の結果だけを受け付けます。
実行プロセスにも上記`GOVERNANCE_TRUST_ANCHOR_SOURCE`を明示し、ローカル操作では`local-file`を指定します。
ProviderとTransportはGovernance一式が`refs/remotes/origin/main`と一致し、Governance配下に未追跡ファイルがない場合だけ動作します。engineだけなど一部helper以外を変更した候補版からも署名付きOwner Evidenceや承認コメントを作成しません。

Governance実装そのものを変更するPRの初回審査では、候補checkoutのengine / Provider / Transportを承認に使いません。
別のformal-main checkoutからformal main版の`governance.engine`とOwner helperを実行し、CLIの`--repository`
には審査対象checkoutを指定します。そこで新しいTask Contextからsnapshotを生成し、同じcandidate HEAD・CI Evidence・
Owner bindingを従来のformal main実装でVerifyします。候補schemaの`verification_mode`は、旧formal main writerとの
この移行審査に限り省略可能ですが、候補engineは常に`fresh`を出力し、候補Owner helperは`fresh`欠落を拒否します。
この旧方式のVerifyはP5設置可否のfresh Verifyとして流用せず、Anchor復旧後のP5確認と、候補PR merge後の新方式
Validate／snapshot／fresh Verifyを別途行います。formal-main checkoutや候補targetの正確なbindingを用意できない場合は
審査をHOLDし、候補版Verifyへ切り替えて続行しません。

PR #105のGovernance移行PR自身は、当時のformal mainの旧方式で受入済みである。上記のcurrent formal-main実装によるcandidate審査は、以降のGovernance実装PRにも使える移行経路であり、PR #105固有の例外手順とは区別する。通常の後続PRはOwnerの明示的最終承認後にformal mainへ採用済みのhelperを使い、技術値の手動コピーを求めない。helperはOwner actorの最新コメントが`OWNER_ACCEPTANCE: REVOKED`ならHOLDし、APPROVEDを自動投稿しない。稀な再承認では新しいOwner明示判断と新コメントを要し、完全形式の手動コメントによるfail-closed復旧を許す。新helperはformal main採用前に候補checkoutから起動できない。

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
  -TaskContext <repo外context.json> -TrustAnchorSource local-file `
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

### 歴史資料：v1.0 → v1.1 Trust Anchorの一回限りのbootstrap（PR #96）

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
同一差分・環境の成功testを理由なく繰り返さず、失敗・変更・未解決事項に応じて再実行する。
DEC-0163では作業中は関連テストだけとし、通常の全体pytestは最終差分を固めた統合前に1回とする。
廃止機能専用の明示selectorだけを別実行へ分け、混在・共有・判断不明は残す。
標準／retired／allの呼出しと分類理由は[テスト範囲](TEST_SCOPE.md)を正本とする。
全体実行中は繰り返し完了確認を続けず区切り、未完了を成功扱いにしない。
CIだけに置くcommerce-api-coreのテストはSora本体とは別step・別の時間と件数で集計する。
結果は対象・環境・実行方法・成否を特定できる最小限で報告し、全ログを複製しない。
mandatory checksの削減、古いEvidenceの新headへの転用、未実行のPASS扱いはしない。

WORK_BRIEFを使う条件は、目的が曖昧、複数module、責務変更、外部API、費用、データ移行、
復元不能操作等を伴い、短い依頼だけでは安全な実装範囲を固定できない場合とする。
`docs/templates/WORK_BRIEF.md`を使用し、すべての作業開始条件にはしない。
pushまたはPRだけを理由に必須化しない。project名、chat名、worktree絶対pathを安全gateにしない。

## 承認集約・自律継続ルール v1

DEC-0153を適用する。DEC-0073の通常開発承認を維持し、同一目的・同一リスク境界・同じ固定対象の
連続した技術工程を、既存のWORK_BRIEF／P5非公開票または作業報告で具体化する。
新しい承認制度・台帳・汎用認可engineは作らず、通常の局所開発へ票作成を一律要求しない。
包括的な「最後まで進める」指示は、AGENTSの別承認事項や個別契約の禁止操作を許可しない。

### Ownerが却下した手段の扱い

タスク開始時と承認案の作成前に、関連する正式文書と現在有効なOwner判断を確認する（DEC-0155）。
Ownerが却下した手段は、実質的な条件が変わらないまま再提案・再承認依頼しない。
タスク名・票・表現を変えて同じ依頼を繰り返さず、許可済みの別手段で進める。
新事実・条件変更がある場合は以前との違いと必要な判断を明示する。ただし、Ownerが明示した
継続的な不実施方針はOwner自身の明示変更まで維持し、変更を促す反復依頼を行わない。
却下を別操作の許可や未確認情報の確認済み根拠へ読み替えず、既存gateと停止範囲を維持する。
Shopee公式問い合わせの不実施は[P5実施設計](P5_ACCEPTANCE_EXECUTION_PLAN.md#5-shopee認証の有限計画案)に従う。

### 承認前の準備と個別票

Codexは実行可能なoffline事前確認を先に終える。対象／依存条件／実装／payload／有限枠／保存と復旧／
失敗時の挙動を現行契約・関連testsで確認し、差分・secret確認と必要なCI・read-only reviewを進める。
Ownerへ技術方式や毎回の次作業を選ばせず、目的内の調査・最小修正・再検証を自律的に進める。
実Anchor・鍵・実API・実設置が必要な確認は未実施として分離し、その未実施をPASSにしない。
formal採用の承認要求はmandatory technical gatesとPost-Merge Stability成立後だけとする。
追加gateを指定する前に、変更分類・component・影響capabilityから現在の必須集合を確認する。
追加する場合は対象リスク・coverageとの対応理由をTask Contextまたは既存報告へ残し、一律に全件を追加しない。
Governanceの意味的な回帰やPH/SG保護を失う削減は行わず、CIで動くjobと正式な必須gateを区別する。

個別の別承認を求める場合、以下を具体化し、Ownerへ事業上の意味と残るリスクを示す。
実対象・秘密の参照情報は非公開票へ置き、既存Task Contextのauthorization_refsで現在の承認に結合する。

| 項目 | 固定する内容 |
| --- | --- |
| 目的・許可操作 | 同じ目的の工程列、許可する各操作と対象外。設置、credential参照、API、merge等の別決裁を識別可能にする |
| 固定対象 | repo／PR・現在Summary、release、market／shop／商品、保存先、指定参照等、今回操作のbinding。将来の非依存項目は未結合・禁止として分離 |
| 期限・終了 | 時刻とtimezone、または有限のsession／工程終了条件。撤回・対象変更・最初の停止等、許可が終了する条件も固定 |
| 累積上限 | 操作回数、物理send、商品数、予約token／費用、再取得・再試行分。既消費・予約を差し引き、余り枠の他対象転用を禁止 |
| 事前許可する再試行 | なしを既定に、許す失敗条件・同一性／副作用の確認方法・修正範囲・最大回数・待機／期限・追加予約を列挙。SDK・子processの隠れretryも含める |
| 停止・保全・復旧 | HOLD／HARD_STOP／Safety、部分実行・結果不明、binding変更、予算・保存障害で止まる操作と依存先。保持する予約・データ・履歴、許可済み復旧と別決裁の境界 |

今回要求する操作の依存項目は先に解消する。許可前に実行できない確認は、その確認自体の限定操作と
成功後にだけ進む工程を票で区別する。作成後に得る実IDは生成後に結合し、仮値で事前確認を通さない。
依存条件を用意できない工程まで同じ承認単位へ詰め込まず、独立した準備だけを具体化する。
承認原文・日時・票version/digest・明示された操作範囲を既存Task Contextへ参照結合する。
新しい別権限が必要なときだけ不足分をまとめて尋ね、成立済みの同じ許可を毎工程で聞き直さない。

### 失敗・副作用・再試行

実行結果は操作単位で、未実行／副作用ゼロを確認／部分実行／結果不明／成功を区別する。
HTTP送信0やexit codeだけで副作用ゼロとしない。秘密の参照、永続予約、作成物、ACL／probe、
外部送信、出力失効等を確認し、確認不能な項目があれば結果不明として保持する。
実secret・API・実データを使う確認操作も許可を別に照合する。

| 結果 | 再開判断 |
| --- | --- |
| 副作用ゼロを必要項目すべてで確認 | 技術調査・修正・offline再検証は継続できる。承認対象操作の再試行は、許可が有効で、票の条件・回数・期限・残枠と現行契約をすべて満たす場合だけ |
| 部分実行 | 作成物・予約・消費・履歴を保全し、同じ操作の再実行を止める。既存契約に沿う照合・復旧の許可範囲を確認し、必要なら残る操作だけを別承認へ提示 |
| APIを含む結果不明 | 未送信／失敗と決めつけず、二重送信・作成・投入を止める。無許可の診断API・再取得・削除を行わず、結果照合と必要な新承認を分離 |
| 許可終了・撤回・対象／binding変更・上限到達 | 旧許可で再試行しない。同じ目的でも現在対象の票と承認が必要。初回停止で終了する票は副作用ゼロでも復活しない |

一般の再試行欄は個別の再送禁止、sticky stop、RESERVED／UNKNOWN lockを解除しない。
P5の自動retry=0・失敗／不明予約保持・部分設置保全を優先し、reset・再初期化・別runで回避しない。
新承認でも既存gateと技術的な再開条件は別途必要であり、予約・履歴を消して成立させない。
技術的失敗は原則として自律調査・最小修正・offline再検証を続ける。停止は当該承認対象操作と、
その結果・信頼前提に依存する工程へ限定する（「HOLDの適用範囲」）。独立性が不明なら停止を維持する。
formal Verify／Owner Evidenceのfreshnessとbindingは「Evidence」「Formal acceptance」を適用する。
同一bindingのreceipt更新を事前許可できても、head・CI Evidence等によるSummary変更時の再承認を免除しない。

### 完了・失効・次工程

独立タスクの完了、個別許可の失効、次の独立工程を分ける。停止で許可が終了しても、承認済みの
独立したoffline修正まで終了扱いにしない。次工程が見つかっても元タスクの権限は拡張されない。
post-merge検証成功後のTask Context CLOSEDはそのタスクの終了であり、未使用枠や過去の鍵利用・
設置許可を別タスクへ転用しない。新タスクは現行正本と現在対象から開始し、必要な別承認を取り直す。
履歴としての票／Evidenceは読み取れるが、過去票の書換えや遡及適用で許可を復活させない。
成功記録だけの次PR・Decisionは作らず、「Post-Merge Stability」に従い終了する。

## タスク境界・正本化

同じ原因・同じ受入条件の問題は同じCodexタスクを継続できる。次の場合は分割の候補とする。

- 独立した問題が解決し、次の独立問題へ移る。
- 実装目的、受入条件、module、責務が変わる。
- 修正・テストの反復で会話、log、diffが大きく蓄積した。
- 同じ調査、ファイル読込、説明を繰り返し始めた。
- Context Compaction等が発生し、長大なタスクになった。

同一問題で修正・テストの反復が3回程度を超えたら、機械的に終了せず、
タスク分割または原因分析への立返りを一度見直す。

基本順序は下記「Post-Merge Stability」のNo Recursive Finalizationを適用する。
終了・handoff時は今回の変更範囲に応じて次を実施する。

1. 採用するコード・設定・テストを確定する。
2. 対象testと必要な回帰testの結果を確認する。mock、実API、実データ、Owner受入を分ける。
3. `git status`とdiffで、無関係な変更、未追跡ファイル、secret混入がないか確認する。
4. formal mainで成立する再開案内が変わる場合は、merge後にも正しいCURRENT_WORKを同一PRへ含める。Required Decisionsも「Decision読込」に従い次工程への関連性を確認する。
5. 恒久判断が変わった場合だけDECISION_LOGへ新IDで追記し、既存entryを書き換えない。
6. 長期工程・順序が変わる場合だけPROJECT_ROADMAPを更新する。
7. 恒久ルールが変わる場合だけAGENTS等を更新する。詳細を複数文書に複製しない。
8. 正本文書更新時は「開始・実行」の操作別検証を行う。正式受入ではsnapshotを再生成する。
   必須生成・検証の失敗を完了扱いにしない。通常編集にはsnapshotを一律要求しない。
9. 関連検証、変更ファイル、未追跡ファイル、secret確認後、検証済み範囲だけlocal commitする。
   push / Draft PRは通常開発承認のscope内、merge / deployは別の承認規則に従う。

次のタスクが過去会話を読まずに正式状態、確認済み事項、未解決事項、次の単一作業と停止条件を
判断できることを完了条件とする。テスト失敗、無関係なdirty変更、snapshot生成失敗、正本矛盾で
正本化できない場合は阻害要因を示して当該正本化を停止する。独立作業は「HOLDの適用範囲」に従う。handoff自体は正本の代替にしない。
handoffには完了内容、確認済みtests、未解決事項、次タスクの目的、最初に読む正本fileまたはcommitを記載する。

## Post-Merge Stability

DEC-0114を適用する。DEC-0072 / DEC-0073 / DEC-0106のtechnical gates、Owner最終承認、
fresh Owner Evidence、binding、formal Verify、protected capability契約は維持する。
過去Decisionの個別受入事実は保持するが、後続の成功記録PRを通常終了工程とする部分は本節に置き換える。

### A. Post-Merge Stability Rule

Git管理文書へ追加・変更する現在状態は「このPRが今このままformal mainへmergeされた直後」にも正しくする。
branch上の文面は採用後の再開案内として用意し、formal採用の成立はGitHub / Gitから別に確認する。
merge直後に古くなる現在状態の例は、WAITING_APPROVAL、OWNER_ACCEPTANCE_REQUIRED、
Owner承認待ち、Owner Acceptance待ち、Owner最終承認を待つ、未マージ、Draft PR、merge前、
このPRをmerge後に正本化する、current headの承認待ちである。
これらはGitHub、repo外Task Context、Git外Evidenceで管理し、CURRENT_WORKへ複製しない。
accepted済み過去PR番号・確定commit等の恒久的な事実参照は許す。
手順の条件分岐・禁止例と歴史Decisionは、現在状態の主張と区別する。

### B. CURRENT_WORK Responsibility Rule

CURRENT_WORKは再開案内に限定し、formal mainで成立する状態、完了工程、次の独立工程、
未解決の既知制約、停止条件、必要なRequired Decisionsを保持する。
open PR状態、current branch / head、CI待ち、Owner Acceptance待ち、merge予定、
一時的Task Context状態は保持しない。branch / head / PR / checksはGit / GitHub、
タスク固有状態はrepo外Task Contextを正本とする。詳細な実行結果はEvidenceへ置く。

### C. No Recursive Finalization

通常終了フローは次に固定する。

成果物作成 → tests → 正本文書をmerge後にも正しい形で同一PRへ含める →
mandatory technical gates → Owner Acceptance → merge → formal main確認 →
Validate → snapshot → read-only Verify → Task Context CLOSED → 終了。

merge commit、MERGED状態、CI結果はGitHub、post-merge Verify結果はTask Context / Evidenceを正本とする。
post-merge Verify成功だけをGitへ記録する追加PRや「前PRをmergeした結果を記録するPR」を通常工程にしない。
同一PRへ採用後の再開案内を含めることが正本化であり、成功記録の再正本化を要求しない。

### D. Decision Necessity Gate

新Decisionは恒久仕様、Safety / Risk方針、完成条件、Owner承認境界、Governance恒久ルール、
長期再利用する設計判断が変わった場合だけappend-onlyで追加する。
commit、push、PR作成、CI PASS、当該PRのOwner承認、merge、post-merge Verify成功、
Task Context CLOSEDだけでは追加しない。それに伴う実際の恒久判断変更は別に判断する。
今回のルールのような恒久判断にも、その候補PR番号・current head・短命承認状態を埋め込まない。

### E. Pre-Acceptance Counterfactual Merge Check

Owner Acceptance Summary作成前に、変更した全Git管理文書の差分と周辺文脈をread-onlyで読み、
「このheadを今mergeしたと仮定すると、直後にfalse / obsoleteになる記述がないか」を確認する。
現在状態、同一PRの予定・承認・採用主張、終了・次工程境界を確認し、手順の条件分岐や過去事実と区別する。
1件でも不成立ならPOST_MERGE_STABILITY_FAILでOwner Acceptanceへ進まず同一PR内で修正する。
修正後は必要なtests / gatesを現在headで再確認する。
PASS結果はGit外Evidence / Task Contextへ記録し、9項目Summaryの「確認済みEvidence」に
「Post-Merge Stability Check: PASS」を含める。Summary項目数・binding・承認境界は変更しない。

最小自動回帰はtests/test_governance_docs_contract.pyでCURRENT_WORK全文の明確なtransient markerを検出する。
再開案内へ短命履歴・禁止例を追加せず、必要な履歴はDECISION_LOG、ルール説明は本節へ置く。
一般語の「候補」「head」「PR」、accepted済み過去PR参照、次工程の別承認条件は禁止しない。
DECISION_LOG全体へ禁止語検査を適用しない。現在文書PASS、各marker差込みFAIL、stable text PASSを
mandatory tests.offlineの全pytestで実行する。意味全体の反実仮想確認はread-only reviewで補完する。
engine / manifest / schema / gate定義を拡張せず、正規表現PASSだけを本節の意味確認PASSに昇格しない。

### F. Formalization Loop Fuse

同一の独立成果物について、前の正本化 / closeout PRの状態を直すだけのdocs-only corrective PRを
2件目として提案する場合はFORMALIZATION_LOOP_DETECTEDで自動継続を止める。
最初のcloseout PRに続く補正PRを1件目と数え、その次の同目的補正PRを提案する前に発火させる。
単にPR番号が増えた場合や独立した実障害修正には適用せず、
同一成果物の正本化結果を記録・補正するだけの連鎖に限定する。

新PR作成前に、前PRがmerge後stableでなかった理由、volatile stateを書いた場所、
Git / Task Context / Evidenceの責務混同、新PRなしで正本から判断できるかを原因分析してOwnerへ報告する。
Owner報告後も同じ補正を自動再提案せず、原因解消と必要なscope判断を先に行う。

### G. Post-Merge Closure Rule

Owner承認済みPRのGitHub MERGED、最新formal main一致、Validate、snapshot、read-only Verifyが
成功し、新しい実障害・正本矛盾・恒久判断変更がなければTask ContextをCLOSEDにして終了する。
成功した事実をGit文書へ書くための次PR・新Decisionは作らない。
post-mergeで実不具合または正本矛盾を見つけた場合だけ、通常のbug / correctionとして別判断する。
恒久判断が変わった場合はDecision Necessity Gateを適用する。失敗・未確認をCLOSEDにしない。

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
