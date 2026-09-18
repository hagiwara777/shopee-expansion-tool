# CURRENT WORK

本書は再開案内。長寿命の承認済み状態はgovernance/state.json、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

SG Category Mapper Minimum BetaはDESIGN_GATE PASSをOwnerが受入済みであり、製品実装前のSG開発再開状態を正本化している。SG operationはINACTIVEを維持し、SG development_policyだけをALLOWEDへ戻す。今回許可するのはSG Category Mapper Minimum Betaの開発再開であり、実運用開始ではない。

PH runtimeは引き続きACTIVE / ALLOWEDであり、`ph.beta.operation`をprotected capabilityとして保護する。`sg.safety.baseline`はACCEPTEDのまま保護し、Battery、Community NG、own penalty、PH / SG Safety、SLS停止状態はCategoryやBrandの確認で解除しない。DB migration、Candidate15列、Prelisting Gate contractは不変である。

## 次の単一作業・停止条件

この工程の完了後、formal mainへ統合された現在headにOwner Acceptanceを得てから、同じCodexタスクを継続してSG Category Mapper Minimum Betaの最小製品実装へ進む。Brand、SG SLS runtime、`listing_ready`、handoff、live API、deploy、自動Category確定、自動出品は今回の正本化では未承認のままとする。

## 再開・更新・rollback

再開時はGitでcurrent formal mainを確認し、DEC-0078、governance/state.json、SG Category Mapper Minimum Beta設計Gate結果、PR #78の製品merge commit `5079795fd1eb7a4ae1940852b76e2bd2315e0006`、DEC-0076、DEC-0077、`guardrails/sls_market_categories/README.md`を先に確認する。source identityはsource-lock.jsonと外部原本hashで確認し、推測再生成しない。

rollbackは今回のgovernance/docs/test差分を通常revertし、SGをINACTIVE / PAUSEDへ戻して`pause-sg-product-development`停止条件を復元する。既存PH operation、既存Category/Brand DB、SLS資産、前工程Safetyは維持する。
