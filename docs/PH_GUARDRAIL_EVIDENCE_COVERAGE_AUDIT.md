# PH Guardrail 根拠・カバレッジ監査（v1）

## 目的と範囲

PHの出品前保安ゲートが、アカウントへの大きな影響が想定される「一発アウト」候補をどこまで自動的に止められるかを明確にする。網羅的な規約適合判定を目的にしない。その他の不確実な候補は、人が試すかを判断する`REVIEW`として残す。
この文書は、出品可否、法令適合、Shopeeの承認を保証するものではない。実商品、外部API、Shopeeへの書込みは行わない読み取り専用監査である。

- 監査日: 2026-08-03
- 監査基準: main `a364b42d09afd11ba61b556ead675d677652aa70`
- 対象: `modules/guardrails.py`、`modules/prelisting_gate.py`、PH辞書、関連テスト、Shopee PH公式ポリシー
- 対象外: 辞書ルールの追加・削除、実商品判定、法的助言、Shopeeへの出品

## 現在のGuardrailの意味

PHを選択したGateはPH専用辞書だけを読み込む。辞書や判定結果の契約が壊れている場合は、SG辞書へ代替せず処理を停止する。

- `BLOCK` はGateで `EXCLUDE` になる。
- `REVIEW` はGateで `REVIEW` になり、人の確認が必要である。
- `ELIGIBLE` は、現在のPH辞書、既出品照合、重複、起点ASIN、必須メタデータの確認を通過した状態である。

したがって、`ELIGIBLE` は「現在のフィルタで止める理由が見つからなかった」という意味に限る。Shopeeの出品承認、法令適合、知的財産権の安全性を保証する表示ではない。

## 辞書とテストの確認結果

| 項目 | 確認結果 |
| --- | --- |
| PHブランド専用辞書 | 0ルール。ファイルの契約ヘッダーだけを保持する。 |
| PHリスクキーワード辞書 | 89ルール（`BLOCK` 31、`REVIEW` 58）。 |
| ルールの出典区分 | `shopee_policy` 23、`own_penalty_case` 7、`internal_rule` 59。 |
| 市場の分離 | PH実行時にSG辞書が混ざらないことをテスト済み。 |
| 各PHルール | すべての`BLOCK`、`REVIEW`ルールが自分の用語に対して期待どおり判定されることをテスト済み。 |
| 異常時 | PH辞書の欠落・不正値・Gate出力の契約不一致は安全側で停止することをテスト済み。 |

各PHルールには、出典区分、日付、規制上の位置付け、当社運用の注記がある。一方で、このリポジトリ内には、各ルールが参照する公式ページの保存コピー、URL対応表、更新履歴を一元管理する証拠台帳は見つからなかった。注記だけでは、将来の公式ポリシー改定を再照合しにくい。

## Shopee PH公式ポリシーとの照合

一次資料は、Shopee PHの[Prohibited and Restricted Items Policy](https://help.shopee.ph/portal/4/article/77276?previousPage=other+articles)（ページ表示の最終更新日: 2025-04-28、2026-08-03確認）と、[Terms of Service](https://help.shopee.ph/portal/4/article/77272-Shopee-Terms-of-Service)である。前者は禁止・制限品の案内を網羅的ではないものとしており、更新確認を求めている。後者は、知的財産権を侵害する出品を認めず、ポリシー違反等の出品を削除し得るとしている。

| 公式ポリシーの主な分類 | 現在のPH辞書 | 現時点の扱い |
| --- | --- | --- |
| 医薬品、医療・治療表現、検査キット、中古化粧品 | 30ルール | 一部は`BLOCK`、文脈や許認可の確認が必要なものは`REVIEW`。**部分対応**。 |
| 武器、スタンガン、催涙スプレー、たばこ・Vape | 12ルール | 該当語を`BLOCK`。表記ゆれ、付属品、全品目の網羅性は未検証。**部分対応**。 |
| 酒類、食品、農薬、危険な配送物 | 30ルール | 主に`REVIEW`。免許、期限、梱包、成分、配送可否の証拠までは自動確認しない。**部分対応**。 |
| 通信機器・監視機器の登録要件 | 無線機の一部を`REVIEW`する7ルールのみ | 登録確認や監視機器の網羅的な判定はできない。**不足**。 |
| 模倣品、無許諾品、商標等の知的財産権 | PHブランド専用辞書は0ルール | ブランドや真贋を自動的に通してよい根拠がない。**重大な不足**。 |
| 動植物、古物、通貨・カード、政府・警察用品、鍵開け用品、宝くじ、リコール品 | 対応するPH分類・ルールを確認できない | 自動判定の根拠なし。**不足**。 |
| 成人向け、政治的・攻撃的表現、違法出版物、盗品、誤表示、禁止サービス | 成人向け語3ルールを`REVIEW`するのみ | それ以外を自動的に扱う根拠なし。**不足**。 |
| その他の法令・安全上の制限 | 包括的な判定はできない | タイトルのキーワードだけでは判断不能。**人の確認が必須**。 |

この表は「辞書にキーワードがあるか」の照合である。各カテゴリを完全にカバーすることを目標にせず、明確な一発アウト候補を見逃さないための優先順位付けに使う。

## 運用上の結論

現在のPH Guardrailは、初期運用で明らかな危険候補を早めに止める保守的な第一段階として利用できる。一方、次を理由に、これだけでPHへの出品を判断してはならない。

1. PHのブランド・知的財産リスクを自動で除外するルールがない。
2. 公式ポリシーの複数カテゴリに、辞書上の対応がないか、部分対応しかない。
3. ルールの根拠は注記に残るが、公式資料との対応表・保存証拠・定期見直しの仕組みがない。
4. 実商品での見逃し・過剰停止の測定は未実施である。

## 次の扱い

当初提案した独立した`PH Guardrail Block Register v1`は、DEC-0025により採用しない。既存31件の`BLOCK`ルールの分析は、`docs/PH_GUARDRAIL_KEEPA_FIELD_IMPACT_ANALYSIS_DRAFT.md`へ統合し、結論はHOLDとする。

この分析資料はレビュー用であり、運用ルールの正本である市場別Guardrail辞書CSVを置き換えない。`REVIEW`は、完全にアウトとは言えない候補を人が試すか判断するために残す。ブランド・知的財産、許認可、公式ポリシーの未対応分類を、根拠なしに一律`BLOCK`へ広げない。ルール追加、実データテスト、Shopeeへの書込みは別途承認が必要である。

## P1a追補 — PH Guardrail Evidence Coverage Inventory（2026-08-27）

### 判定範囲とP1a状態

この追補は、formal main `0626a6504af15ebc0a1723a13dcac613aef7e676` 上のGit管理内の辞書・実装・既存監査記録と、`CURRENT_WORK.md` のGit外成果物索引を照合した棚卸しである。coverageは「現在どのルールが登録されているか」の事実だけを表し、根拠の有効性、BLOCK / REVIEW / 非対象・根拠不足のdisposition、または辞書変更を決めない。

Git外の固定storage alias `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Sources/` に配置されたSLS、Community NG、PH restriction imageの実物を読み取り、各ファイルのSHA-256を計算した。3件すべてが`CURRENT_WORK.md`の正本索引値と完全一致したため、P1aの実物確認は **完了** とする。外部サービス・外部API・live Shopee pageは使用していない。この確認は根拠内容のdispositionまたは辞書変更を意味せず、次の判断はP1bで行う。

`VERIFIED` は今回の実物と完全SHA-256を照合できた状態、`NOT_AVAILABLE` は索引のみで実物に到達できない状態、`INDEX_ONLY` はGitまたは索引で参照・登録状況だけを確認できた状態を表す。

### 一次・公式・運用Evidence

| Evidence / source ID | source名・種別 | PH対象・版 / integrity reference・storage alias | 実物アクセス | 現行Guardrailでのcoverage（登録事実のみ） | P1bで追加判断 |
| --- | --- | --- | --- | --- | --- |
| `SHOPEE_PH_PROHIBITED_RESTRICTED_POLICY` | Shopee PH Prohibited and Restricted Items Policy / Shopee公式 | PH / ページ最終更新日 `2025-04-28` は既存監査の記録。Git ref: formal main の本書「Shopee PH公式ポリシーとの照合」 | `INDEX_ONLY`（`LIVE_RECHECK_REQUIRED`） | V1注記で直接参照する17ルール（`BLOCK` 8、`REVIEW` 9）。既存監査の分類照合は部分対応または不足であり、完全coverageではない。 | 要 |
| `SHOPEE_PH_TERMS_OF_SERVICE` | Shopee PH Terms of Service / Shopee公式 | PH / 版・現行性は今回未確認。Git ref: formal main の本書「Shopee PH公式ポリシーとの照合」 | `INDEX_ONLY`（`LIVE_RECHECK_REQUIRED`） | V1 / V2にこのsource IDの直接参照はない。既存監査では知的財産リスクの一般根拠として扱うが、PHブランドV1辞書は0件。 | 要 |
| `OWNER_SOURCE_SLS_PROHIBITED_CATEGORY` | `【SLS対象マーケット】SLS出品可否確認表（Prohibited Category List）2025年3月17日適用.xlsx` / SLS | PH / ファイル名は2025-03-17適用、索引SHA-256 `ee68151aa951921dfb7c8a5ea76ea67441342b5be5511d4b18905591e4c621c2` / `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Sources/【SLS対象マーケット】SLS出品可否確認表（Prohibited Category List）2025年3月17日適用.xlsx` | `VERIFIED`（実物SHA-256一致） | V1注記が明示するSLS由来11ルール（`BLOCK` 3、`REVIEW` 8）。別表記の「Shopee Japan販売規制ガイドPH欄」23ルール（`BLOCK` 9、`REVIEW` 14）との同一資料性は今回のSHA照合対象外。 | 要 |
| `OWNER_SOURCE_COMMUNITY_NG_LIST` | `ＮＧリスト.xlsx` / community operational（オーナー提供） | PH / 版指定なし、索引SHA-256 `82a4b72cfdfa53fdfec87f00685ea3f81ced6bde747e54a71155e56ef92312d1` / `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Sources/ＮＧリスト.xlsx` | `VERIFIED`（実物SHA-256一致） | Rule V2のブランドexact 13ルール（`PH-V2-BRAND-001`〜`013`）がこの`evidence_ref`を持つ。元リストの全件および13件との対応はP1bで判断しない限り確定しない。 | 要 |
| `OWNER_SOURCE_PH_RESTRICTION_IMAGE` | `2026-08-13_121116.png` / オーナー提供 | PH / 2026-08-13、索引SHA-256 `7df6f6196b7ad4ac7a63a380f3eb3c03a3b6ab661bd4941152b6a4484196a681` / `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Sources/2026-08-13_121116.png` | `VERIFIED`（実物SHA-256一致） | V1 / V2にこのartifact IDを直接参照するルールは確認できない。 | 要 |
| `ART-PH-GABA-FREEZE-OWNER-ATTESTATION-V1` | `PH_GABA_Freeze_Community_Report_Owner_Attestation_v1.md` / community operational owner attestation | PH / v1、索引SHA-256 `cc6b369250bedb0a99c9731e438e420ee1e2bccd14721e75546aa2f191919a88` / `LOCAL_GITEXCLUDED_PH_GABA_EVIDENCE_V1` | `INDEX_ONLY` | Rule V2のIngredient Safety 6 alias（`PH-V2-INGREDIENT-GABA-001`〜`006`）がこの`evidence_ref`を持つ。索引と既存Ruleの照合のみで、原コミュニティ投稿はP1aの再取得対象外。 | 要 |

### Git注記だけで確認できる追加source reference

次のsourceはV1辞書の`note`に記録されているが、今回到達可能な実物・artifact ID・SHA-256はない。元Evidenceが未照合のまま、現在のルール登録を根拠の有効性またはP1bの結論として扱わない。

| source reference | 種別 | 実物アクセス | 現行coverage | P1bで追加判断 |
| --- | --- | --- | --- | --- |
| 自社SGペナルティ・削除事例 | 自社実害（originはSG、現行辞書でPHに適用） | `INDEX_ONLY` | V1 7 `BLOCK`（`own_penalty_case`） | 要 |
| Philippine FDA medical-device framework（2021と注記） | 外部規制reference | `INDEX_ONLY` | V1 1 `REVIEW` | 要 |
| Shopee PH policyとNTC rules | Shopee公式 / 規制referenceの複合注記 | `INDEX_ONLY` | V1 3 `REVIEW` | 要 |
| Shopee PH policyと当社決定 | Shopee公式 / internal ruleの複合注記 | `INDEX_ONLY` | V1 4 `REVIEW` | 要 |

### 派生監査Evidence（一次根拠ではない）

| Evidence ID | source名・SHA-256・storage alias | 実物アクセス | 現行coverage | P1bで追加判断 |
| --- | --- | --- | --- | --- |
| `GAR-AUD-CLASSIFICATION-CANDIDATES` | `classification_candidates.csv` / `b6c0329e1d5d63a38507c34588ca95e0c8483a05614c4bb711f27ea0a4dc2832` / `LOCAL_GITEXCLUDED_GUARDRAIL_AUDIT_CLASSIFICATION_CANDIDATES` | `INDEX_ONLY` | 現行辞書の根拠ではない。過去の候補分類の比較資料。 | 不要（一次Evidenceの代替不可） |
| `GAR-AUD-SUMMARY` | `audit_summary.md` / `0f76e38904c6f4eeaa6be3338f75dbb15c10725260b5e0ba2451a431d14efeb1` / `LOCAL_GITEXCLUDED_GUARDRAIL_AUDIT_SUMMARY` | `INDEX_ONLY` | 現行辞書の根拠ではない。過去監査の要約資料。 | 不要（一次Evidenceの代替不可） |
| `GAR-AUD-EXISTING-DICTIONARY-COMPARISON` | `existing_dictionary_comparison.csv` / `c5a2c6faaf5d24ca722d406e571bcdd669c1a271e5779c96a6d2be6370cbd180` / `LOCAL_GITEXCLUDED_GUARDRAIL_AUDIT_EXISTING_DICTIONARY_COMPARISON` | `INDEX_ONLY` | 現行89 V1ルールとの過去比較資料。 | 不要（一次Evidenceの代替不可） |
| `GAR-AUD-NEW-CANDIDATE-EXISTING-COVERAGE` | `new_candidate_existing_coverage.csv` / `e545583f8b3765ddecadc6878128f95e446bd358bfb2ea3f7162475495b9b08b` / `LOCAL_GITEXCLUDED_GUARDRAIL_AUDIT_NEW_CANDIDATE_EXISTING_COVERAGE` | `INDEX_ONLY` | 新候補と既存辞書の過去比較資料。 | 不要（一次Evidenceの代替不可） |

### 現行辞書のcoverage snapshot

- V1: `risk_keywords_ph.csv` は89ルール（`BLOCK` 31、`REVIEW` 58）。source typeは`shopee_policy` 23、`own_penalty_case` 7、`internal_rule` 59である。`prohibited_brands_ph.csv` は契約ヘッダーのみで0ルールである。
- V2: `deterministic_block_rules_v2.csv` はPH `BLOCK` 19ルール（brand exact 13、Ingredient SafetyのGABA alias 6）。brand 13件の`evidence_ref`は`OWNER_SOURCE_COMMUNITY_NG_LIST`、GABA 6件の`evidence_ref`は`ART-PH-GABA-FREEZE-OWNER-ATTESTATION-V1`である。
- 実装: PH実行時だけV1 PH辞書とRule V2を読み、V2の`BLOCK`はV1結果を降格させない。これは`modules/guardrails.py`と関連testで確認できる実装事実であり、各sourceの有効性を確認した事実ではない。

P1aでは、一次Evidenceの実物と完全SHA-256を確認した。P1bで初めて、各項目を`BLOCK`、`REVIEW`、`非対象・根拠不足`へ判断する。このP1a追補では新しいBLOCK / REVIEW / 非対象判断、辞書変更、Rule V2 schema変更、外部API、live page再確認を行っていない。

## P1b開始前の判断基準正本化（2026-08-27）

この追補は過去監査およびP1a棚卸しを書き換えず、P1bを始めるためにDEC-0044が明確化した運用基準との関係だけを記録する。本文の「文脈や許認可の確認が必要なものは`REVIEW`」という一般表現は、当時のcoverage監査の記述であり、P1bのdisposition規則ではない。許認可が販売に必須で当社が取得しない対象は該当市場のBLOCKとする後続判断がこれをsupersedeし、DEC-0026、DEC-0027、DEC-0044を優先する。

- SLS出品可否確認表は市場別Evidenceである。PHではPH欄・PH条件だけを読み、他市場または複数市場のNG・条件をPH_BLOCKまたはCOMMON_BLOCKへ自動的に推測しない。
- SLS、`ＮＧリスト.xlsx`、PH制限参考画像はNG・禁止・制限を示すEvidence sourceであり、中立カタログではない。ただし、その全行をBLOCKとするのではなく、市場、条件、NG理由をP1bで確認する。
- community operational evidenceは公式Evidenceと区別する。市場、ブランドまたは商品、第三者販売で起きた具体的な警告、削除、違反、ペナルティ、制限または凍結の理由を確認できる場合は、DEC-0027の範囲で内部リスク回避BLOCKの根拠になり得る。正規品または有名ブランドであることだけで、ブランド・IPリスクを否定またはBLOCKすることはしない。DEC-0030の13 Brand-exact PH_BLOCKは維持する。
- REVIEWは、具体的な追加確認または対応によって販売可能性が残る場合だけに用いる。取得しない許認可を確認待ちREVIEWに置かず、許認可が必須で当社が取得しない場合は該当市場のBLOCKとする。市場固有の条件をCOMMON_BLOCKへ自動昇格しない。

この追補は個別EvidenceのBLOCK / REVIEW / 非対象・根拠不足をまだ決めず、辞書またはRule V2も変更しない。P1bの開始は、DEC-0044を含む正本化差分がmainへ統合された後とする。

## P1b Evidence disposition candidate（2026-08-28）

### Candidateの範囲とintegrity

`LOCAL_ARTIFACT_ROOT` を解決し、P1aの3一次Evidenceへ実物アクセスして完全SHA-256を再計算した。SLS workbook、`ＮＧリスト.xlsx`、PH制限参考画像は、いずれも本書および`CURRENT_WORK.md`の索引値と一致した。過去の727件分類candidateも索引SHA-256 `b6c0329e1d5d63a38507c34588ca95e0c8483a05614c4bb711f27ea0a4dc2832` と一致したため、P1bではその全727 `item_id`を保持し、現行DEC-0024 / DEC-0026 / DEC-0027 / DEC-0030 / DEC-0044で再dispositionした。

Git外artifact `PH_GUARDRAIL_P1B_DISPOSITION_CANDIDATE_v1.csv` は727行、SHA-256 `f1daed1bcdcb1388d42859b9050b216d665c0dff6853feb3fa4229f662bcae19`である。必須16列を持ち、`BLOCK` 243、`REVIEW` 125、`OUT_OF_SCOPE_OR_INSUFFICIENT_EVIDENCE`（非対象・根拠不足）359、未分類0件である。最後の区分はSAFEや出品承認を意味せず、PHの具体的な品目・条件・NG理由をこのEvidenceだけでは確定できないことを表す。

### P1bの判定結果

- SLSの全市場輸送禁止18件、PH欄`NO`170件、PH制限参考画像の明確なPH禁止等37件、PHで商品・ブランド・具体的NG理由を持つcommunity 14件は`BLOCK`とした。community 14件は公式禁止の主張ではなく、DEC-0027による当社内部リスク回避の根拠である。
- `一般用医薬品`、`医療用針`、およびSLSで必須許認可が示された商品は、当社が必要な許認可を取得しないというDEC-0026 / DEC-0027 / DEC-0044の方針により`BLOCK`とした。許認可待ちの`REVIEW`には置かない。
- SLSのPH `Shopeeと要確認`110件、全市場の具体的な発送前承認12件、PH画像の条件付き2件、および単体電池と電池内蔵機器を区別して承認可否を確認できる1件は`REVIEW`とした。各行には、何を確認し、未充足ならBLOCK、充足なら通過候補となるかを記録した。
- 311件のgeneric community NG、PH以外のみの41件、補助sheet等、資料間の条件境界を確定できない項目は`OUT_OF_SCOPE_OR_INSUFFICIENT_EVIDENCE`とした。PHのSAFEを意味せず、P1c候補にもしていない。資料間の矛盾は一律のBLOCK / REVIEWへ平坦化していないが、PH画像がアルコール飲料のオンライン販売禁止を明示する項目は、SLSの別条件がPH禁止を解除しないためPH `BLOCK`とした。

過去727候補との差異は分類ラベルの収束である。旧`COMMON_BLOCK_CANDIDATE`18件と`PH_BLOCK_CANDIDATE`221件は`BLOCK`、旧`REVIEW_CANDIDATE`124件は`REVIEW`、旧`INSUFFICIENT_EVIDENCE`314件と`OUT_OF_SCOPE_OTHER_MARKET`41件は非対象・根拠不足へ対応付けた。旧`OWNER_DECISION_REQUIRED`3件は現行の許認可方針により`BLOCK`、旧`SOURCE_CONFLICT`6件はアルコールを`BLOCK`、電池形態を`REVIEW`、残る4件を非対象・根拠不足とした。item IDの増減はない。

### 現行coverageと未実施事項

coverageは読み取り専用で確認した。V1 `risk_keywords_ph.csv`は89ルール（BLOCK 31、REVIEW 58）、`prohibited_brands_ph.csv`は0ルール、Rule V2はPH BLOCK 19ルール（既存Brand exact 13、既存GABA alias 6）である。PH community 14件のうち、Brand exact 13件は既存Rule V2を保持し、降格していない。Boseイヤホン／ヘッドホンは具体的community Evidenceに基づくPH BLOCKとしてcandidateへ残すが、既存のBrand exact ruleへ広げず、P1c候補scopeだけを示した。GABA 6 aliasは、P1aの再取得対象外だったowner attestation索引に結び付く既存BLOCKとして保持し、本candidateによって変更・降格していない。

Shopee PHの[Prohibited and Restricted Items Policy](https://help.shopee.ph/portal/4/article/77276?previousPage=other+articles)と[Terms of Service](https://help.shopee.ph/portal/4/article/77272-Shopee-Terms-of-Service)は、2026-08-28にCodexがread-onlyで独立再確認した。前者は2025-04-28更新のままで、禁止・制限違反に対するlisting deletion、account privilege制限、suspension/terminationを明記する。これは公開ページの現行性確認であり、保存された一次Evidence、辞書、Rule V2、またはP1cの実装を置き換えない。

このcandidateは`CANDIDATE / OWNER_ACCEPTANCE_PENDING`であり、P1bの正式完了、P1c、辞書変更、Gate P再開を意味しない。次はオーナーが分類とP1c候補scopeを受入する単一作業である。
