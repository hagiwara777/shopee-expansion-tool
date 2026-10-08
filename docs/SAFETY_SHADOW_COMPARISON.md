# Shadow V3の読取専用比較

通常の出品前保安ゲートで判定した後、「Shadow V3との比較（任意）」を開き、
同じ商品の保存済みFact JSONを選ぶ。分類候補・一致欄・抜粋・出所・versionと、
現在のSafety／Gate結果を並べる。比較は既存Safety判定・本体確認記録・出力CSVを変更しない。
BODY_CANDIDATEだけでBLOCKせず、ACCESSORY_CANDIDATEだけで停止を解除しない。
SG本体・実同梱の確認と除外はDEC-0129／DEC-0130の既存処理を使う。

## 再利用とmainとの差分

既存local Shadow成果の`SAFETY_SHADOW_V3`、`KNIFE_JP_SHADOW_V1`、
`CONTACT_LENS_JP_SHADOW_V2`、純粋Evaluator、保存Fact adapter、独立比較CLI、
合成fixtureを再利用する。Evaluator／CLI／fixtureは元成果と同じbytesを保持する。
旧テストの「通常経路から一切importしない」という境界だけを、比較module以外の
製品経路がShadowをimportしない境界へ変更する。分類期待値を変更しない。
旧成果の未採用管理文書はコピーせず、正式DEC-0129／0130を基準とする。

mainには分類Core・商品自身のstructuredカテゴリ搬送・Shadow接続がない。
今回追加するのは独立比較module／UI／検証と、Gate判定後の表示呼出しだけ。
Guardrail辞書・matcher、Gate判定、SG本体確認、Candidate15列、既存Gate CSV、
Keepa client／cache、DB、Category Mapper、State、認証・API枠・起動先は変更しない。

既存のV2 report JSONはASIN単位の独立比較であり、Candidate全項目や現在の
商品文章との対応を立証できない。旧report単独を通常フローの確定Factとして取り込まない。
その元の保存Factを現在の入力へ照合し、一致商品のみ既存V3をoffline再生する。
保存済み実商品レポートの再評価・大規模再分類・追加API取得はこの接続検証に含めない。

## 入力と結合

JSONは既存CLIと同じ`{"products": [...]}`形式。形式を明示選択する。

- `keepa_response`: 保存したProduct応答のASIN、title、brand、domainId、categoryTree、
  categories、承認済み文章欄と、保存時の`fetched_at`を使う。取得時刻はenvelopeにも指定できる。
- `cache_snapshot`: 既存adapterの`category_tree`、Product Text payload markerを使う。
  `category_origin`を必須とし、未指定時にOWN_PRODUCTを推定しない。
- ファイル名・ASINだけの一致、旧reportのtitleだけの一致から比較可能にしない。
  Candidateのtitle／brand／取得時刻は非空で完全一致、domainId=5を必須にする。
  Product Text Safety sidecarのCandidate SHA・ASIN集合・schemaと、保存Factの
  全文章欄・provider・capture status・取得時刻を照合する。
- OWN_PRODUCTはstructured category pathとCandidate categoryを照合する。
  SEED_FALLBACK／MISSINGはカテゴリIDとpathを分類に使用せず、商品自身の
  title＋文章だけの比較であることを表示する。seed由来ブランドの代用も認めない。
- Candidate全15項目と全行・CSV bytes・現在の市場・文章Fact・Gate全結果・
  Evaluator／分類規則をcontext digestへ結合する。表示用入力widgetもこのcontextで区別する。
  比較結果をsession／DBへ保存せず、毎rerunで現在入力から再計算する。
- 欠損・重複・不一致・旧cacheの出所不明・不正JSONは比較不能。比較不能で追加REVIEWを作らず、
  有効な既存Gate結果と出力を保持する。対象familyのsignalなしも安全保証ではない。

hashと同一資料照合は取り違え検出であり、API由来の真正性、資料の最新性、
商品実体や人間確認の電子署名を証明しない。JSONには秘密値を含めない。

## 具体的に残る接続制約

通常Candidateのcategory文字列だけからは自分のカテゴリかseed fallbackかを判定できない。
現行Keepa探索はブランド／カテゴリにseed fallbackを使う場合があり、Candidateの
探索実行時刻とcache Fact取得時刻も異なる場合がある。現在の情報だけで一致を証明できない
商品は比較不能となる。これを通すためのKeepa保存・搬送改善は別scopeで判断する。
未採用Keepa成果を自動コピー・統合しない。旧cacheに欠けるdomain／文章／出所を補完しない。

保存Factの選択は手動であり、通常フロー全商品への自動取得や自動比較ではない。
分類は2familyの小さいheuristicで、否定・引用・複雑なセット・未登録語句を網羅しない。
便宜標本の既存結果や合成テストを一般精度・実商品受入・作業時間削減の実測値にしない。

## 実務上の効果と受入境界

一致した商品では、別のShadowレポートからASINを探し、どの文章・カテゴリが
本体／付属品候補を支持したかを探し直す作業を減らせる。既存停止理由との比較と
確認箇所の絞込みを支援する。本体・実同梱の人間確認、国別販売条件、既存Safety、
Category／Brand／SLS確認を省略する機能ではない。

offline検証は実Gateと実CSV生成を用い、分類前後の全結果／bytes不変、
SG確認済み本体EXCLUDE、BLOCK優先、Battery／既存REVIEW維持、seed非採用、
Fact不一致、全15項目変更、市場切替、通常画面のuploadと比較障害を確認する。
正式採用の判断はmandatory technical gates・read-only review・現在対象の
Owner Acceptanceを経る。local検証だけでformal main統合・deploy・実商品受入へ進まない。
追加の独立工程へ移るまでは同じ成果物の修正・review・PR・正本化を同じタスクで続ける。

rollbackは比較表示と追加moduleの通常revert。既存本体確認記録、DB、API消費記録を削除しない。
