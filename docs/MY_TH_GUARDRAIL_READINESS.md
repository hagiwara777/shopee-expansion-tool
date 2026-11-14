# MY / TH Guardrailの準備状況

既存Repositoryの資料と判定コードを調べた結果。国の法令やShopeeの現行規制を
網羅・確認済みという意味ではない。現在はDEC-0189によりMY・TH・TWをSoraの国別判定・通過出力へ接続する。
国別CSV辞書は追加せず、rules.jsonと各国Counterfeit一覧を使う。Governanceは3か国ともINACTIVE／ALLOWEDを維持する。
初版の完成対象はSG・PH・MY・THの4か国とする（DEC-0193）。Ownerが実際に出品する際に通過・要確認・停止の結果を目視で確認し、見逃し・止めすぎはその都度の修正タスクで対応する。件数・回数を固定した専用の確認工程は設けない。
MY・THのACTIVE化はOwnerの指示があったときに別タスクで行い、現在のINACTIVEを維持する。MY・THの実出品時の確認はACTIVE化と必要な別承認が成立した後に行う。
TWは初版の対象外とし、DEC-0192の完成確認・展開の当面見送りを維持する。既存のTWルールと判定接続は削除しない。この方針変更を初版完成や実商品の確認済みとは扱わない。

## 保存資料の調査履歴（DEC-0189以前）

以下は保存時点の準備状況であり、現在のSora接続範囲は上記とDEC-0189を適用する。
販売規制ガイド2026-08-13版の個別条件はOwner提示を根拠とし、保存済み旧資料の版を検証済みとはしない。

| 判断材料 | MY | TH | 保存時点の扱い |
| --- | --- | --- | --- |
| SLSカテゴリー条件 | 2,162レコード | 1,790レコード | 国別JSONとmanifest・出典を保存済み。判定actionは未実装 |
| Community NG | ASIN照合3行・Brand照合8行 | ASIN照合2行・Brand照合8行 | 国別の正規化資料あり。照合行数であり、全禁止商品の件数ではない |
| 武器画像検査の対象 | 初期設定あり | 初期設定あり | 共通selector＋独立国別JSON。国別規制の受入を意味しない |
| 販売規制ガイド | 対象市場として登録済み | 対象市場として登録済み | 元PDFと派生TXTのSHA登録あり。資料日付・版・取得URLは未確認 |
| 国別禁止Brand・危険語辞書 | 未作成 | 未作成 | 現在の国別辞書はPH / SGだけ。MYは共通ルールとIPR等だけで評価し、通過は出さない（DEC-0184） |
| Shared Battery・SLS評価処理 | 共通電池REVIEWは適用（SLSカテゴリ条件は未接続） | 未接続 | 共通処理を再利用できる。THへは未適用 |

SLSのMYは現行canonical一覧の欠落0、THは372 IDが未収録。
THのID 102009には異なるカテゴリーidentityが重複する既知の資料上の問題がある。
既存provenanceを保持し、未収録・曖昧さをALLOWへ変換しない。
これらを理由に新しいBeta MUSTや全面的な資料収集を先に追加しない。

MY / THの初期開発を始める土台はある。ただし、この資料を読み込むだけで
Guardrailが完成するわけではない。着手時に既存資料の国別条件を読み、
BLOCK / REVIEWへどう適用するかを定め、国別辞書・評価処理・回帰テストへ接続する。
PH / SGの国固有規則やIDをコピーしない。資料で判断できない商品は保留する。

資料の最新版が別にある場合は現行のsource identityと照合して更新する。
現在登録されている販売規制ガイドの版が不明なため、最新規制を確認済みとは扱わない。
個別の条件を現行規制として採用する際に、当該条件の公式根拠・更新日を確認する。
いま追加資料の提出を必須にはしない。具体的な不明条件が出た際に必要な資料を絞る。

根拠は `guardrails/sls_market_categories/markets/{MY,TH}.json` と各manifest、
同ディレクトリのREADME・provenance、`guardrails/community_ng/`、
`docs/evidence/GUARDRAIL_SOURCE_MANIFEST.csv`、`data/image_inspection/{my,th}.json`、
`modules/guardrails.py`。市場の稼働状態は `governance/state.json` を参照する。
