# B00HVLUR18限定JP Fact証拠runner

`python -m modules.keepa_jp_fact_runner`はB00HVLUR18／JP（domainId=5）の
Product応答を1回だけ取得する専用入口。importと`--help`はoffline。
通常アプリ、Keepa cache、SG作業DB、Policy／Grant／ledger／claimには接続しない。
実APIは実装・mock検証の承認と別のOwner明示承認を必要とする。

## 送信・保存契約

- Keepa SDK 1.5.0のみ。`check_key=False`で初期化し、共通bounded transportを再利用する。
  `_product_query([B00HVLUR18], domain=JP, raw=True, history=False, wait=False)`を使い、
  offers／stock／buybox／rating／videos／aplus／stats／updateは要求しない。
  raw=TrueはSDKがHTTP応答をそのまま返すprivate契約で、実SDK＋mockで固定する。
- endpoint・全payloadを送信前に照合し、Product以外・別ASIN／市場・暗黙token照会を拒否する。
  Sessionのretry=0、redirect追随なし、timeout=10秒、429待機なし。
  上限はHTTP送信試行1回であり、費用・消費token数の上限保証ではない。
- `%LOCALAPPDATA%/ShopeeKeepaJPFact/B00HVLUR18/`に独立した永続予約を排他的に作成する。
  `attempt.json`をflush／fsync／読戻し確認してから送信する。予約状態は結果不明として扱う。
  同時起動・再起動・別証拠保存先でも、このdirectoryがあれば停止する。
  部分保存・記録欠落でもdirectoryを残し、runnerは削除・reset・再送しない。
- 新規のGit外専用directoryだけを証拠保存先に指定できる。既存directory、Git内、
  link／junction、予約先と包含関係のある保存先は拒否する。既存API承認枠やDBは指定しない。
  保存先の親directoryは承認済みの独立領域を事前に用意する。
- `raw-response.json`はSDK加工前のHTTP応答bodyの正確なbytes（非200・不正JSONも含む）。
  `raw-response.sha256`、`manifest.json`、正常validation後だけ`facts.json`を新規排他的に保存する。
  timeoutでbodyがない場合はrawを生成しない。manifest／予約outcomeには結果不明を残す。
  API keyを含む応答は保存せず停止する。request URL・credential・raw exceptionは記録しない。
- JSONの重複key／NaN／不正UTF-8、error envelope、商品数が1以外、ASIN／domainId不一致、
  categoryTreeの型・正整数ID・名前・重複、rootCategoryとの矛盾、取得項目の型を拒否する。
  categoryTree欠落・null・空配列は不足Factとして保持し、seedやrootからpathを補完しない。
- Factには項目ごとの原値・PRESENT／MISSING／UNKNOWN・authority・ASIN・JP／domainId・
  UTC応答取得時刻・raw SHA・JSON pointerを保存する。category pathとleaf IDは有効な
  商品自身のcategoryTreeだけから導出し、その参照と変換を明示する。
  説明・成分・画像参照も同じ応答から保持し、画像URLへの追加アクセスはしない。

SUCCESSは取得・厳密検証・証拠保存の成立だけを意味する。現在のAmazonページ、購入可能性、
SG Category rule適用、Shopee Brand ID、Safety、出品可否を証明しない。
MISSING／UNKNOWNはOWN_PRODUCTへ昇格しない。応答取得時刻はprovider内部更新時刻ではない。

## 別承認後の実行

Ownerは対象B00HVLUR18／JP、Keepa Product HTTP最大1回、既存契約内のtoken消費、
新規Git外証拠保存先と独立予約先の設置を明示承認する。認証値を指示・logへ貼らず、
承認済みprocess内の既存`KEEPA_API_KEY`を利用する。runnerは`.env`の自動読込を行わない。
承認参照文字列と`--execute`は承認の搬送であり、Owner承認そのものの証明ではない。

```powershell
python -m modules.keepa_jp_fact_runner --execute `
  --authorization-ref '<Ownerの実API1回承認参照>' `
  --evidence-dir '<承認済みGit外親directory内の未作成専用directory>'
```

予約directoryの有無を実行前にread-only確認する。存在したら新しい保存先を選んでも再実行しない。
HTTP失敗・timeout・raw不整合・保存失敗・CLI非正常終了後は、既存記録を保持しOwnerへ報告する。
追加送信には独立した再承認と設計判断を必要とし、このrunnerに解除optionは設けない。
ローカル記録の悪意ある削除・環境変数による保存root変更・機器故障後のdisk巻戻しへの
耐改竄保証は含めない。通常の同一端末・同一LOCALAPPDATAでの自動再送を防止する。

## Offline検証と保護

`python -m pytest tests/test_keepa_jp_fact_runner.py -q`で合成応答と実SDKを使用し、live HTTPを禁止する。
PH／SG保護gateと共通Keepa／通常継続modeの回帰も実行する。実API・有料API、8503反映、
実DB変更・移行、実出品、rule／Brand実運用適用、formal main mergeは別承認。
rollbackは専用入口の利用停止と通常revert。予約・証拠・既存DB・API枠は削除しない。
