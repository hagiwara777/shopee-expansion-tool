# PH Betaを基準とする市場展開

## 固定する最初の完成目標

2026-10-04時点のPH Beta（正式基準commit `42eb460ff87a6f45a497fb345064de616418a1dd`）の
操作と支援機能をSG / MY / THの初期到達目標とする。PHの後続改善を自動的に初期必須条件へ加えない。
事業目的はShopee出品準備の人手を減らすこと。自動出品や全面自動化を初期目標に含めない。

| 機能 | 共通処理 | 市場ごとの情報・条件 |
| --- | --- | --- |
| Expansion / Resolver | 候補取得・検証の二つの入口 | リサーチCSVの国・URL・発送元 |
| Safety / 重複 | 判定・根拠提示・人間確認・既出品照合 | 禁止条件、要確認条件、画像・文章の適用条件、ショップ在庫 |
| Category | AI候補提示、検索、確定・再利用、グループ確認 | 当該市場の現在catalog・ID・path・必須属性 |
| Brand / No Brand | 候補検索、明示確認、保存・再検証 | 実ID・名称・No Brand分類、取得完全性・商品単位確認 |
| 発送条件 | Category確認後の停止・理由表示 | 市場別SLS条件・根拠 |
| 出品準備 | 確認状況表示、CSV / TXT取得 | 必須項目・形式・市場binding |

同じUIでも適用ルールは各国の情報を使用する。PHの禁止条件やIDを他市場へコピーしない。
未確認商品を推測で準備完了にしない。No Brandは候補なし時の自動fallbackにしない。
PHの既存operationとSG Safetyを回帰保護し、市場間の確認記録を混用しない。

## 実装順

1. SGの不足機能を埋める過程でPH / SGの確認処理を共通化する。
   最初の追加は共通Brand検索と、既存SG Brand契約を使う隔離offlineの画面部品。
   明示注入したoffline clientを使い、SG画面のCSV読込・Category確定・Brand取得・保存へ接続する。
   AI結果表示をPHと共通化し、明示注入したoffline engineによるSG候補提示・人間採用も検証する。
   隔離画面では同じKeepa Category / Brandの商品群に対する人間Category確認を一括保存する。
   現在のSG ID / path / leafをtransaction内で再確認し、失敗時に一部だけ保存しない。
   グループCategory採用でBrand / No Brandを一括確定せず、各商品の確認・再validationを維持する。
   SG属性は明示offline取得・session保持・現在Category再validationを行い、未取得を0件と扱わない。
2. Category AI、グループ確認、説明Factによる既存の自動安全判定・対象商品の武器画像検査、必須属性表示、出品準備出力を
   固定PH基準との差として扱い、必要な差分だけ順に実装・検証する。
3. PH / SGの機能と停止条件を確認し、実環境への採用・必要なlive確認を別に実施する。
4. 共通moduleと市場別adapter / 情報を再利用してMY / THへ展開する。
   MY / THのruntimeと国別判定をSG開発中に先行有効化しない。

## 完成判定と履歴

SG Step 8の半手動Beta受入は履歴として維持する。PH相当の機能統一は新しい開発目標であり、
Step 8受入だけを根拠に機能統一済みとは扱わない。
各機能はコードの存在だけで完了にせず、画面操作・保存再利用・停止維持・出力を確認する。
Fake / synthetic確認はliveの精度・認証・実務受入の代替ではない。

本方針はscope内のlocal開発を指定する。正式main採用、実API・有料API実行、通常DB移行、
起動先変更、SG operation開始は各境界に必要な承認と確認に従う。
現在の通常SG画面はBrand保存・live AI・出品準備出力を有効化しない。
開発画面の明示Brand取得は完全取得時のみ候補を有効とし、入力変更・再取得失敗・未完了で
過去のcurrent catalogを利用しない。取得はボタン操作時だけとし、rerunで自動取得しない。
AI候補は人間採用時にcurrent SG ID / path / leafを再検証する。
ABSTAIN / FAILED / catalog不整合では手動確認を残し、confidenceだけで確定しない。
開発用確認状況CSVはDEVELOPMENT_AUDIT_ONLYと全件listing_ready=FALSEを明示し、
出力直前にCategory / Brand / SLSを再検証する。出品用CSV / TXTの出口開放とは区別する。
説明・画像がそのASINの商品に合うかを全商品で人間確認する追加機能は削除する（DEC-0125）。
説明Factは既存SG Guardrail / Shared Batteryの自動判定へ渡し、BLOCK / REVIEWを解除しない。
画像は武器・武器形状の疑義検出にだけ使用し、PHの画像取得・AI問い合わせ処理を共通adapterから再利用する。
対象選択は共通moduleと国別設定を使い、対象外では画像表示・画像検査・人間判断を要求しない。
WeaponImageReviewSessionは武器画像の評価と、その疑義に対する人間判断だけを扱う。
検査がCOMPLETED / NO_SIGNALなら、画像由来の追加の人間判断は不要。
REVIEW / INDETERMINATE / PARTIAL / UNAVAILABLE / ERRORは武器疑義・判断不能として停止する。
対象画像と判断根拠を確認した人間判断は画像由来の停止にだけ適用し、既存Safety / Battery / SLSを解除しない。
全体の認証・設定・応答契約失敗は出力を停止し、明示的な正常再実行を必要とする。
商品資料・root・国別設定・画像評価が変われば古い武器画像の判断を失効させる。
通常画面のlive factoryは設けず、明示承認枠付きの隔離実接続modeはDEC-0124で区別する。
隔離SG画面は元Candidate CSV、PRODUCT_TEXT_SAFETY_FACT_V1、未評価PH_IMAGE_SAFETY_V1の
raw Factを明示読込し、両sidecarのCandidate SHA・ASIN集合・providerとSG eligible商品情報を照合する。
元Candidateの一部だけがSG eligibleである場合も対応する。PH評価・人間判断は取込を拒否する。
資料変更・削除、SG入力変更、読込失敗でloaderと確認結果を失効させ、rerunだけでは資料を採用しない。
SHAはファイル対応の検証でありアップロードの真正性を証明しない。Gate CSVに元Candidate SHAがないため、
Gate判定の由来は暗号学的に検証済みとせず、搬送された商品情報の一致だけを確認する。
画像AI対象選択は`modules/image_inspection_policy.py`をPH / SGで共用し、
`data/image_inspection/{ph,sg,my,th}.json`で市場別のAmazon / Keepa大カテゴリーを管理する。
PH / SGはおもちゃ・ホビー・スポーツ＆アウトドア・DIY工具ガーデンの4 rootを初期対象とする。
root不明は対象、その他rootは対象外・未実行とし、AI疑義なしへ変換しない。
MY / THも同じ初期設定と選択契約を用意するが、runtime / Safety / 出品接続は後続工程とする。
対象外では画像表示・画像取得・画像AI・画像の人間判断を要求しない。既存Safety / SLS条件は維持する。
選択だけではAPI実行せず、明示一括実行の前に対象商品の過去確認を無効化する。
root変更・市場設定変更は古い人間確認を失効させ、設定欠落・不正は停止する。
現在の開発用準備候補CSV / TXTは、current SG Category / Brand、SLS ALLOW候補と武器画像検査条件が
成立した商品だけを含め、DEVELOPMENT_PREPARATION_PREVIEW / listing_ready=FALSEを明示する。
CSV / TXTの組立はPHと共通moduleを使用し、当該market・Category ID・Brand IDごとにまとめる。
PHの列順・文字コード・ASIN順・貼付用TXT形式を維持する。SGは開発用途の追加列を付け、
属性未取得を空欄 / NOT_FETCHED / 未取得、取得済み0件を0 / FETCHEDとして区別する。
属性件数の表示はSeller Centerへの入力完了を意味せず、取得自体で停止を解除しない。
この結果は画像AIの通常接続・実精度、商品全体の安全保証、SG実運用受入、通常の出品準備完了を意味しない。
別の起動入口app_sg_candidate.pyから、Catalog / Category AI / 画像の再生資料と既存のCandidate・
説明・未評価画像sidecarを明示取込して、確認・保存・準備候補出力まで操作できる。
再生資料はrequestへ結合し、不一致・欠落で実APIへfallbackしない。新しい隔離DBだけを初期化し、
通常DBを開かない。資料変更・削除・再初期化で人間確認と画面の確認チェックを破棄する。
画像素材は再生資料としてsession内に保持する。評価結果とDBには画像bytesを保存しない。
手順と合成確認資料は[SG開発版の確認](SG_LOCAL_REVIEW_GUIDE.md)を参照する。
PH形式の出品準備出力とSGベータ入口は採用候補として実装する（DEC-0126）。
通常環境への正式採用・起動先反映と実務受入は未完了である。
これらは追加の承認境界を含み、再生結果だけでSG機能統一完了とは判定しない。
隔離Brand部品は初期化済みDBと当該sessionで検証済みcatalogを明示注入する。
環境変数だけで通常画面に未検証のlive経路を開かない。


隔離実接続画面は`Start-SGCandidate.ps1 -LiveGrantPath <承認済みrun設定>`で明示起動する。
画面の再表示・環境初期化では通信せず、操作ごとに当該SG Bridgeの最新tokenを読む。
最大3商品・対象Category・ページ数・属性/Category取得数・費用を永続ledgerへ結合し、
再起動で消費を戻さない。現在catalog取得失敗はAI / Brand / 属性 / 準備候補を停止する。
商品ごとの準備確認と不足手順を共通化したが、正式CSV / TXT出口・SG operationは開かない。
実接続の新規実行は具体的な対象・上限についてOwner承認を得てから行う（DEC-0124）。
