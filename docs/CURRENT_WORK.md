# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

ShopeeCatalogClientのmarketplace-neutral化（DEC-0089）。PR #91はformal mainへ統合済み。現在の作業はPH/SGを明示bindする共通Category / Attribute / Brand client、PH caller更新、offline回帰、Governance mandatory gates、Draft PR / CI確認まで進め、formal main merge前にOwner Acceptanceを待つ。

## Required Decisions

- DEC-0072 / DEC-0073 — Governance正本・protected capability・通常開発とformal mergeの承認境界。
- DEC-0081 / DEC-0082 — SG offline成果と共通認証・Catalog基盤の工程境界。
- DEC-0084 / DEC-0085 / DEC-0086 — 共通Access Token Source、Bridge先行検証、既知freshness制約。
- DEC-0087 / DEC-0088 — 開始・読込・正本化手順。
- DEC-0089 — 今回のClient binding、認証優先順位、市場別停止範囲。

## 確認済みの前工程

PR #88のGoogle Sheet Access Token Source、PR #89のPH Bridge、PR #90のAGENTS軽量化、PR #91のDECISION_LOG読込軽量化はformal mainへ統合済み。PH Bridgeのlive結果を本作業で再実行しない。PR #86はDraft・runtime OFF・未merge候補として分離する。

## 今回の境界と次の単一作業

PH Category MapperのCategory / Brand / Attribute契約を維持する。SGはClient contractとfake requestによるoffline確認のみ。SG production Catalog API、SG source identity受入、SG Mapper live接続、SG Brand / SLS runtime、listing_ready、handoff、deploy、operation ACTIVE化は含めない。MY / THはCatalog Client request前にfail closedし、operation INACTIVE / development_policy NOT_STARTEDを維持する。Candidate 15列、Prelisting Gate、DB schema、Safety、SLS、Resolver、Expansion、governance/state.json、protected capabilityを変更しない。

対象offline回帰96件、protected PH / SG回帰574件、PowerShell 5.1 / 7のGovernance Validate、Python構文、secret混入、diff checkを確認済み。ローカル全体pytestはStreamlit 1.44.1が既存`width`引数に未対応のためUI 42件が失敗し、1,417件が成功した。Draft PRのPython 3.12 / requirements環境ではoffline全体とGovernance mandatory 6 gateが成功した。GitHub CI Evidenceを現在対象へbindingしたformal-acceptance Verifierはtechnical requirementsすべてPASS、`owner_acceptance_ready=true`、HOLD理由は`OWNER_ACCEPTANCE_REQUIRED`のみを返した。文書更新後の新headでもCI Evidenceを再確認し、Owner明示的最終承認までformal main mergeせずWAITING_APPROVALとする。

次の単一作業は別scopeのSG production Category catalog source identity確認。live API・credential操作には別明示承認を要する。

## 再開・rollback

再開時はGit/GitHubの実状態、AGENTS、RUNBOOK、PROJECT_ROADMAP、governance/state.json、本書のRequired Decisionsと全Decision見出しを確認する。今回の差分は通常のcode/docs revertで戻せる。DB migration、credential変更、State変更、force pushやdirty resetを伴わない。
