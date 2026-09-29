# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch / HEAD / PR / checksはGit / GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の正式状態

SG実catalog・6実商品のCategory acceptanceはPR #100でformal mainへ正式採用済み（DEC-0103）。Ownerの現在headとOwner Acceptance Summaryへの最終承認、fresh署名付きOwner Evidence、mandatory technical gates 6 / 6 PASS、formal Verify CONTINUEを確認して通常mergeした。merge後のformal main / PR MERGED / accepted内容一致、PowerShell 5.1 / 7 Validate、snapshot、read-only Verify CONTINUEまで確認済み。PR #100のmerge対象と受入結果を再実行・再承認する工程には戻らない。

SG Brand / No Brand Minimum Betaのscope・受入条件定義は完了し、Ownerは修正版のDESIGN_PASSを受理した（DEC-0104）。本書は確定設計のdocs-only正本化を記録する。Brand製品実装、DB schema適用、production Brand API、実商品Brand確認は未実施であり、live / 実商品操作は未承認。設計受入を製品完成またはlive実行許可へ読み替えない。

現在のタスクは、DEC-0104のappend-only追記、本書の再開案内、ROADMAP / READMEの古いCategory状態表記の補正を対象とする。commit / push / Draft PR / CI / read-only reviewまで同じタスクで進め、現在headのmandatory technical gates完了後にOwner Acceptance Summaryを提示して停止する。formal main mergeはOwnerの明示的最終承認後だけ行い、merge後検証と文書整合確認まで終えて本タスクを終了する。Category受入手順の詳細は[受入手順書](SG_REAL_PRODUCT_CATEGORY_ACCEPTANCE.md)を参照する。

## Required Decisions

- DEC-0104 — SG Brand設計完了、商品単位No Brand保存、strict current取得・再validation、実装 / live / formal採用の境界。
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

PR #100の現在対象CIはmandatory 6 gateすべてPASS。offlineは1,514 passed / 1 skipped、PH / SG protected回帰は598 passed。CIのskipはGit外ローカルBenchmark artifactが未設置の既存条件で、job自体はSUCCESS。local offlineは1,515 passed、SG module / UIは65 passed。実商品Evidenceとoffline / synthetic testsを区別する。merge後ValidateはPowerShell 5.1 / 7双方PASS、snapshot / read-only Verify CONTINUE。

旧brand理由STOP（DEC-0100）、source改行hashの診断、fresh DBのPH seed期待値補正はDecisionとGit外Evidenceに保持する。旧未実施記録を現在の進捗へ混ぜず、DEC-0101のscope修正・DEC-0102の実行結果・DEC-0103の正式採用の順で読む。PR #98 / #99の前工程も再実行しない。

## 次の単一作業（本正本化のformal採用後）

**SG Brand Minimum Beta最小実装・offline検証を、新規Codexタスクで開始する。** 新規タスクは最新formal main、本書、PROJECT_ROADMAP、Required Decisions、Stateを照合し、DEC-0104の確定設計を適用する。既存共通Client / Access Token Source / Storeを再利用し、real Brand aliasのcurrent再validation、商品単位No Brand保存、strict完全取得、対象Category単位replace、失敗時の未確定停止を最小差分で実装する。PH / SG protected gatesを維持し、SG listing_ready=falseとexport / handoff閉鎖を保つ。実装は現在のdocs-onlyタスクで開始しない。新規タスクはOwnerが開始し、本タスクから自動作成・dispatchしない。

production Brand APIと実商品Brand確認は未承認であり、offline成果の成立後に対象shop / Category allowlist / request上限 / retry方針 / 隔離DB / Git外Evidence / 実商品範囲への別Owner承認を必要とする。過去Category GETの承認を流用しない。新No Brand tableは後続受入の隔離acceptance DBへだけ明示初期化し、通常の実運用DBへのschema導入は将来の別判断とする。実運用DB replace、Bridge / credential変更、Attribute / SLS runtime、listing_ready=true、export / handoff / deploy、SG operation ACTIVE化、自動確定・出品、MY / THへ進めない。PH operation / data / schemaと保護capabilityを維持する。

## 終了とrollback

SG Brand設計正本化の4文書だけのPRに対するmandatory technical gates、現在対象SummaryとOwnerの明示的最終承認、fresh Owner Evidence、formal Verify CONTINUE、通常merge、最新formal main / PR MERGED / 採用内容一致、Validate / snapshot / read-only Verifyと文書整合まで確認して本タスクを終了する。Owner Acceptance待ちはWAITING_APPROVALであり、formal採用・終了を完了扱いにしない。

rollbackは今回の設計正本化文書の通常revert。Decision撤回・訂正は新しい記録で残し、過去Decisionを編集・削除しない。PR #100の受入実行を再実行せず、前工程のcode / tests、実運用DB、PH、Bridge、credential、既存Evidenceを変更・削除しない。force push / dirty reset禁止。
