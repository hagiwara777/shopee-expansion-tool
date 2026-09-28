# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

SG production Category catalog import offline preflightの最小実装候補とfixture / tmp DB検証を完了した（DEC-0094）。normalized Category全件からSG正式6列CSVを決定的に生成し、全件validation後に既存SG-only transactional replaceへ渡す経路を追加した。formal mainへの採用・実production catalog受入はまだ行っていない。

OwnerがBridgeのSG Access Token更新後に新しいread-only GET 1回を明示承認した。SG shop binding MATCH / Google Sheet Source AVAILABLEでproduction Category GETはHTTP 200、現行get_categories()で全2,285件を正規化・Git除外保存した（DEC-0096）。PR #98の決定的6列catalog、全件validation、tmp DBでSG-only replaceを検証し、判定は`IMPORT_PREFLIGHT_PASS`。root 31件 / leaf 1,962件でDEC-0093参考件数との差は0。前回失敗（DEC-0095）は履歴として維持し、今回のAPIは1 request / retry 0。formal main merge・実運用DB replace・production catalog acceptanceは行わずOwner判断待ちで停止する。

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
- DEC-0096 — 更新後認証で新たに承認されたGET 1回とnormalized全件のoffline / tmp DB検証PASS。merge・実運用受入はOwner判断待ち。
- DEC-0097 — Ownerがpreflight PASSを受理し、成功結果の正本化と同じPRの公開・検証を承認。追加production API・mergeは含めない。

## 確認済みと停止境界

SG suiteは63 passed、offline全体は1,515 passed、PH/SG protected回帰は598 passed。SG pathは親pathと自身nameの完全一致を要求し、余分な中間segmentを拒否する。tmp DBで不正入力時のSG不変、SG完全置換、古いSG ID削除、PH不変、schema不変、INSERT失敗時rollbackを確認した。既存testsで保存済みmappingのcurrent ID / path / leaf再validationとlisting_ready=falseを確認した。

今回のproduction Category GETは1 request、retryは0（DEC-0095の以前の1 requestとは別承認）。全件でduplicate / empty name / missing parent / cycle / root到達不能 / path不整合 / leaf不整合はすべて0。tmp DBでPH catalog / PH sync state不変、schema不変、SG ID集合の全件一致、旧SG ID消失を確認した。Windowsのtmp DB cleanup時PermissionErrorは検証helperだけでconnection close / GCを明示して解消し、保存済みnormalized全件からoffline再検証した。追加APIは0、製品codeの修正はない。Git除外Evidenceは`outputs/sg-production-import-preflight-20260928-owner-recheck/`のnormalized-categories.json、provenance.json、request-attempt.json、verification-report.json（初回cleanup失敗記録）、offline-revalidation-report.json（最終PASS）。Google Bridge変更、credential表示・保存・変更、raw response保存、Brand / Attribute API、実運用DB replace、migration、実商品受入、SLS runtime、handoff、deploy、operation ACTIVE化、自動確定・出品は実行していない。Client、shared AI Core、Store、Safety、Candidate 15列、Prelisting Gate、governance/state.jsonは変更しない。既存dirty PH作業ツリーのファイルを編集・整理していない。

## 次の単一作業・rollback

OwnerはIMPORT_PREFLIGHT_PASSを受理し、成功結果の正本化、関連tests / Governance再検証、secret / scope確認、同じbranchへのcommit / push、PR #98更新、現在headのCI / mandatory gates確認とread-only reviewを承認した（DEC-0097）。今回の公開工程でproduction APIを追加実行しない。PR #98はDraftを維持し、Git / GitHubの現在headとrepo外Task Contextに検証結果をbindする。次の単一操作は、公開結果を確認したOwnerによるformal main受入判断。現在対象のOwner Acceptance Summaryと明示的な最終merge承認まで停止する。実運用DB replace・実catalog / 実商品Category acceptance・deploy・SG operation ACTIVE化・listing_ready=trueは別の受入範囲とし、今回PASSまたは公開承認から自動昇格しない。

rollbackは今回のSG-local code / tests / docs差分の通常revert。DB migration、State、credential、PH運用の変更を伴わない。force pushとdirty resetは行わない。
