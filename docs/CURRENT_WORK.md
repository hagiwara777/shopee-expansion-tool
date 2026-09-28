# CURRENT WORK

本書は再開案内。長寿命の承認済み状態は`governance/state.json`、branch/HEAD/PR/checksはGit/GitHub、タスク固有状態はrepo外Task Contextを参照する。

## 現在の単一作業

SG production Category catalog import offline preflightの最小実装候補とfixture / tmp DB検証を完了した（DEC-0094）。normalized Category全件からSG正式6列CSVを決定的に生成し、全件validation後に既存SG-only transactional replaceへ渡す経路を追加した。formal mainへの採用・実production catalog受入はまだ行っていない。

判定は`IMPORT_PREFLIGHT_STOP`、reasonは`PRODUCTION_NORMALIZED_CATEGORY_DATA_NOT_AVAILABLE_OFFLINE`。DEC-0093のsource identity確認にbindingしたproduction normalized Category全2,285件をofflineで利用できず、synthetic testsをproduction import受入へ昇格しない。

## Required Decisions

- DEC-0072 / DEC-0073 — Governance正本、protected capability、通常開発とformal mergeの承認境界。
- DEC-0079 / DEC-0081 — SG全件validation、SG-only replace、保存済みmappingのcurrent catalog再validation、listing_ready=false。
- DEC-0082 / DEC-0084 / DEC-0085 / DEC-0086 — 共通Catalog / Access Token Source、Bridge、既知freshness制約。
- DEC-0088 — Decisionの段階的読込とappend-only正本。
- DEC-0089 / DEC-0090 — PH/SG Catalog Client契約とformal main採用範囲。
- DEC-0091 / DEC-0092 — OwnerコメントEvidenceとTrust Anchor v1.1移行の承認境界。
- DEC-0093 — production source identity PASSの意味、2,285件の確認事実、未受入境界。
- DEC-0094 — offline import最小経路、fixture検証、production全件データ不足によるSTOP。

## 確認済みと停止境界

SG suiteは63 passed、offline全体は1,515 passed、PH/SG protected回帰は598 passed。SG pathは親pathと自身nameの完全一致を要求し、余分な中間segmentを拒否する。tmp DBで不正入力時のSG不変、SG完全置換、古いSG ID削除、PH不変、schema不変、INSERT失敗時rollbackを確認した。既存testsで保存済みmappingのcurrent ID / path / leaf再validationとlisting_ready=falseを確認した。

production API、Google Bridge変更、credential変更、production raw response保存、実運用DB replace、migration、実商品受入、Brand / Attribute / SLS runtime、handoff、deploy、operation ACTIVE化、自動確定・出品は実行していない。Client、shared AI Core、Store、Safety、Candidate 15列、Prelisting Gate、governance/state.jsonは変更しない。既存dirty PH作業ツリーのファイルを編集・整理していない。

## 次の単一作業・rollback

次に必要なのは、SG代表shop / marketplace / source identity実行とのbindingとprovenanceを確認できるproduction normalized Category全件をGit外のoffline入力として用意すること。保存済みの正規データがない場合は、production read-only再取得とnormalized全件のGit外保存について別Owner明示承認が必要であり、本タスクでは取得しない。その全件を同じ変換・parse・tmp DB replaceへ通すまでIMPORT_PREFLIGHT_PASSにしない。実運用DB replace・実商品Category acceptance・formal main mergeは別の受入境界を維持する。

rollbackは今回のSG-local code / tests / docs差分の通常revert。DB migration、State、credential、PH運用の変更を伴わない。force pushとdirty resetは行わない。
