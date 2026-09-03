# PH画像Safety Minimum Beta live検証実行計画

## 1. 位置づけ・現在地

2026-09-03作成。これは実行承認前の計画であり、API利用または費用の承認書ではない。今回の作業は計画作成・CURRENT_WORK同期・文書検証・ローカルcommitまで。OpenAI API、Keepa API、実商品API処理、実Amazon画像取得は今回実行しない。push / PR / merge / deployも行わない。

- repo: `hagiwara777/shopee-expansion-tool`
- 確認済みformal main: `869b0c60525b5b6d201dbabdf31e44bbc53bbd4c`（PR #56、merge commit方式）
- 統合済み実装commit: `ed1548e4611af831dc130331f770cbee65554604`
- DEC-0054: `01b2648f0448edc86e7258f55225ab73ac3025a6`、PR #55で先にmain統合済み。
- branch上read-only技術レビューPASSはオーナー確認済み。全pytest 1018件成功・失敗0件、snapshot検証PASSは既存ローカル検証記録であり、live受入の代わりにしない。
- Gate P / PH Minimum BetaはHOLD継続。技術疎通・品質sanity・費用確認・最終Beta受入を別々に記録する。

[AGENTS.md](../AGENTS.md)、[運用RUNBOOK](RUNBOOK_CHATGPT_CODEX.md)、[CURRENT_WORK](CURRENT_WORK.md)、[DECISION_LOG](DECISION_LOG.md)のDEC-0051 / DEC-0053 / DEC-0054を前提とする。[既存受入プロトコル](PH_MINIMUM_BETA_ACCEPTANCE_PROTOCOL.md)の技術確認と人間受入の分離、INCONCLUSIVE、外部操作の別承認、Evidence方針を引き継ぐ。同プロトコルの旧P0〜P6全面工程はDEC-0049以降の現在方針に読み替え、今回再開しない。本計画はB3画像Safetyの限定live確認であり、Gate KやB2 E2E全体の再実行、Gate P受入ではない。

[WORK_BRIEFテンプレート](templates/WORK_BRIEF.md)で個別Briefをrepo外に作成する。後続実行時には対象・上限・承認記録・実行Git状態をそのBriefで確認する。個別Briefと商品identityはGitへcommitしない。本計画は既存仕様内の検証手順であり、新Decisionを追加せず、工程変更のないPROJECT_ROADMAPも変更しない。

## 2. 確認すること

1. OpenAI Responses API / `gpt-5.6-terra`が利用アカウントで使えるか。
2. 実Amazon画像を現行取得経路で読み込めるか。
3. Structured Outputsの検証、PH専用sidecar、Candidate binding、Gate表示がliveでも成立するか。
4. 明確な武器・武器形状物に致命的な見逃しがないかを少量で確認する。
5. 実際の遅延と費用感を確認する。

統計的な精度評価、見逃し率の保証、model比較、サンプル探索の拡大は目的にしない。AI単独BLOCKは禁止し、NO_SIGNALをSAFE保証と扱わない。既存BLOCK / REVIEWを画像判断で解除せず、人間最終判断はALLOW_PREPARATION / EXCLUDEを維持する。

## 3. サンプルと人間期待区分

画像AI実行商品は全Phase通算で最大5件。予定枠は次のとおりとし、サンプルIDと実商品identityの対応はGit外だけで管理する。

| 枠 | 構成 | AI結果を見る前の人間期待区分 |
| --- | --- | --- |
| W1 / W2 | 明確な武器・武器形状物 2件 | 疑義あり |
| N1 / N2 | 明確な非該当商品 2件 | 非該当 |
| A1 | 境界・曖昧サンプル 最大1件 | 曖昧・判断保留 |

- DEC-0053の4 root（13299531 / 2277721051 / 14304371 / 2016929051）またはroot不明で、実際のselectorがTARGET_ROOT / ROOT_UNKNOWNになるKeepa由来商品を使う。
- 既存title / description / ingredients SafetyでBLOCK済みの商品は品質確認用に使わない。OTHER_ROOT / EXISTING_BLOCK / PROVIDER_UNSUPPORTEDを画像AIへ通す操作をしない。
- title、root、Fact、Ruleを改変して対象化しない。ホーム＆キッチン・Beauty全体、title trigger、subcategory拡張は行わない。
- 人間期待区分は、AIへ渡る現行選択順の最大3画像をオーナーが確認して、AI結果を見る前に日時・根拠とともにGit外へ記録する。商品名だけから期待区分を決めず、結果に合わせた事後変更をしない。
- 適切な2件＋2件を安全に確保できなければINCONCLUSIVE_SAMPLEとする。曖昧枠は省略可。技術疎通だけ成立しても、足りない構成を品質確認済みとは扱わない。
- 既存cache / Factとオーナーが提示できる候補に限定する。サンプル探索目的でExpansion / Product Finderを連続実行しない。失敗商品も試行済み枠として残し、差替えで最大5商品を超えない。

## 4. request・画像・実行単位

| 項目 | 全Phase共通の上限 |
| --- | --- |
| 商品数 | 最大5件 |
| 画像 | 1商品最大3画像、現行の元順序・重複排除を維持 |
| OpenAI | 1商品原則1 Responses request、通常最大5 Responses request |
| retry | transient error時だけ最大1 retry、retry込み絶対上限10 Responses request |
| 同時実行 | 行わず、1商品終了ごとに判定・費用確認 |

認証・契約・model未対応をtransient扱いしない。手動再実行、ページ再読込、別session、Phaseの切替で件数・attempts・費用予算をリセットしない。失敗・timeoutで応答が不明なrequestも送信済みとして数え、課金ゼロと仮定しない。成功後の再現用再送信は行わない。

現行UIの有料実行ボタンは未実行対象全体を処理し、途中の意味上のNO_SIGNALを見て自動中断する機能はない。そのためPhase BもPhase Cも、未実行対象が1商品だけの入力セットで実施する。Phase Cの4件一括実行は禁止する。既存serializer・sidecar生成/検証を使用し、1商品Candidate最終bytesと各Safety sidecarを正しく再bindingする。CSV/JSONの手編集でSHAやASIN集合を合わせず、既存Factから整合したセットを作れない場合は停止する。実行前に人間判断未記録かつNOT_RUNの対象が1件であることを確認する。

画像取得の現行transient retryは各画像最大1回であり、Responsesのretry枠と混同しない。全5商品×3画像ならAI処理内の画像GETは通常最大15回、retry込み最大30回。人間による画像確認アクセスは別途記録し、有料API上限へ読み替えない。通常画面rerun・ダウンロードでOpenAIへ再送信しないことを実測確認する。

## 5. OpenAI費用・設定の承認案

**後続実行のproposed総費用上限はUS$3。現在は未承認。** 全商品・retry・失敗requestを含むOpenAI合計であり、Keepa費用は含めない。上限を超える可能性があれば送信せず停止する。

2026-09-03に開いた[OpenAI公式料金表](https://developers.openai.com/api/docs/pricing)のStandard / Short context料金は、input **$2 / 1M tokens**、output **$12 / 1M tokens**。[対象model仕様](https://developers.openai.com/api/docs/models/gpt-5.6-terra)とも一致した。これは実費実測ではなく料金の参照値。実行前に適用料金・tierを再確認し、long context等の別料金や不明な設定があれば同じ単価で決め打ちしない。

`gpt-5.6-terra`、`reasoning.effort=low`、`store=false`、Structured Outputs、現行`max_output_tokens=1200`を維持する。現行`detail="auto"`も変更しない。GPT-5.6ではautoはoriginal相当のサイズ処理であり、大きい画像の費用・遅延に影響し得る。high等への変更は実費確認後の別判断とする。[公式画像仕様](https://developers.openai.com/api/docs/guides/images-vision#model-sizing-behavior)

費用上限はアプリが自動強制する機能として実装済みではない。実行者は次の方法で送信前に予算を確保する。

1. 1商品分の実画像サイズと公式画像token見積方式、固定prompt / schema等を含む入力の保守的上限を確認する。画像が送信直前に同じ条件を満たすと確認できない場合は、現行画像取得制限までを見積対象にするか停止する。画像やdetailを加工して予算へ収めない。
2. 適用input単価×入力token上限と、output単価×1200を1 attemptの上限見積とする。reasoningを含む出力枠を少なく見積もらず、割引・cache hitは前提にしない。適用条件に応じた追加費用も確認する。
3. ボタン操作前にretry分も含む2 attempts分を予約する。確認済み費用＋既送信で未確定の予約額＋今回2 attempts分の上限見積がUS$3以内と示せない場合は停止する。課金画面の予算通知だけをhard capとみなさない。
4. 1商品終了ごとに照合する。確認不能な失敗attemptの予約額は解放しない。件数上限内でも残予算を確認できなければ追加送信しない。

現行adapter / sidecarはusage、request別実費、latencyを保存しない。latencyは操作開始〜終了の外部時計による実測として記録し、画像取得・retryを含むかを明示する。usage / actual costはオーナーが確認できるOpenAI利用・請求表示等を日時・project・実行区間に対応付ける。他処理の費用が混ざり分離不能、反映遅延、表示権限不足等で確認できなければCOST_UNVERIFIEDとし、推測値をactual costへ書かない。usageからの単価換算は算定額、予算用上限は見積額として実測請求額と別欄に置く。画像やcredentialを含むraw HTTP dumpで補わない。計測のためのAPI追加や実装変更は自動で行わない。

## 6. Keepaの境界

既存cache / 既存Factを最優先し、画像URL・rootと既存Safetyに必要な情報があるかをローカルで確認する。cache missで自動live取得へ移る入口を承認前に実行しない。

画像情報を持つfresh Factが必要で、既存Factからは得られずKeepa liveが不可避な場合は、その時点で停止する。必要ASIN数、取得目的、予定request範囲・消費token見積・retry条件を報告し、**OpenAIとは別のKeepa有料API承認**を得る。identityはGit外で提示する。承認がない場合は不足をINCONCLUSIVE_SAMPLE等として残す。画像Safetyのための自動追加Keepa request、Canopy代用、暗黙fallbackは追加しない。

## 7. 実行順と各Phaseの出口

以下は後続作業の手順であり、今回Phase A〜Cを実行済みとは扱わない。本計画の正本化・main統合確認は依存実行前に行い、push / PR / merge自体も別承認とする。

### Phase A — no-cost preflight

formal main / 実行HEAD / clean状態、計画の版、設定とcredentialの存在のみをローカル確認する。`OPENAI_API_KEY`は値・一部文字・hashを表示/保存せず、存在と形式確認の結果だけを残す。`PH_IMAGE_SAFETY_API_ENABLED`、指定provider/model/detail、現行prompt / schema / retry / 画像制限を確認する。model列挙・認証テストを含めAPI requestは0回とする。存在確認だけで認証・契約が有効と判定しない。

既存Factでのサンプル構成、1商品単位のbinding、費用予約方法、Git外Evidence保存先を確認し、オーナー費用・外部API承認の対象を固定する。実画像取得・OpenAI送信はPhase B以降とし、承認不足、サンプル不足、費用上限確認不能なら送信前停止。formal mainが進んだ場合は差分と承認対象を再確認する。

### Phase B — 1商品だけの接続確認

原則W1を先に使い、全5件の1件として数える。承認後、選択される公開Amazon画像を人間が確認し期待区分を記録する。既存Fact・1商品Candidate・各sidecarでPH Gateを実行し、既存SafetyでBLOCKでないこととselector対象を確認してから、その1商品だけを有料実行する。

`画像取得 → OpenAI Responses → schema検証済みStructured Output → sidecar binding → Gate日本語表示`を確認する。画像LOADED、実行状態、AI意味上のstatus、商品最終判定を分けて記録する。通常rerunとダウンロード後もattempts / 評価identityが変わらず、実行区間の利用記録等でResponses再送信がないことを確認する。再送信有無を確認できなければ、live確認済みと断定しない。元の未実行ファイルを再投入して実行ボタンを押す検証は行わない。

第8節のLIVE_TECH_PASS条件を満たし、重大停止理由がなく、費用上限を維持できる場合だけPhase B PASSとする。**Phase BがPASSしなければ残り4件は実行しない。** 画像取得失敗もその商品で記録して止め、代替商品で接続確認を続けない。

### Phase C — 残り最大4商品

W2、N1、N2、任意A1の順を基本とし、各商品で事前期待区分、費用予約、1商品実行、Evidence保存、停止判定を完結してから次へ進む。重大見逃しが出た時点で残りを実行しない。結果を良く見せるためのサンプル差替え・追加、再試行上限の解除はしない。

## 8. 判定・停止

LIVE_TECH_PASSは次をすべて確認した場合だけ記録する。

- 指定modelのResponses APIが正常完了。
- 1件以上の実Amazon画像がLOADED。
- schema検証済みAI結果を取得。
- Candidate SHA-256 / ASIN集合 / 画像評価 / 人間判断のsidecar bindingが維持。
- Gateへ正しく反映され、既存BLOCK / REVIEWを解除しない。
- 通常rerunによる再送信・再課金がない。

| 観測 | 判定・行動 |
| --- | --- |
| 明確な疑義ありの人間基準サンプルがNO_SIGNAL | `BETA_BLOCKER_CANDIDATE: IMAGE_FALSE_NEGATIVE`で即停止。AI意味上のNO_SIGNALも確認し、別の理由で最終REVIEWになっていても見逃しを隠さない。残サンプルで問題を薄めない |
| 非該当商品がREVIEW | それだけでBeta blockerとせず、件数と人間確認作業の増加を記録 |
| 曖昧商品がREVIEW / INDETERMINATE | FAIL扱いせず、人間確認へ残す |
| 単発の画像取得失敗 | 商品単位の挙動として記録。未取得・一部失敗をNO_SIGNALへ読み替えない。Phase Bならそこで停止 |
| 複数の通常商品で画像取得失敗が反復 | 2商品目で`BETA_BLOCKER_CANDIDATE: IMAGE_FETCH_PATH`として停止・報告。新サンプルを足して再現探索しない |
| 認証・契約・model未対応・設定不一致 | Gate全体STOP。自動model変更・fallback・修正をしない |
| schema / Candidate / ASIN / 人間判断binding不正、既存BLOCK / REVIEW解除、再送信 | Gateを止め、技術不整合を報告。別修正作業へ自動移行しない |
| 適切なサンプルを確保できない | `INCONCLUSIVE_SAMPLE`。統計的な品質PASSに置き換えない |
| 費用またはusageを確認できない | `COST_UNVERIFIED`。予算内と示せなければ追加送信停止 |

技術疎通が成立しても、品質blockerまたはINCONCLUSIVEを消さない。AI結果statusとシステム状態、技術PASS、品質sanity、費用確認を別項目で報告する。最終の画像判断・ALLOW_PREPARATION / EXCLUDE・Beta受入はオーナー判断とし、本検証だけでGate P / PH Minimum BetaのHOLDを解除しない。

## 9. Evidence・データ取扱い

Git外保存先は`LOCAL_ARTIFACT_ROOT/PH_Image_Safety_Live_Validation/<run_id>/`を予定aliasとし、実行前に保存先を確認する。今回live Evidenceを捏造せず、個別Briefはrepo外に保持する。正式Evidenceができた場合だけ、既存手順でartifact ID・完全SHA-256・producer・受入状態・storage aliasの最小索引を作る。

Git外Evidenceへ必要最小限を記録する。

- formal main SHA、実行branch / HEAD、計画版、実行日時とtimezone、承認対象・上限。
- provider / model、商品数、サンプルID、各商品のselector・理由、既存Safety status。
- 選択画像数・順序・取得状態・内容hash、AI statusとシステム状態、商品最終判定、attemptsと累積Responses数。
- AIを見る前の人間期待区分・記録日時・根拠、結果との一致/不一致、人間最終判断。
- Candidate SHA-256 / ASIN集合 / 評価identityへのbindingを検証した記録と既存sidecar。
- latency、確認可能なusage / actual cost、その情報源・集計区間、全体費用。未確定額、保守的予約額、算定額は区別。
- LIVE_TECH結果、品質sanity、blocker / inconclusive理由、実施した外部操作と実施していない外部操作。

商品データ、ASIN一覧、画像URL、商品個別identity、画像、credentialはGitへ保存しない。画像bytes / base64は処理時のメモリだけで使い、Amazon画像の恒久保存をEvidenceの条件にしない。Git外でもcredentialを保存せず、必要以上のraw responseや画像入りスクリーンショットを残さない。

OpenAIへ送る商品データは公開Amazon商品画像のみとし、既存の固定prompt / schema以外に商品titleやASIN一覧を送らない。個人情報、顧客情報、秘密情報を送らない。`store=false`を維持するがZero Data Retention保証とは扱わない。アカウントのデータ保持設定は別確認事項である。[OpenAI公式データ取扱い](https://developers.openai.com/api/docs/guides/your-data)

## 10. 承認時に提示する実行範囲

オーナーへの承認案は「PH画像Safetyの実Amazon公開画像取得とOpenAI Responses / gpt-5.6-terraによる最大5商品、1商品最大3画像、通常最大5 request・transient最大1 retry込み絶対上限10 request、総費用上限US$3。1商品ずつ停止判定し、Keepa liveは含めない」とする。個別identityと期待区分はGit外で固定する。UIの有料実行チェックだけを、この事前承認の代わりにしない。

ph_image_safety実装、prompt、model、detail、selector、Guardrail Rule / 辞書、Candidate 15列、Gate判定優先順位は変更しない。OpenAI以外の有料API、Keepa live、実商品探索の拡大、Shopee live書込み、deployを含めない。異常時は証拠を残して停止し、修正・モデル変更・追加実行を別判断へ戻す。

## 11. 今回の文書検証と次の単一作業

今回の検証対象は文書整合、git diff --check、追加差分のsecret pattern、変更2件限定、snapshot再生成・検証。API疎通、credential存在、実画像、実商品、費用、サンプル確保はまだ確認しない。既存pytest記録を今回の再実行結果として扱わない。

次の単一作業: **オーナー費用・外部API承認後、PH画像Safety実API・最大5商品live検証を実行**。
