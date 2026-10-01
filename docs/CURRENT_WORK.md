# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch / HEAD / PR / checksはGit / GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

SG Minimum Beta完成判定（Roadmap Step 8）は正式採用・最終正本化を完了し、CLOSEDとする。PR #110で半自動完成線を採用し（DEC-0111 / DEC-0112）、PR #111でその採用結果とmerge後検証を4文書へ正式記録した（DEC-0113）。PR #111はaccepted head `148b9d53600583b12bbde6d21655258d87424695`、merge commit `9d37cf1a60475b6e1a0347744397cf9833f7cfc7`でformal mainへ通常merge済み。fresh Owner Evidenceとformal Verify CONTINUE後にmergeし、GitHub MERGED / main一致、PowerShell 5.1 / 7 Validate、snapshot、read-only Verify CONTINUEを確認した。Step 8の新規Beta MUST実装残作業はない。

採用済み完成線は少量商品ごとのSG Gate `ELIGIBLE`、人間Category・Brand / No Brand確認、SLS `ALLOW`候補、Seller Center必須Attribute・商品固有発送条件確認を経た手動出品である。未解決BLOCK / REVIEW / EXCLUDE / UNCHECKED / UNAVAILABLE、Category / Brand未確認、Battery / 危険物 / 許認可等の未解決疑義があれば出品しない。Safety / Battery / SLS停止条件を維持する。

SG operationはINACTIVE、`listing_ready=false`、SG export / handoff CLOSEDを維持する。PHはACTIVE / ALLOWED、SGはINACTIVE / ALLOWED、`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDを維持する。production API / DB変更、deploy、SG ACTIVE化、自動出品は未承認で未実施。Brand / SLS live acceptanceとSeller Center E2Eは未実施の既知制約である。

Step 8を終了し、次の独立工程はRoadmap Step 9「SG実運用」とする。Step 9は未承認・未着手であり、開始には別タスクとOwnerの別途明示承認が必要である。この補正ではStep 9へ進まない。

## 現在の正式状態

Owner Acceptance方式BをPR #105で正式採用した。accepted head `629c7fc7c6f3dc22335a09ffcbecf4d1d391b34f`をmerge commit `1bfd4ee065b4121ef7e9d081d902a25cb9b40ef1`としてformal mainへ統合し、PR #105のMERGEDを確認した。Ownerの手動技術値コピーは不要となり、明示的な最終承認は引き続き必須である。GitHub OWNER_ACCEPTANCEコメントは、承認後にrepository / PR / exact head / verification_input_hash / summary_binding / scopeを固定するmachine-readable binding / transport Evidenceとして扱い、Owner本人のUI手入力を独立証明するものとは扱わない。

PR #105はGovernance tests 96 passed、protected regression 612 passed、mandatory CI 6 / 6 PASSを確認した。current対象のfresh signed Owner Evidenceとformal Verify CONTINUE後に通常mergeし、merge後Validate、snapshot、read-only Verify CONTINUEを確認した。Provider / Verifier / Trust Anchor / State / protected capabilityおよび製品runtimeに変更はない。後続の文書正本化はPR #106で正式mainへmerge済み。SG SLS offline最小runtimeもPR #107 / DEC-0109で正式採用済み。

SG実catalog・6実商品のCategory acceptanceはPR #100でformal mainへ正式採用済み（DEC-0103）。Ownerの現在headとOwner Acceptance Summaryへの最終承認、fresh署名付きOwner Evidence、mandatory technical gates 6 / 6 PASS、formal Verify CONTINUEを確認して通常mergeした。merge後のformal main / PR MERGED / accepted内容一致、PowerShell 5.1 / 7 Validate、snapshot、read-only Verify CONTINUEまで確認済み。PR #100のmerge対象と受入結果を再実行・再承認する工程には戻らない。

SG Brand / No Brand Minimum Betaのoffline最小実装をPR #103でformal mainへ正式採用した（DEC-0105）。通常merge commitは`c1cfab9fef0283532fd3bf5968ea75c438179233`、accepted headは`7928086a2e870018943d9483acdc1684fc439fdf`で、main treeとaccepted head treeの一致を確認した。現在headにbindしたCI mandatory 6 / 6 PASSとfresh署名付きOwner Evidence、formal Verify CONTINUE後にmergeし、PR MERGEDを確認した。PowerShell 5.1 / 7 Validate、snapshot生成、read-only Verify CONTINUEもmerge後に確認済み。

実装はstrict opt-in raw検証、最大10 pageの完全取得、SG Category単位のtransactional replace、client / shop / request / run / session binding、session currentとDB digest再照合、商品単位No Brand保存、real Brand alias再validationを含む。No Brand tableは隔離acceptance DBへの明示初期化だけで、通常Store初期化へ追加しない。offline suiteはlocal 1,615 passed、CI 1,614 passed / 1 skipped、PH / SG protected回帰598 passed。skipは既存のformal local Benchmark artifacts未配置による条件。

正式採用はoffline実装だけであり、SG Minimum Beta全体やlive運用の受入ではない。production Shopee / Bridge request、実商品Brand / No Brand受入、production DB schema適用は未実施。SG operation INACTIVE、`listing_ready=false`、export / handoff閉鎖を維持し、Attribute、live SLS受入、deploy、自動確定・出品は未実施。SG SLS offline最小runtimeはPR #107 / DEC-0109で採用済み。responseにmarketplace / Category echoがないため、server内部の別Category誤応答をresponse内容だけから独立検出できるとは主張しない。Client marketplace / shop、request Category、run、sessionのbindingを取得provenanceとして扱う。

PR #103はOwnerのoffline限定最終承認で正式採用済み。Attribute、実商品受入、production API / DB / schema、listing_ready、export / handoff、deploy、SG ACTIVE化、自動確定・出品は別途明示承認なしに実施しない。SG SLS offline最小runtimeの正式採用はPR #107 / DEC-0109に限定する。DEC-0104の設計本文は変更せず、正式採用結果はappend-onlyのDEC-0105に記録する。

## Required Decisions

- DEC-0113 — PR #111のStep 8最終正本化、merge後確認、Step 8 CLOSEDとStep 9別承認境界。
- DEC-0112 — PR #110のStep 8正式採用、Owner Evidence、merge後検証、最終正本化とStep 9停止。
- DEC-0111 — SG Minimum Beta Step 8完成候補、半自動運用の完成条件・制約、Step 9別承認境界。
- DEC-0071 / DEC-0075 / DEC-0076 / DEC-0077 — SG Safety・Shared Battery・formal SLS assets・PH SLS runtimeの保護契約。
- DEC-0109 — PR #107 SG SLS offline最小runtime正式採用、Owner Evidence、merge後検証と後続境界。
- DEC-0108 — SG SLS offline最小runtime、exact ID・current内容binding、Safety非解除とOwner受入境界。
- DEC-0107 — PR #105 Owner Acceptance方式Bの正式採用、merge後確認、Governance taskの終了と次工程。
- DEC-0106 — Owner明示承認後のコメント搬送、移行PRの旧方式受入、維持するbindingと停止条件。
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
- production API再取得0、Bridge / credential変更、production SLS runtime、Brand / Attributeのlive受入、ready / deploy / SG ACTIVE化、自動確定・出品は未実行。SG SLS offline最小runtimeはPR #107 / DEC-0109で採用済み。
- 同一brandの6用途向け保護ケース標本であり、広い商品群の精度保証やSG実運用完成を意味しない。
- Git外Evidenceは`outputs/sg-real-product-category-acceptance/reselection-v2/`のacceptance-result.json、formal-adoption-result.json、選定 / 保存 / 再読込記録と、`outputs/governance/accepted-pr100/`のSummary / Owner Evidence / formal Verify。過去STOP・request試行・production Evidenceを保持し、商品名 / ASIN一覧 / raw catalog / DB / wrapper / secret / snapshotをGitへ追加しない。

## 確認済み検証と履歴

PR #103の現在対象CIはmandatory 6 gateすべてPASS。offlineは1,614 passed / 1 skipped、PH / SG protected回帰は598 passed。skipはGit外のformal local Benchmark artifact未設置による条件で、job自体はSUCCESS。local offlineは1,615 passed。PR #103 merge後ValidateはPowerShell 5.1 / 7双方PASS、snapshot / read-only Verify CONTINUE。実商品Evidenceとoffline / synthetic testsを区別する。

PR #100のCategory acceptance CIは当時mandatory 6 gateすべてPASS、offline 1,514 passed / 1 skipped、protected 598 passed。merge後にPowerShell 5.1 / 7 Validate、snapshot / read-only Verify CONTINUEを確認済み。これはPR #100当時の記録であり、今回のPR #103検証結果と混同しない。

旧brand理由STOP（DEC-0100）、source改行hashの診断、fresh DBのPH seed期待値補正はDecisionとGit外Evidenceに保持する。旧未実施記録を現在の進捗へ混ぜず、DEC-0101のscope修正・DEC-0102の実行結果・DEC-0103の正式採用の順で読む。PR #98 / #99の前工程も再実行しない。

## 今後の承認境界

SG SLS offline最小runtimeはPR #107 / DEC-0109、Step 8の半自動完成線はPR #110 / DEC-0111で正式採用済み。Step 9のSG実運用開始、production API / DB / schema、runtime切替・deploy・SG ACTIVE・listing_ready変更・export / handoff開放は別scope・別途明示承認を要する。手動確認として残す範囲とBeta後改善はDEC-0111に従い、未実施だけを理由に新しいBeta MUSTへ昇格しない。Roadmap工程順は不変。

## 終了とrollback

PR #112によるStep 8終了状態の再開案内とDecision Log不整合の補正まで完了し、Step 8はCLOSEDである。次の独立工程はRoadmap Step 9「SG実運用」だが、Step 9は未承認・未着手である。開始には新規タスクとOwnerの別途明示承認が必要であり、このタスクでは着手しない。

rollbackは今回のdocs-only文書を通常revertする。DB migration・production復旧は不要。過去Decision、正式SLS資産、PH、State、Trust Anchor、credentialと既存Evidenceを変更・削除せず、force push / dirty resetを行わない。
