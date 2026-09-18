# CURRENT WORK

本書は再開案内。長寿命の承認済み状態はgovernance/state.json、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

SLS Market Category Rules Minimum Beta — Technical Design V0.3に基づく実装・技術検証候補。
DESIGN_GATE_PASSに基づき、7市場asset、PH限定runtime、独立SLS state、pure ready、refresh/export境界、UI停止理由とfail-closedを実装する。同一Codexタスクでtests、Draft PR、CI/read-only reviewまで進める。

前工程SLS Shared Battery Fail-Safe v0.1はPR #76で正式受入済み。今回のCategory ALLOWでBattery、Community NG、own penalty、PH/SG Safetyを解除しない。

## 次の単一作業・停止条件

現在候補のmandatory technical gatesとEvidence bindingを確認し、Owner Acceptance Summaryを提示してWAITING_OWNER_ACCEPTANCEで停止する。formal mainへmergeしない。CI結果・技術検収は現在のPR/checksと生成Evidenceを確認し、本書の記載だけでPASSと判断しない。

Candidate15列、Prelisting Gate契約、DB schemaは不変。SG/MY/TW/VN/TH/BR runtime、live Shopee/Keepa/OpenAI API、有料API、自動出品、deployは対象外。DB migration、公開contract変更、既存Safetyの緩和、大規模Mapper再設計が必要になればBLOCKING_IMPLEMENTATION_FINDINGとして戻す。

## 再開・更新・rollback

Git root/remote/HEAD/clean state、AGENTS.md、Governance State/Config、DEC-0076、asset READMEを確認する。source identityはsource-lock.jsonと外部原本hashで確認し、推測再生成しない。

Source更新はapp stop→validated code/assets更新→restart→new session。hot swapは対象外。rollbackはSLS追加単位の通常revertとrestart/new sessionで行い、既存Category/Brand DBと前工程Safetyを維持する。詳細はguardrails/sls_market_categories/README.mdを参照。
