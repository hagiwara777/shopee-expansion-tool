# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

DECISION_LOG読込軽量化の設計・実装・検証（DEC-0088）。全Decision見出し一覧とRequired Decisionsを入口に関連DECを選択し、根拠不足・競合・置換不明時には検索範囲を広げ、最後に全文読込へ戻る開始手順をformal main候補にする。DECISION_LOGは完全な判断履歴のappend-only正本として維持する。

対象はAGENTS、RUNBOOK、CURRENT_WORK、PROJECT_ROADMAP、DECISION_LOGとGit管理外Task Context / snapshot / 検証Evidenceだけ。過去DECの削除・分割・書換え、製品コード、Safety、SLS、Mapper、Catalog Client、secret処理、governance/state.json、Governance Config / gate / verifier、protected capability、policy検査、approval boundaryを変更しない。

## Required Decisions

現在の単一作業の必須本文参照。これだけを盲目的に信頼せず、毎回全見出し一覧と照合し、RUNBOOK「Decision読込」で関連DEC・参照元・後続の置換判断を追加確認する。

- DEC-0072 / DEC-0073 — 正本・信頼契約、mandatory technical gateとformal main最終受入の境界。
- DEC-0081 — SG offline成果と未受入のproduction / operation境界。
- DEC-0084 / DEC-0085 / DEC-0086 — 現行共通認証source、PH Bridge完了事実、既知制約と後続工程の境界。
- DEC-0087 / DEC-0088 — AGENTS整理の既存契約と、今回置換する読込義務・工程順。

## 確認済みの前工程

AGENTS軽量化はPR #90でformal mainへ統合済み。Google Sheet Access Token Source Minimum BetaはPR #88、PH Access Token Bridge自動同期Minimum BetaはPR #89で統合済み。
PH Bridgeの5分トリガー、自動同期2回、shop_id binding、元表とのToken一致、既存Sourceのread-only取得は前工程で確認済みであり、本タスクでlive再実行はしない。Bridge全面書込み失敗時に旧token消去を保証できない既知制約を保持する。PR #86はDraft・未merge候補として分離し、既存文書上のruntime OFFを変更しない。

## 検証・次の単一作業

既存policy検査、PowerShell 5.1 / 7のGovernance Validate、offline全体1,445件はPASS。過去87 DECの不変性、DEC-0088のみの追記、参照ID・文書間整合、追加差分のsecret混入確認も完了した。snapshotのlocal-validationはCONTINUE。本書更新後およびcommit後に再生成・検証する。CI / mandatory gateと対象bindingの最新結果はTask Context、Git/GitHub、Git管理外Evidenceを参照し、未実行をPASSとして記録しない。

次の単一作業は本変更のformal main最終受入。local commit、push、Draft PR / CI確認を通常開発承認内で進め、mandatory technical gates完了後に現在対象のOwner Acceptance Summaryを提示し、WAITING_APPROVALで停止する。Ownerの明示的最終承認なしにmerge / deployしない。

## 現在の工程境界

AGENTS軽量化 完了 → DECISION_LOG読込軽量化 → marketplace-neutral ShopeeCatalogClient → SG production Category source identity → 後続SG工程。Catalog Clientは後続の別scope・開始承認とし、今回着手しない。SG production Category調査を中止せず、共通Catalog Clientの後に再開する。

PHはACTIVE / ALLOWED、SG operationはINACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTEDを維持する。`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDのまま保護する。SG Category確定後も`listing_ready=false`、SG export / handoff停止を維持する。

実SG production Category catalogのsource identity、実catalogでの実商品受入、SG live OpenAI API、SG Brand、SG SLS runtime、listing_ready、handoff、deploy、自動Category確定、自動出品は未受入。Candidate 15列、Prelisting Gate契約、DB schemaも変更しない。live API、credential操作、runtime切替を今回の承認に含めない。

## 再開・rollback

再開時はGit/GitHubでformal mainと本変更PRを観測し、AGENTS、RUNBOOKの該当手順、PROJECT_ROADMAP、governance/state.jsonを確認し、Required Decisionsと全見出し一覧から必要DECを読む。branch / HEADを本書へ二重入力しない。文書差分の通常revertで戻せる。製品、credential、State、PR #86の変更を伴わない。DECISION_LOGの訂正・方針撤回は新規DECを追記し、履歴を削除しない。
