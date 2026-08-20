# PH Minimum Beta 実物受入プロトコル

## 1. 目的

このプロトコルは、PH Minimum Betaが次の流れを実務で使い始められるかを、安全かつ再現可能に受け入れるための実行手順、判定、Evidenceを定める。

`候補生成 → PH Safety → Category / Brand確認 → 人間へのhandoff`

性能最大化、完全自動化、provider最適化、固定KPIの達成は目的ではない。

## 2. 前提

- formal main上で、B1〜B7の確認済み`MISSING_IMPLEMENTATION`は0件である。
- 本番標準providerはKeepa、Canopyは開発・試験専用である。
- providerの自動fallbackは行わない。Canopy結果をKeepa本番確認の根拠にしない。
- 残るBeta MUSTはKeepa live確認とPH実物受入である。これらは未実施のままである。

## 3. 二段Gate

### Gate K — Keepa本番標準経路live技術確認

Gate KはGate Pより先に行う。対象はASIN ExpansionとASIN Resolverであり、通常Keepa providerによる本番標準経路を確認する。Canopyで代替しない。

### Gate P — PH Minimum Beta実物受入

Gate PはGate Kが`GATE_K_PASS`のときだけ行う。対象はCandidate、PH Gate、Category、Brand / No Brand、安全な停止、`listing_ready`、人間へのhandoffである。

## 4. Gate Kの実行前条件

この文書の正本化ではGate Kを実行しない。将来の実行には、オーナーによるKeepa利用および有料API利用の明示承認を別途必要とする。実行前に次を確認する。

- formal main、実行branch / HEAD、provider = Keepa、対象シナリオ
- credentialの利用可能性、API利用範囲、費用承認、再試行条件
- 外部サービスへの書込みがないこと、Canopy fallbackがないこと

API keyその他credential値はGit、Evidence、報告へ記録しない。Keepa承認をShopee API承認へ流用しない。

## 5. Gate K1 — Expansion

実ASINを起点に通常Keepa providerでExpansionを実行する。

- `PASS`: Keepa live通信、source ASINのFact取得、Expansion正常終了、Candidate出力までが成立する。
- `INCONCLUSIVE_SOURCE`: APIと処理は正常だがCandidateが0件で、入力sourceの適合性を判断できない。
- `STOP_KEEPA_LIVE`: 認証、契約、API error、実装例外等により本番経路自体が成立しない。

Candidate 0件だけを実装FAILと扱わない。自動再試行しない。

## 6. Gate K2 — Resolver

Resolver候補のAmazon URL / ASINを通常Keepa経路で確認する。

- `PASS`: Keepa live確認、`FOUND`、`KEEPA_VERIFIED`相当、Candidate出力までが成立する。
- `INCONCLUSIVE_INPUT`: 入力候補自体がKeepaで見つからず、入力適合性を判断できない。
- `STOP_KEEPA_LIVE`: Keepa本番経路自体が成立しない。

Canopy確認結果をPASS根拠にしない。

## 7. Gate K全体判定

- ExpansionとResolverの双方がPASS: `GATE_K_PASS`
- 片方でも未判定またはINCONCLUSIVE: `GATE_K_INCONCLUSIVE`
- Keepa本番経路自体が成立しない: `GATE_K_STOP`

`GATE_K_PASS`以外ではGate Pへ進まない。STOP後、またはINCONCLUSIVE後に、自動実装・自動修正・自動再試行へ進まない。

## 8. Gate Pのサンプル方針

固定件数KPI、時間目標、候補件数目標は設定しない。少なくともExpansion入口とResolver入口を実物で確認し、全体として少なくとも1件がPH GateからCategory / Brand確認を通ってhuman handoffまで到達することを確認する。

正当にREVIEW / EXCLUDE / 未確定で止まり、readyへ1件も到達しない場合は、即Beta FAILにせず`INCONCLUSIVE_SAMPLE`とする。追加サンプルの実行はオーナー判断へ戻す。

## 9. B1〜B7実物受入基準

### B1 Candidate

Expansion / Resolver双方を実物操作でき、Keepa確認済み候補をGate用入力へ渡せる。

### B2 PH Safety

marketplace PHを明示する。EXCLUDEと未解決REVIEWをreadyへ進めず、ELIGIBLEだけをCategory / Brand確認へ進める。

### B3 Category

ELIGIBLE候補が実在する確認済みShopee Category IDへ到達する。推測だけでconfirmedにしない。

### B4 Brand / No Brand

実在Brand ID、またはカタログ上で利用可能なNo Brandを、人間が明示確認できる。

### B5 Safe Stop

Category、Brandその他のBeta準備情報を確認できない候補を、推測値で`listing_ready`にしない。

### B6 Ready

`GATE_ELIGIBLE`、Category confirmed、Brand confirmedまたは明示No Brand、manual review不要の全条件を満たすときだけ`listing_ready`とする。`listing_ready`を「Shopee出品可能」とは扱わない。

### B7 Handoff

ready候補について人間がAmazon ASIN、Shopee Category ID、Shopee Brand ID / No Brandを画面またはファイルから取得し、既存出品ツールへの手入力準備に利用できる。自動投入、保存、出品は要求しない。

## 10. B7と外部出品ツール

既存出品ツールの正式入力契約はBeta MUSTではない。Beta受入では、現行handoff情報を見て人間が実際の手入力作業を開始できるかをオーナーが確認する。入力画面で対応項目を確認してよいが、保存、送信、出品その他のlive書込みは別承認なしに行わない。

## 11. mandatory attribute

mandatory attributeの全面対応はBeta MUSTではない。ASIN / Category ID / Brand IDが揃っていてもmandatory attribute不足により実際の手入力準備が成立しないと実物で確認された場合だけ、`BETA_BLOCKER_CANDIDATE: MANDATORY_ATTRIBUTE`としてオーナーへ戻す。「あれば便利」または手入力が少し増えるだけではblockerにしない。

## 12. Shopee API

まず既存のローカルCatalog Factを使う。Category / Brand確認に必要なFactが不足しShopee read APIが必要になった時点で、別のオーナー明示承認を得る。Shopeeへのlive書込みは行わない。

## 13. 判定区分

- `PASS`: 必要なGateとB1〜B7が成立し、オーナーが実務で使い始められると確認した。
- `INCONCLUSIVE`: サンプル不適合、候補なし、入力候補不一致、一時的外部要因などで材料が不足する。実装FAILとは確定しない。
- `STOP`: 未承認外部API、provider不一致、credential / 契約問題、外部書込みが必要など、安全に継続できない。
- `BETA_BLOCKER_CONFIRMED`: B1〜B7の成立を妨げる具体的事実を実物で確認した場合だけ使用する。

blocker確認後も自動修正しない。最小対応が必要な場合は、別途オーナー承認を得てから範囲を決める。

## 14. 重大停止条件

少なくとも次では停止する。

- EXCLUDEまたは未解決REVIEWが`listing_ready`になる。
- 未確認Categoryまたは未確認Brandがreadyになる。
- PH以外として処理される、またはCanopyがKeepa確認を代替する。
- 未承認API、有料処理の承認範囲外、外部サービスへの書込みが必要になる。
- 現行handoffで実務的な手入力準備が成立しない。

STOP後に自動実装・自動修正へ進まない。

## 15. Evidence

Gate実行時には最低限、formal main commit、実行branch / HEAD、provider、Gate K1結果、Gate K2結果、Gate K全体判定、Gate Pの入口種別、B1〜B7各判定、実施した外部API、実施していないAPI / 書込み、blocker / inconclusive理由、オーナー実物確認結果、次の単一作業を記録する。

商品CSV本文、credential、秘密情報をGitへ記録しない。スクリーンショットまたはraw結果を正式Git外Evidenceとして保存する必要がある場合だけ、artifact ID、ファイル名 / 版、完全SHA-256、producer、受入状態、storage alias、用途、実物アクセス要否を正式索引に記録する。

## 16. Beta最終判定

`GATE_K_PASS`、Gate PでのB1〜B7実物受入成立、オーナーが実務で使い始められるとの確認がそろった場合だけ、Minimum Beta受入候補とする。最終的な事業上のBeta受入はオーナーが決裁する。
