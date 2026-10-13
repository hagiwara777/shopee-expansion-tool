# SG Initial Beta offline fixture

すべて人工商品です。実商品4ASINの保存資料とは別です。catalogの階層名は既存SLS照合契約を使いますが、
catalog／Brand一覧のcurrentフラグはoffline試験の仮定であり、現行公式API取得を意味しません。

- B000000001: OWN_PRODUCT JP・有線audio・承認aliasでCategory／Brand AUTO_RULE。
- B000000002: Category AUTO_RULE、模擬Brand未登録の確認待ち。No Brand fallbackなし。
- B000000003: Bluetooth反例。Category自動確定なし。
- B000000004: category treeはSEED_FALLBACK。Category自動確定なし。

利用手順と承認境界は`docs/SG_INITIAL_BETA_V1.md`を参照。
新しい隔離作業DBだけで再生し、旧DB／ledger／claim／8503へ使用しない。
