# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

AGENTS.md軽量化実装・検証（DEC-0087）。Ownerが監査案を承認し、同じCodexタスクで文書編集、検証、local commit、push、Draft PR、CI確認までを通常開発承認した。AGENTSには毎タスク必須の恒久原則、RUNBOOKには詳細手順を置き、実行時点の必須参照を残す。既存policy検査の6文言と開始時の正本文書読込義務を維持する。

対象はAGENTS、RUNBOOK、CURRENT_WORK、PROJECT_ROADMAP、DECISION_LOGと必要なGit管理外snapshot派生物だけ。製品コード、Safety、SLS、Mapper、Catalog Client、secret処理、governance/state.json、Governance Config / gate / verifier、protected capability、policy検査、approval boundaryを変更しない。

## 確認済みの前工程

Google Sheet Access Token Source Minimum BetaはPR #88、PH Access Token Bridge自動同期Minimum BetaはPR #89でformal mainへ統合済み。PR #89のmerge承認待ちは解消済み。Sourceの設計・認証優先順位はDEC-0084、Bridge同期はDEC-0085、PH live受入はDEC-0086を参照する。

PH Bridgeの5分トリガー、自動同期2回、shop_id binding、元表とのToken一致、既存Sourceのread-only取得は前工程で確認済み。本タスクでlive再実行はしない。Bridge全面書込み失敗時に旧token消去を保証できない既知制約を保持する。PR #86はDraft・未merge候補として分離し、既存文書上のruntime OFFを変更しない。

## 検証・次の単一作業

文書軽量化の実装と、既存policy検査、PowerShell 5.1 / 7のGovernance Validate、既存venvのoffline全体1,445件、文書間整合・secret混入確認は完了した。最初のlocal実行ではglobal Streamlitの旧版とvenvのgoogle-auth不足を検出し、既存venvとrequirements指定依存で再検証した。製品コード・requirementsは変更していない。snapshotは本書更新後に再生成・検証する。CI / mandatory gateと対象bindingの最新結果はTask Context、Git/GitHub、Git管理外Evidenceを参照し、未実行をPASSとして記録しない。

次の単一作業は本変更のformal main最終受入。local commit、push、Draft PR / CI確認を通常開発承認内で進め、mandatory technical gates完了後に現在対象のOwner Acceptance Summaryを提示し、WAITING_APPROVALで停止する。Ownerの明示的最終承認なしにmerge / deployしない。

## 現在の工程境界

AGENTS.md軽量化 → marketplace-neutral ShopeeCatalogClient → SG production Category source identity → 後続SG工程。Catalog Clientは後続の別scope・開始承認とし、今回着手しない。SG production Category調査を中止せず、共通Catalog Clientの後に再開する。

PHはACTIVE / ALLOWED、SG operationはINACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTEDを維持する。`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDのまま保護する。SG Category確定後も`listing_ready=false`、SG export / handoff停止を維持する。

実SG production Category catalogのsource identity、実catalogでの実商品受入、SG live OpenAI API、SG Brand、SG SLS runtime、listing_ready、handoff、deploy、自動Category確定、自動出品は未受入。Candidate 15列、Prelisting Gate契約、DB schemaも変更しない。live API、credential操作、runtime切替を今回の承認に含めない。

## 再開・rollback

再開時はGit/GitHubでformal mainと本変更PRを観測し、AGENTS、RUNBOOKの該当手順、DEC-0072 / DEC-0073 / DEC-0084〜DEC-0087、PROJECT_ROADMAP、governance/state.jsonを確認する。branch / HEADを本書へ二重入力しない。文書差分の通常revertで戻せる。製品、credential、State、PR #86の変更を伴わない。
