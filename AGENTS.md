# Codex Repository Rules

AGENTSには毎タスク必須の恒久原則、[RUNBOOK](docs/RUNBOOK_CHATGPT_CODEX.md)には詳細手順を置く。
参照化は任意化ではない。下記の実行時点で該当手順を必ず読み、適用する。

## 正式Repository・正本

- 正式Repositoryは `hagiwara777/shopee-expansion-tool` とその現在のclone。古いprojectや一時コピーを推測で使わない。
- Gitはbranch / HEAD / tree / 差分、`governance/state.json`は長寿命の承認済み状態、
  repo外Task Contextはタスク固有状態の正本。Stateにactive task、branch、HEAD、test resultを置かない。
- `docs/CURRENT_WORK.md`は再開案内。branch / HEAD / tree / 差分を二重入力しない。
  判断理由は`docs/DECISION_LOG.md`、長期工程は`docs/PROJECT_ROADMAP.md`を正本とする。
- 会話、handoff、README、snapshotを現在の正式状態の代替正本にしない。
  snapshotと`outputs/governance/`は派生物で、snapshotを手動編集・commitしない。

## 開始チェック・作業範囲

- 開始時に `git status`、`git rev-parse --show-toplevel`、`git log -1 --oneline` を実行する。
  root、remote、branch、HEAD、main、origin/main、clean / dirtyを実測し、正式状態と照合する。
- 本書と適用する下位AGENTSを全文読み、CURRENT_WORK、PROJECT_ROADMAPを読む。
  DECISION_LOGは全Decision見出し一覧とCURRENT_WORKのRequired Decisionsを確認し、
  必須DEC・今回のmarketplace / module / phase関連DECの本文を読む。選択・検索拡大・全文読込への
  fallbackはRUNBOOK「Decision読込」を必ず適用する。Required Decisionsだけで対象を限定しない。
  利用方法・機能仕様に関係する場合はREADMEも読む。
- 変更対象・禁止範囲を編集前に特定し、振舞い・scope変更は事前に報告する。
  作業票と再開案内のmarketplace / module / phase、およびGit / Task Contextの作業対象が
  不一致なら推測で進めず停止する。停止条件に反して保留工程を再開しない。
- dirtyなworktreeのユーザー変更・未追跡ファイルを無断整理・破棄・上書きしない。
  dirtyのままbranchを切り替えず、無関係な変更をstage / commitしない。
- 開始時はRUNBOOK「開始・実行」のValidate・snapshot生成を必ず行う。
  Governance操作前は「正本」「Trust Anchor」「Task Context」「開始・実行」を適用する。

## 軽量開発運用 v1・承認境界

- CodexはGit・正本を確認し技術判断と検証を担う。GPTは必須の伝言役または承認者にしない。
  Ownerへ技術方式の選択を求めず、事業上の違いと確認結果を平易に説明する。
- 読み取り・scope内local編集・testはユーザー変更とsecretを保護し、小さく可逆に進める。
  関連検証成功、差分・secret確認後の範囲内local commitは可能。
  目的とscopeが明確な通常開発承認は、local編集・test・commit、push、Draft PR、
  CI / checks確認、read-only reviewを含む。push / Draft PRだけで追加承認を求めない。
- formal mainへのmergeは別境界。mandatory technical gates、現在対象のOwner Acceptance Summary、
  Ownerの明示的最終承認を必要とする。head、scope、主要リスク、protected capabilityへの影響、
  Summary bindingが変われば再承認する。technical gate完了前にOwner Acceptanceを要求しない。
- 費用・有料API、live API / 実商品（read-onlyも含む）、外部live書込み、復元不能な削除・上書き・移行、
  deploy、GitHub repository設定・branch protection / ruleset・Actions secret / variable、
  実環境Trust Anchor、credential / secret操作、大幅な目的・責務・満足条件変更は別の明示承認を要する。
- `--force` / `--force-with-lease`は原則禁止。対象branchと具体操作への明示承認なしに例外化しない。
  force pushやdirty resetを標準復旧手順にせず、承認範囲外のpush・正本化を自動実行しない。
- WORK_BRIEFは全作業必須ではない。変更前にRUNBOOK「軽量開発運用v1との互換契約」の利用条件を適用する。
  project名・chat名・worktree絶対pathを安全gateにしない。

## Governance・protected capability・秘密情報

- HOLD / HARD_STOP、Protected Capability Gate、mandatory technical gateを無効化・迂回・緩和しない。
  Task Contextで既存gate、Global State、保護capabilityを削除・緩和しない。
- bootstrap repository identityはOwner受入済みrepo外Trust Anchorだけを信頼し、
  repo / remote / State / Config / Task Contextの自己申告を期待値にしない。
- 変更分類はGOVERNANCE_ONLY / MARKET_LOCAL / SHARED_CORE。
  未知path・混合・分類不能はSHARED_COREとし、`ph.beta.operation`と`sg.safety.baseline`を保護する。
  両ACCEPTED capabilityを弱めず、SHARED_COREまたは未知変更では両方の保護gateを適用する。
- mandatory checksはbranch protectionと独立して評価する。欠落、pending、skipped、neutral、
  古いhead、provider不在をPASSにしない。formal merge前はRUNBOOK「Evidence」「Formal acceptance」を適用する。
- Gitに`.env`、`.env.*`、cache DB、`outputs/`、`.venv/`、`__pycache__/`、
  `.pytest_cache/`、`.pytest_tmp/`、`.agents/`、`.codex/`、`work/`を追加しない。
  API key、token、passwordをsource・README・testsへ埋め込まない。
- secret本文をGit・docs・log・UI・snapshot・Evidenceへ出さず、管理文書に商品CSV本文・個人情報を含めない。
  共有出力には絶対path、username、hostname、credential、raw exception / command output、
  認証付きURLを含めない。共有前はRUNBOOK「Shareable output」を適用する。

## Component boundary・検証

- Product Finder、Guardrail、ASIN Resolverの責務を分離し、承認済みscope変更なしに統合・拡張しない。
- 変更後は実行可能な限りpytestを行う。実Keepa APIと外部APIを使うE2Eは明示承認なしに実行しない。
  Browser E2E前はRUNBOOK「Browser E2E」を適用し、upload確認とdecision実行を別段階にする。
- ユーザー提示、Git観測、test確認、未確認・仮定を区別し、未実行をPASSにしない。
  mock、実API、実データ、Owner受入は別の確認。Evidenceのprovenanceと対象bindingを検証し、
  過去結果をVer2 TESTとして捏造しない。移行済み受入はLEGACY_ACCEPTANCEとする。
- 危険性に直接関係しない不明事項は仮定を明記して可逆な範囲を続行できる。
  外部影響、復元不能性、責務変更に関わる不明事項では停止する。明示的な停止条件は優先する。

## タスク境界・正本化

- 同じ原因・受入条件の問題は同じタスクで継続できる。独立問題、目的・受入条件・module・責務変更、
  長大化では分割を検討し、RUNBOOK「タスク境界・正本化」の見直し条件を適用する。
- handoffより先に正本化する。終了・handoff時は同節のチェックリストを必ず実施する。
  正式状態、確認済み・未解決事項、次の単一作業、停止条件を過去会話なしで再開可能にする。
- 実作業状態変更時はCURRENT_WORK、判断変更時はDECISION_LOGへ新IDで追記（既存entryを書き換えない）、
  工程順変更時はPROJECT_ROADMAP、恒久ルール変更時はAGENTS等を更新する。詳細を重複複製しない。
- CURRENT_WORKまたはDECISION_LOG更新時はRUNBOOK「開始・実行」に従いsnapshotを再生成・検証する。
  テスト失敗、無関係なdirty変更、snapshot生成失敗、正本矛盾で正本化できない場合は、
  阻害要因を明示して停止し完了扱いにしない。復旧時はRUNBOOK「Rollback」を適用する。
