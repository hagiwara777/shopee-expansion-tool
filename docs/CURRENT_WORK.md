# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

SG実catalog・実商品Category acceptanceは実行結果PASS候補（DEC-0102）。Ownerが6件を商品単位にレビューし、CONFIRMED 6 / REVIEW 0となった。新ブラウザセッションへ同じGate入力を再読込した結果、6件すべてが保存済みmappingとして再利用され、current catalogのID / path / leaf再validationが成立した。全商品listing_ready=false、SG export / handoff閉鎖、実運用DB / PH不変、禁止runtime未実行を確認した。現在の単一作業はこの結果の文書正本化・検証・正式公開 / formal main受入準備。formal main採用とタスクDONEは未完了。DEC-0099 / DEC-0100の旧brand条件とSTOPは履歴として保持し、選定scopeはDEC-0101を適用する。詳細は[受入手順](SG_REAL_PRODUCT_CATEGORY_ACCEPTANCE.md)を参照する。前工程PR #98 / #99は再実行しない。

### 前工程の正式成果（保持）

SG production Category catalog importのoffline実装とIMPORT_PREFLIGHT_PASS検証事実をPR #98でformal mainへ正式採用した（DEC-0098）。Ownerが現在headとOwner Acceptance Summaryを最終承認し、既存DPAPI保護鍵とTrust Anchor公開鍵の一致確認、GitHub承認コメント取得、fresh署名付きOwner Evidence、mandatory 6 gateのformal Verify CONTINUEを得て通常mergeした。追加production API、実運用DB・Bridge・credential変更、deployは行っていない。SG operationはINACTIVEを維持する。

Owner受理済みのpreflightはnormalized全2,285件 / root 31 / leaf 1,962件、全不整合0、決定的6列catalog、全件validation、tmp DBでSG-only replace、旧SG ID削除、PH / schema不変までの成立を意味する（DEC-0096）。過去STOPとhelper cleanup補正の履歴を保持し、実catalog・実商品受入や実運用DB importへ自動昇格しない。

## Required Decisions

- DEC-0102 — 人間レビュー6 / CONFIRMED6 / REVIEW0、新セッション再利用・current再validation6、安全停止とformal採用未完了。
- DEC-0101 — 同一brand許容、用途 / familyの多様性による6件選定、旧STOPの置換範囲。
- DEC-0100 — 実行承認後のcatalog binding PASS、適切な6商品入力不足によるSTOPと再開地点。
- DEC-0099 — 今回の6実商品受入設計、隔離DB、実行承認とformal main受入の境界。
- DEC-0080 — SG live OpenAI UIを閉じたまま人間確認だけを行う。
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

## 今回の実商品結果（DEC-0102）

- 6件すべて人間レビュー、CONFIRMED 6件、REVIEW 0件。
- 新ブラウザセッションに同じhash bindingの正式6件Gate入力を再読込し、保存済みCategoryの再利用6件、current ID / path / leaf一致6件を確認した。初期セッション0件保存と再読込後6件再利用は別session IDのGit外Evidenceで確認した。
- 全6件listing_ready=false、SG export / handoff閉鎖。専用DBのschemaとPH初期seedは不変、実運用DB file digest / size / mtimeは開始時と一致。製品code / tests / State / Safety / SLS・PH operation変更なし。
- production API request 0、Brand / Attribute / SLS runtime、Bridge / credential操作、ready / export / handoff / deploy / SG ACTIVE化、自動Category確定・出品は未実行。
- 14必須条件を満たしCATEGORY_ACCEPTANCE_PASS_CANDIDATEとした。今回の実商品受入結果のformal main採用・Owner最終merge承認・タスクDONEは未完了。
- 最終Git除外Evidenceは`outputs/sg-real-product-category-acceptance/reselection-v2/acceptance-result.json`。商品別記録・ASIN・raw catalog・DB・wrapper・snapshotはGitへ追加しない。
- 標本は同一brandの6用途向け保護ケースに限定され、広い商品群の精度BenchmarkやSG実運用受入を意味しない。人間確定結果は5つのroot / 5 Category IDへ分散した。

## 今回の実行準備（DEC-0101適用後）

元Gate46件は元Candidate49件の15列情報（schema_versionはGateのcandidate_schema_versionへ対応）と一致し、Gate audit49件のELIGIBLE46件と完全一致した。用途の異なる6familyを同じCSVからセル改変なしで抽出し、正式SG / 全行ELIGIBLE / EXPANSION単一source / ASIN重複なしを再validationした。全件同一brandを許容するが、色 / 容量違いだけを選んでいない。全6件が保護収納ケースである標本制約を明示した。準備時点ではCategory候補の分散は未確定とし、人間がケース自身を分類した。最終結果は上記DEC-0102集計を参照する。

厳密hash一致のproduction catalog全2,285件を新規acceptance DBへloadした。SG ID集合 / parent / path / leaf全件一致、schema不変、初期PH seed不変、実運用DBのfile digest / size / mtime不変を確認した。初回helperは新規DBのPHカテゴリ0件を期待して停止したが、既存StoreがPH seed1件を初期化する仕様だった。別のfresh初期化reference DBとの全PH table行・schema一致で補正し、製品code / 実運用DBを変更していない。SG catalogをfixtureで代用していない。

Git除外Evidenceは`outputs/sg-real-product-category-acceptance/reselection-v2/`のselection-manifest.json、正式6件Gate CSV、production catalog CSV、専用DB、human-review-progress.json、reload-events.jsonl等。過去STOP Evidenceは保持する。Git外wrapperは明示DB経路と子process限定LOCALAPPDATAで既存SG product UI / parse / validation / mapping保存を再利用し、初期画面で6件入力・確認済み0件・listing_ready0件・export停止を観測した。この段階では人間確認・保存・再読込の実商品再validationは未完了だった。現在の結果はDEC-0102の上記集計を参照する。

production API request 0、production DB / PH operation・data / Bridge / credential / State / 製品code・tests / Safety・SLS変更なし。Brand / Attribute / SLS runtime、ready / export / handoff / deploy / SG ACTIVE化、自動確定・出品を実行していない。

## 今回の準備検証

既存SG module / UI testsは65 passed（offline・synthetic / tmp DBのみ）。保存mapping再利用・stale path失効・non-leaf / stale path確定拒否・listing_ready=false・SG export拒否を再確認した。実商品Evidenceを代用しない。Governance testsは82 passed、PowerShell 5.1 / 7のValidateは双方PASS。開始時のsnapshot / local-change VerifyはPASS / CONTINUE。検証対象は受入設計であり、formal acceptanceのmandatory CI完了を意味しない。

## 結果文書の最終ローカル検証

結果記録後のoffline全体は1,515 passed、PH / SG protected回帰は598 passed。PowerShell 5.1 / 7のValidateは双方PASS。Decision本文のappend-onlyとID一意性、追加内容の商品識別子・絶対path・token pattern不在、製品code / tests / State / guardrails / dataの差分なしを確認した。変更はCURRENT_WORK / DECISION_LOG / 受入手順の3文書のみ。これはlocal検証であり、未公開の結果に対するmandatory CIやformal main受入の代用ではない。

## 前工程の確認済み事実と停止境界

SG suiteは63 passed、offline全体は1,515 passed、PH/SG protected回帰は598 passed。SG pathは親pathと自身nameの完全一致を要求し、余分な中間segmentを拒否する。tmp DBで不正入力時のSG不変、SG完全置換、古いSG ID削除、PH不変、schema不変、INSERT失敗時rollbackを確認した。既存testsで保存済みmappingのcurrent ID / path / leaf再validationとlisting_ready=falseを確認した。

前工程（DEC-0096）のproduction Category GETは1 request、retryは0（DEC-0095の以前の1 requestとは別承認）。全件でduplicate / empty name / missing parent / cycle / root到達不能 / path不整合 / leaf不整合はすべて0。tmp DBでPH catalog / PH sync state不変、schema不変、SG ID集合の全件一致、旧SG ID消失を確認した。Windowsのtmp DB cleanup時PermissionErrorは検証helperだけでconnection close / GCを明示して解消し、保存済みnormalized全件からoffline再検証した。追加APIは0、製品codeの修正はない。Git除外Evidenceは`outputs/sg-production-import-preflight-20260928-owner-recheck/`のnormalized-categories.json、provenance.json、request-attempt.json、verification-report.json（初回cleanup失敗記録）、offline-revalidation-report.json（最終PASS）。Google Bridge変更、credential表示・保存・変更、raw response保存、Brand / Attribute API、実運用DB replace、migration、実商品受入、SLS runtime、handoff、deploy、operation ACTIVE化、自動確定・出品は実行していない。Client、shared AI Core、Store、Safety、Candidate 15列、Prelisting Gate、governance/state.jsonは変更しない。既存dirty PH作業ツリーのファイルを編集・整理していない。

## 次の単一作業・rollback

次の単一作業は、今回の最小結果文書の検証・差分 / secret / 無関係混入確認を完了し、明示的なcommit / push承認の範囲で結果を公開すること。formal main mergeは別の現在対象Owner Acceptanceと最終承認を要する。レビュー完了をmerge承認へ読み替えない。mandatory technical gates / CI / exact head / Summary bindingが成立する前にformal merge承認を要求しない。merge後の最新formal main / PR MERGED / Validate / snapshot / read-only Verifyまで終わるまではDONEにしない。実運用DB replace、Brand / Attribute / SLS、listing_ready=true、export / handoff / deploy、SG ACTIVE化へ自動進行しない。

DEC-0100時点のSTOP、0件選定・DB未作成は以下に履歴として保持する。Owner修正後の再開を旧入力不足の継続STOPと混同しない。これらの過去未完了記録はDEC-0102の実行結果で進捗更新したが、formal main採用は未完了とする。

今回、DEC-0096 normalized全件の厳密SHA-256一致、provenanceのrepository / SG / production endpoint / shop binding、historical source hashと現formal main sourceの同一性、決定的6列catalogの厳密SHA-256一致、全件parser validation、入力逆順byte一致、total 2,285 / root 31 / leaf 1,962、parent / path / leaf整合を確認した。provenanceのsource hashはnormalizerがCRLF bytes、transformerがLF bytesで記録されており、対応する歴史bytesへ完全一致し、現formal mainのGit blobも両方不変。sourceやEvidenceを書き換えてhashを合わせていない。

前回（DEC-0100）発見した3 CSVは正式parserを通るが、2ファイルは同一synthetic 1商品、残る1ファイルは46商品すべて同一brand（最大2件条件では選択可能2件）。後者の実Gate出所は正式受入未確定であり、filename / parser PASSだけで実データ由来を保証しない。商品情報のreplacement characterは0で、表示時の文字コード問題を入力破損と判定していない。6件選定0、人間レビュー0、確定0、商品REVIEW・実商品の保存再validationは未評価。隔離DBも未作成。

Git除外Evidenceは`outputs/sg-real-product-category-acceptance/input-verification-report.json`。production API request 0、production DB / PH / Bridge / credential / State / Safety / SLS / 製品code不変、Brand / Attribute / SLS runtime・export / handoff・deploy・SG ACTIVE化・自動確定未実行。既存dirty PH作業ツリーは触っていない。今回の文書はローカル候補でありformal mainへの採用・実商品受入完了を意味しない。

受入は6件すべての人間レビュー、CONFIRMED 4件以上、理由付きREVIEW最大2件、最低1件の保存・再読込・current ID / path / leaf再validation、全商品listing_ready=falseを必要とする。SG export / handoff、Brand / Attribute / SLS runtime、SG ACTIVE化、実運用DB replaceは禁止を維持する。結果文書・mandatory technical gates・現在対象のOwner Acceptance・明示的最終merge承認・formal mainのmerge後検証が完了するまでタスク完了にしない。

今回のrollbackは受入設計のdocs-only差分の通常revert。前工程のcode / testsは戻さない。DB migration、State、credential、PH運用の変更を伴わない。force pushとdirty resetは行わない。
