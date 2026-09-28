# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

SG production Category catalog importのoffline実装とIMPORT_PREFLIGHT_PASS検証事実をPR #98でformal mainへ正式採用した（DEC-0098）。Ownerが現在headとOwner Acceptance Summaryを最終承認し、既存DPAPI保護鍵とTrust Anchor公開鍵の一致確認、GitHub承認コメント取得、fresh署名付きOwner Evidence、mandatory 6 gateのformal Verify CONTINUEを得て通常mergeした。追加production API、実運用DB・Bridge・credential変更、deployは行っていない。SG operationはINACTIVEを維持する。

Owner受理済みのpreflightはnormalized全2,285件 / root 31 / leaf 1,962件、全不整合0、決定的6列catalog、全件validation、tmp DBでSG-only replace、旧SG ID削除、PH / schema不変までの成立を意味する（DEC-0096）。過去STOPとhelper cleanup補正の履歴を保持し、実catalog・実商品受入や実運用DB importへ自動昇格しない。

## Required Decisions

- DEC-0072 / DEC-0073 — Governance正本、protected capability、通常開発とformal mergeの承認境界。
- DEC-0079 / DEC-0081 — SG全件validation、SG-only replace、保存済みmappingのcurrent catalog再validation、listing_ready=false。
- DEC-0082 / DEC-0084 / DEC-0085 / DEC-0086 — 共通Catalog / Access Token Source、Bridge、既知freshness制約。
- DEC-0088 — Decisionの段階的読込とappend-only正本。
- DEC-0089 / DEC-0090 — PH/SG Catalog Client契約とformal main採用範囲。
- DEC-0091 / DEC-0092 — OwnerコメントEvidenceとTrust Anchor v1.1移行の承認境界。
- DEC-0093 — production source identity PASSの意味、2,285件の確認事実、未受入境界。
- DEC-0094 — offline import最小経路、fixture検証、production全件データ不足によるSTOP。
- DEC-0095 — 前回承認のproduction GET失敗とretryせず停止した履歴。
- DEC-0096 — 更新後認証で取得したnormalized全件のoffline / tmp DB検証PASSと実運用受入との境界。
- DEC-0097 — preflight成功結果の正本化・公開と当時のmerge除外境界。
- DEC-0098 — 現在対象へのOwner最終承認、fresh署名付きEvidenceとformal Verify CONTINUE、PR #98正式merge、merge後のread-only検証。

## 確認済みと停止境界

SG suiteは63 passed、offline全体は1,515 passed、PH/SG protected回帰は598 passed。SG pathは親pathと自身nameの完全一致を要求し、余分な中間segmentを拒否する。tmp DBで不正入力時のSG不変、SG完全置換、古いSG ID削除、PH不変、schema不変、INSERT失敗時rollbackを確認した。既存testsで保存済みmappingのcurrent ID / path / leaf再validationとlisting_ready=falseを確認した。

今回のproduction Category GETは1 request、retryは0（DEC-0095の以前の1 requestとは別承認）。全件でduplicate / empty name / missing parent / cycle / root到達不能 / path不整合 / leaf不整合はすべて0。tmp DBでPH catalog / PH sync state不変、schema不変、SG ID集合の全件一致、旧SG ID消失を確認した。Windowsのtmp DB cleanup時PermissionErrorは検証helperだけでconnection close / GCを明示して解消し、保存済みnormalized全件からoffline再検証した。追加APIは0、製品codeの修正はない。Git除外Evidenceは`outputs/sg-production-import-preflight-20260928-owner-recheck/`のnormalized-categories.json、provenance.json、request-attempt.json、verification-report.json（初回cleanup失敗記録）、offline-revalidation-report.json（最終PASS）。Google Bridge変更、credential表示・保存・変更、raw response保存、Brand / Attribute API、実運用DB replace、migration、実商品受入、SLS runtime、handoff、deploy、operation ACTIVE化、自動確定・出品は実行していない。Client、shared AI Core、Store、Safety、Candidate 15列、Prelisting Gate、governance/state.jsonは変更しない。既存dirty PH作業ツリーのファイルを編集・整理していない。

## 次の単一作業・rollback

現在の単一作業は、正式受入記録（CURRENT_WORK / DEC-0098）を別のdocs-only PRとして公開し、technical gatesと現在対象のOwner Acceptance成立後にformal mainへ採用する最終正本化。PR #98のaccepted headと採用範囲は変更しない。この文書PRのmerge後、formal main確認・Validate・snapshot・read-only Verifyを完了して同じCodexタスクを終了する。終了後の次の単一作業は、SG実catalog・実商品受入のscope定義。実運用DB replace・SG operation ACTIVE化・listing_ready=true・deployは未実施であり、次工程は別タスク・別Owner承認とtechnical gatesを必要とする。

rollbackは今回のSG-local code / tests / docs差分の通常revert。DB migration、State、credential、PH運用の変更を伴わない。force pushとdirty resetは行わない。
