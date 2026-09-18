# CURRENT WORK

本書は再開案内。長寿命の承認済み状態はgovernance/state.json、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

SLS Market Category Rules Minimum BetaはPR #78でformal mainへ統合し、Owner Acceptanceまで完了した。PH runtimeはcanonical taxonomyとPH assetだけを読む。SLS resultはCategory / asset versionへbindされ、CURRENTなALLOWだけがready、groups CSV、listing TXTへ進む。

Category / Brand確認済みでもSLS REVIEW、EXCLUDE、UNAVAILABLE、UNCHECKED、binding不一致は出品準備完了にならない。Battery、Community NG、own penalty、PH / SG SafetyはCategory ALLOWで解除しない。DB migration、Candidate15列、Prelisting Gate contractは不変である。

## 次の単一作業・停止条件

この工程は完了した。次工程は独立した新規Codexタスクで、Ownerが目的とscopeを定義して開始する。SLS source更新、REVIEW override、非PH runtime、SG Category / Brand / Handoff、live API、自動出品、deployはこの完了によって開始許可されない。

## 再開・更新・rollback

新規タスクではformal main `5079795fd1eb7a4ae1940852b76e2bd2315e0006`、DEC-0076、DEC-0077、`guardrails/sls_market_categories/README.md`を先に確認する。source identityはsource-lock.jsonと外部原本hashで確認し、推測再生成しない。

Source更新はapp stop→validated code/assets更新→restart→new session。hot swapは対象外。rollbackはSLS追加単位の通常revertとrestart/new sessionで行い、既存Category/Brand DBと前工程Safetyを維持する。
