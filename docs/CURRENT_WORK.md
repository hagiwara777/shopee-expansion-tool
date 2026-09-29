# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch / HEAD / PR / checksはGit / GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の正式状態

SG実catalog・6実商品のCategory acceptanceはPR #100でformal mainへ正式採用済み（DEC-0103）。Ownerの現在headとOwner Acceptance Summaryへの最終承認、fresh署名付きOwner Evidence、mandatory technical gates 6 / 6 PASS、formal Verify CONTINUEを確認して通常mergeした。merge後のformal main / PR MERGED / accepted内容一致、PowerShell 5.1 / 7 Validate、snapshot、read-only Verify CONTINUEまで確認済み。PR #100のmerge対象と受入結果を再実行・再承認する工程には戻らない。

SG Brand / No Brand Minimum Betaのoffline最小実装をPR #103でformal mainへ正式採用した（DEC-0105）。通常merge commitは`c1cfab9fef0283532fd3bf5968ea75c438179233`、accepted headは`7928086a2e870018943d9483acdc1684fc439fdf`で、main treeとaccepted head treeの一致を確認した。現在headにbindしたCI mandatory 6 / 6 PASSとfresh署名付きOwner Evidence、formal Verify CONTINUE後にmergeし、PR MERGEDを確認した。PowerShell 5.1 / 7 Validate、snapshot生成、read-only Verify CONTINUEもmerge後に確認済み。

実装はstrict opt-in raw検証、最大10 pageの完全取得、SG Category単位のtransactional replace、client / shop / request / run / session binding、session currentとDB digest再照合、商品単位No Brand保存、real Brand alias再validationを含む。No Brand tableは隔離acceptance DBへの明示初期化だけで、通常Store初期化へ追加しない。offline suiteはlocal 1,615 passed、CI 1,614 passed / 1 skipped、PH / SG protected回帰598 passed。skipは既存のformal local Benchmark artifacts未配置による条件。

正式採用はoffline実装だけであり、SG Minimum Beta全体やlive運用の受入ではない。production Shopee / Bridge request、実商品Brand / No Brand受入、production DB schema適用は未実施。SG operation INACTIVE、`listing_ready=false`、export / handoff閉鎖を維持し、Attribute / SLS runtime、deploy、自動確定・出品は未実施。responseにmarketplace / Category echoがないため、server内部の別Category誤応答をresponse内容だけから独立検出できるとは主張しない。Client marketplace / shop、request Category、run、sessionのbindingを取得provenanceとして扱う。

PR #103はOwnerのoffline限定最終承認で正式採用済み。live API、実商品受入、production DB / schema、Attribute / SLS、listing_ready、export / handoff、deploy、SG ACTIVE化、自動確定・出品は今回の承認範囲外であり、別途明示承認なしに実施しない。DEC-0104の設計本文は変更せず、正式採用結果はappend-onlyのDEC-0105に記録する。

## Required Decisions

- DEC-0105 — SG Brand offline実装のPR #103正式採用、merge後検証、live工程の別承認境界。
- DEC-0104 — SG Brand設計と商品単位No Brand保存、strict current取得・再validation、実装 / liveの境界。設計履歴は編集せずDEC-0105から参照する。
- DEC-0103 — PR #100の正式採用・merge後検証、文書の最終正本化、次工程SG Brandを新規タスクへ分離。
- DEC-0102 — 6件人間確認・保存・再利用・current再validationと標本制約。記録時点のPASS候補はDEC-0103で正式採用済み。
- DEC-0101 — 同一brand許容と用途 / familyの多様性による6件選定。
- DEC-0099 / DEC-0100 — 受入設計と旧brand条件によるSTOP履歴。現行scopeはDEC-0101を適用。
- DEC-0096 / DEC-0098 — production catalog preflightとSG import offline成果の正式採用。
- DEC-0079 / DEC-0080 / DEC-0081 — SG商品単位の人間確認、保存mappingのcurrent再validation、live OpenAI閉鎖、listing_ready=false。
- DEC-0082 / DEC-0084 / DEC-0085 / DEC-0086 — 共通Catalog / Access Token Source、Bridge、認証責務と既知freshness制約。SG Brand設計でも既存責務を変更しない。
- DEC-0089 / DEC-0090 — PH / SG共通Catalog Clientのoffline contractと正式採用範囲。
- DEC-0093 — SG production Category source identityの確認範囲。
- DEC-0072 / DEC-0073 / DEC-0088 — Governance、formal merge承認、Decision読込とappend-only正本。
- DEC-0091 / DEC-0092 — OwnerコメントEvidence、freshness、Trust Anchor移行の限定手順。

## 正式採用したCategory acceptance結果

- accepted production catalogは全2,285件 / root31 / leaf1,962、bindingと全件validation成立。
- 元Candidate / Gate auditとの出所一致を確認した実Gate46件から、セル改変なしで用途の異なる6familyを選定した。
- 全6件を人間レビューし、CONFIRMED 6 / REVIEW 0。人間確定結果は5 root / 5 Category IDへ分散した。
- 新ブラウザsessionへ同じ入力を再読込し、保存済みCategoryの再利用6件、current ID / path / leaf一致6件を確認した。
- 全14条件成立、全件listing_ready=false、SG export / handoff閉鎖。実運用DB、PH operation / data、製品code / tests / State / Safetyは不変。
- production API再取得0、Bridge / credential変更、Brand / Attribute / SLS runtime、ready / deploy / SG ACTIVE化、自動確定・出品は未実行。
- 同一brandの6用途向け保護ケース標本であり、広い商品群の精度保証やSG実運用完成を意味しない。
- Git外Evidenceは`outputs/sg-real-product-category-acceptance/reselection-v2/`のacceptance-result.json、formal-adoption-result.json、選定 / 保存 / 再読込記録と、`outputs/governance/accepted-pr100/`のSummary / Owner Evidence / formal Verify。過去STOP・request試行・production Evidenceを保持し、商品名 / ASIN一覧 / raw catalog / DB / wrapper / secret / snapshotをGitへ追加しない。

## 確認済み検証と履歴

PR #103の現在対象CIはmandatory 6 gateすべてPASS。offlineは1,614 passed / 1 skipped、PH / SG protected回帰は598 passed。skipはGit外のformal local Benchmark artifact未設置による条件で、job自体はSUCCESS。local offlineは1,615 passed。PR #103 merge後ValidateはPowerShell 5.1 / 7双方PASS、snapshot / read-only Verify CONTINUE。実商品Evidenceとoffline / synthetic testsを区別する。

PR #100のCategory acceptance CIは当時mandatory 6 gateすべてPASS、offline 1,514 passed / 1 skipped、protected 598 passed。merge後にPowerShell 5.1 / 7 Validate、snapshot / read-only Verify CONTINUEを確認済み。これはPR #100当時の記録であり、今回のPR #103検証結果と混同しない。

旧brand理由STOP（DEC-0100）、source改行hashの診断、fresh DBのPH seed期待値補正はDecisionとGit外Evidenceに保持する。旧未実施記録を現在の進捗へ混ぜず、DEC-0101のscope修正・DEC-0102の実行結果・DEC-0103の正式採用の順で読む。PR #98 / #99の前工程も再実行しない。

## 今後の承認境界

PR #103のoffline正式採用とmerge後文書正本化を本タスクの対象とする。production Brand API / Bridge、実商品Brand / No Brand受入、production DB / schema、Attribute / SLS runtime、`listing_ready=true`、export / handoff、deploy、SG ACTIVE化、自動確定・出品には、対象shop / Category allowlist / request予算 / retry方針 / Evidence / 隔離DB / 商品範囲を定義した別Owner承認を要する。過去Category GET承認は流用せず、PH operation / data / schemaとprotected capabilityを維持する。

## 終了とrollback

SG Brand offline実装のformal採用、merge後検証、append-only Decisionと管理文書の正本化を確認して本タスクを終了する。live API / 実商品受入やSG運用開始は本タスクの終了条件に含めない。

rollbackはoffline実装または状態説明文書の通常revert。実運用DBへschemaを適用していないためproduction migration / 復旧を伴わない。Decision撤回・訂正は新しい記録で残し、過去Decisionを編集・削除しない。PR #100の受入実行を再実行せず、実運用DB、PH、Bridge、credential、既存Evidenceを変更・削除しない。force push / dirty reset禁止。
