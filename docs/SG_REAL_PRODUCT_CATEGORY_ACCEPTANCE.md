# SG実catalog・実商品Category acceptance

## 状態と目的

DEC-0099の受入設計にDEC-0101のOwner承認scope修正を適用する。実行は明示承認済み。
DEC-0100の同一brand理由STOPは履歴として保持し、同一brandを許して既存46件から6件を再選定する。
catalog binding・全件validation・用途別6件再選定・専用DB loadは成立。人間レビュー画面を表示済み。
DEC-0102で6件人間レビュー・CONFIRMED6 / REVIEW0・新セッション再利用6・current再validation6を確認した。
全14条件を満たすPASS候補であり、結果のformal main採用・タスクDONEは未完了。
正式進捗はCURRENT_WORK、判断はDECISION_LOG、Git対象bindingはrepo外Task Contextを参照する。

目的はproduction SG catalogで人間が少量実商品のCategoryを確認・保存・再利用でき、
listing_ready=falseで安全停止すること。Category精度Benchmarkではない。

## 実行前の確認

1. 最新GitHub mainとPR #98 / #99のMERGEDを再確認する。開始時のSHAを恒久固定値にしない。
2. AGENTS全文、CURRENT_WORK / Required Decisions、Roadmap、RUNBOOK適用節、関連Decision本文を読む。
3. Task Contextと承認scopeを照合しValidate / snapshot / Verifyを実行する。HOLD / HARD_STOPを迂回しない。
4. 実商品操作直前にAGENTSのlive API / 実商品承認境界を確認する。実行承認がなければWAITING_APPROVAL。
5. 実行承認は既存offline実catalog・実Gate商品読込、6件選定、専用DB load / 人間確認保存 / 再読込検証に限定する。
   API再取得、実運用DB replace、formal mergeの承認と混同しない。

## 入力の固定

- DEC-0096のnormalized-categories.jsonとprovenance / 最終offline reportをGit外既存Evidenceから参照する。
- normalized SHA-256: `1b43516a56ad7d3a101f95b8adf1c38f242a105e5940c4efca95f0330e7d1f12`。
- 正式build_sg_category_catalog_csvで再生成した6列CSVのSHA-256:
  `927651f1f3f5c01046669fd4834c7a2de71dc4d89f4f0cf25248b69a1c261cc6`。
- source identity、取得時のrepo / head、normalizer / transformer source hashと現formal処理の関係を確認し、
  全件parser validation、total 2,285 / root 31 / leaf 1,962、duplicate / empty name / missing parent / cycle /
  root到達不能 / path / leaf不整合の全0を確認する。過去hashの存在だけで今回PASSとしない。
- Git外artifactへ安全にアクセスできない、binding不明、hash / 件数不一致ならSTOP。
  fixture・SLS Category assetを代用しない。productionを自動再取得せず別承認を待つ。
- 1つの正式SG Gate eligible CSVを正式parserで検証する。marketplace=SG、全行ELIGIBLE、単一source_type、
  candidate_asin重複なし。正式filenameはprelisting_gate_eligible_sg_expansion.csvまたは
  prelisting_gate_eligible_sg_resolver.csv。ダウンロードsuffixは元sourceを保全してGit外作業コピーで正規名へ戻す。
- 実データ由来と正式Gate出力であることを出所で確認し、見た目やfilenameだけで保証しない。
  raw Candidate、REVIEW / EXCLUDE、synthetic、複数CSV結合で代用しない。適切な入力がなければSTOP。
- 同じCSVから6件を選び、元file hashと選択行のbindingをGit外へ残す。セルは変更せず、正式列・行順を保つ。
  6件抽出後も正式parserで確認する。同一brandを使用可とし、brand上限は必須条件としない。
  同一family・色違い・容量違い等だけで6件を構成しない。既存46件から用途 / 商品種類ができるだけ異なる6件を選び、
  可能なら異なるCategory候補へ分散する。実質的に同じ商品群しかない場合だけ多様性不足のSTOPとする。
  容易な5件程度＋複数候補1件程度は候補があれば目安とし、6件人間レビューと最低4件確定のPASS条件は変えない。
  収納ケースは対象機器本体ではないため、ケース自体の分類を人間が確認する。

## DBと画面の隔離

- CategoryMapperStore(db_path=専用acceptance DB)で事前検証できる。人間UIには子process限定LOCALAPPDATAを
  Git除外acceptanceディレクトリへ向け、既存SG UIを使う。OSの恒久LOCALAPPDATAを変更しない。
  Git外wrapperではhash bindingした正式6件Gateを既存parserへ渡し、既存SG商品単位UIを直接再利用できる。
  商品確認・保存は既存confirm入口、未確定理由はGit外記録とし、製品codeは変更しない。
- 起動前にdefault_category_mapper_db_path()の解決結果が専用acceptance領域内で、
  実運用DBと異なることをassertする。既存DBをcopy / replaceせず新規DBを用いる。
  既存Store初期化で作られる隔離DB内PH seedは初期状態として保持し、SG load前後で不変を確認する。
  実運用PH dataと混同せず、SG catalogをPH / synthetic seedで代用しない。
- app.py全体を起動する場合は隔離した別port・sessionとし、既存PHプロセスを停止しない。
  SG Category画面だけを操作し、PH catalog同期やExpansion / Resolver / Gate再実行をしない。
- credentialやBridgeをロード・編集するhelperを作らず、live APIを呼ばない。
  手順上必要なhelperや記録はGit外に置き、製品コードを変更しない。
- production DB / PH data保護の検証は本文を読まないfile digest・更新時刻等で行う。
  稼働中PHから別変更があった場合、単純に不変PASSとせず原因を切り分け、意図しない書込疑いではSTOPする。
- State、Safety / SLS asset、codeの開始終了差分も確認する。隔離DBでの確認をproduction DBの実動作Evidenceへ代用しない。

## 人間確認と再読込

1. 検証済みproduction 6列catalogを専用DBへloadし、件数・全件一致を確認する。
2. 同じ正式Gate由来6件を画面で読込し、ASIN・title・Keepa brand / category・必要時Resolver titleを表示する。
3. 人間がcurrent catalogを検索し、各商品でID存在・leaf=true・hierarchy完全一致path・商品実体への妥当性を確認する。
   Codex / AIは候補の自動確定や人間の確認の代行をしない。
4. 人間の明示判断だけを商品単位で確定・保存する。判断不能は未保存REVIEWとし、商品固有理由をGit外記録に残す。
   Category REVIEWは元Gate ELIGIBLEを改変せず受入結果側に記録する。Safety判断は扱わない。
5. 最低1確定商品でアプリ再読込または再起動後、同じ6件Gate入力を再読込する。
   保存済みmappingがcurrent ID / path / leaf一致時だけUSER_CONFIRMED_REUSEとなり、listing_ready=falseを確認する。
6. stale mapping失効は既存test_human_confirmation_is_per_asin_persisted_and_revalidated等のnegative contractを再確認する。
   今回の実catalogを破壊してnegative testを追加することはMUSTではない。

## PASS候補の14条件

| # | 必須確認 |
|---|---|
| 1 | accepted production SG catalogを隔離DBへ正常load |
| 2 | 正式SG Gate eligible由来の実商品6件を読込 |
| 3 | 6件すべてを人間が商品単位レビュー |
| 4 | current leaf Categoryを最低4件で人間確定 |
| 5 | 未確定最大2件、商品固有の明示REVIEW理由あり |
| 6 | 確定ID / path / leafがcurrent catalogと一致 |
| 7 | 最低1件の保存mapping再読込・再利用 |
| 8 | 再利用時current ID / path / leaf validation成立 |
| 9 | 全商品listing_ready=false |
| 10 | SG export / handoff閉鎖 |
| 11 | PH operation / dataへの影響なし |
| 12 | Brand / Attribute / SLS runtime未実行 |
| 13 | production DB変更なし |
| 14 | secret / credential非表示・非保存 |

すべて成立した場合だけPASS候補。未確認はPASSとしない。6件のレビュー自体が未完了ならPENDING。
4件未満の確定またはREVIEWが3件以上なら受入基準未達として理由を報告し、自動的に商品を差替えない。

## STOP・記録・終了

catalog binding / hash / 件数不一致、市場混在・non-ELIGIBLE・source_type混在の通過、catalog外 / non-leaf確定、
stale path再利用、PH影響、意図しないproduction DB書込、listing_ready=true、SG export / handoff開放、
Safety / Shared Battery / Community NG / own penalty解除、secret露出、fixture代用必要時はSTOP。
商品個別のCategory曖昧性は未保存REVIEWとし、その存在だけで全体STOPにしない。
STOP時はscopeを広げて修正せず、原因と最小修正候補をOwnerへ報告する。

Git外詳細Evidenceには入力・catalog・実行codeのbinding、人間の6件判定と理由、保存再読込、
14項目の確認済み / 未確認を残す。管理文書は件数・CONFIRMED / REVIEW・再validation・安全停止・
production DB / PH不変・非対象未実行の最小集計にし、商品名 / ASIN一覧 / raw catalog / credentialを貼らない。

結果はCURRENT_WORK更新と新しいDecision追記で記録し、既存DECを上書きしない。
mandatory technical gates、最新対象Owner Acceptance Summaryと明示的最終merge承認後だけformal mainへ採用する。
merge後の最新main / PR MERGED / accepted対象binding・Validate・snapshot・read-only Verify確認まで完了してDONEとする。
WAITING_APPROVAL時は同じタスクを維持する。実運用DB replaceは受入後の別独立工程へ残す。

失敗時は専用DBと今回のGit除外artifactだけを破棄可能とする。既存Evidence・request試行記録は保持する。
文書差分は通常revert。production DB、PH、Bridge、credentialの復旧を必要とする構成にしない。
force push / dirty resetは行わない。
