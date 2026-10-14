# 候補のAmazon価格帯・平均レビュー評価フィルター設計

DEC-0138によりF1／F2はPH・SG共通Beta前MUST。P1〜P4を優先して実装し、F1/F2完成後にP5へ進む。
本書は設計正本。今回P1ではフィルターを実装せず、Keepa live、商品取得、費用発生を行わない。

## 固定する要件

- F1：Amazon.co.jp自身の販売価格（Keepa AMAZON）を日本円の下限／上限で絞る。両端を含み、片側のみ・指定なしも可能。
  Marketplace NEW、Buy Box、過去の最終有値価格へ無断代替しない。概算選別であり購入価格の保証ではない。
- F2：Amazon.co.jp商品の平均レビュー評価を最低評価で絞る。4.0以上／4.5以上／指定なしを共通UIで選ぶ。
  Sales Rankやレビュー件数とは別指標。未取得・不正値を条件一致と推定しない。
- 両条件を指定した場合はAND。一方が未取得なら一致CSVへ含めない。未取得理由と範囲外理由を別々に記録する。
  条件なしの項目の欠損は、他方の有効条件で一致した候補を除外しない。両方なしは既存候補集合・取得挙動を維持する。
- PH／SGで同一部品・操作・判定を使い、Amazon取得市場JPとShopee出品市場を分ける。将来MY／TH／TWでも同じ選別を再利用する。
- 条件一致は商品候補でありSafety通過ではない。既存Battery／SLS／Gate停止を変更しない。

## 最新mainの差分

監査基準は`aac8548657c1f028368a7e98c8ac44d426821c1b`。

| 対象 | 現行コード・tests | PH／SGの状態・不足 |
|---|---|---|
| Expansion | `modules/keepa_client.py:_build_product_finder_query`／`tests/test_keepa_client.py` | brand/category条件とSales Rank順。価格・平均評価の条件なし |
| Resolver | `modules/asin_resolver.py:verify_selected_rows`→`KeepaExpansionClient.verify_products_by_asin`→`_fetch_products_by_asin`／`tests/test_asin_resolver.py` | 選択ASINを共通Keepa clientで確認。Finder検索は通らないためFinderだけの変更では不足 |
| 取得 | `keepa_client.py:_get_source_product,_fetch_products_by_asin` | `history=False, rating=False, offers=None`、stats未指定。新条件の数値を保証していない |
| 保存 | `keepa_client.py:_product_to_cache_data`、`modules/cache.py:get_product,get_search` | 保存は必要項目を選別したJSON。価格／評価を保持していない。既存7日cacheから数値は復元不能 |
| CSV | `modules/prelisting_candidate_csv.py`／`tests/test_prelisting_candidate_csv.py` | PRELISTING_CANDIDATE_V1固定15列。Resolver既存7列とも新数値なし。契約を無断拡張しない |
| UI・費用 | `app.py`、`keepa_client.py:estimate_token_cost`、`keepa_bounded_transport.py`／`test_beta_application.py`,`test_keepa_client.py` | 共通4タブを利用可能。現推定はseed1＋11×ページ＋候補件数、評価の追加消費を含まない |

F1/F2とも両国で未実装。API仕様読取は確認済みだが、新パラメータの実応答、変換結果、実費は未検証。

## 公式仕様で確認した範囲（2026-10-14）

| 資料 | 確認した内容 | 設計への適用 |
|---|---|---|
| [Keepa Product Finder](https://keepa.com/api-docs/product-finder.html) | `current_AMAZON_gte/lte`、`current_RATING_gte`を構成可能。JP domain=5、金額単位は円。検索結果はASIN。基本料金は10 tokens／request＋結果100 ASINあたり1 token | 検索時の先行選別は可能。検索通過だけでは数値・欠損理由の保存やResolverへの適用にならない。FinderのSearch Insights `stats=1`は不要 |
| [Keepa Product Request](https://keepa.com/api-docs/product.html) | Productの`stats`は追加tokenなし。`rating=1`は既存評価を取得し最大+1 token／商品、評価更新は強制しない。基本1 token／商品。`history=0`で履歴を省略可能 | 条件指定時だけProduct `stats`と必要なら`rating=1`を使う最小案。offers／Buy Box／強制更新は追加しない |
| [Keepa Product Object](https://keepa.com/api-docs/product-object.html) | AMAZON index=0、RATING index=16、評価整数45は星4.5。価格-1はその時点のofferなし。`availabilityAmazon`や更新時刻を別に持つ | 円を100倍／100分の1しない。価格欠損とAmazon販売なしを分け、不明なavailabilityは不明のまま残す |
| [Keepa Statistics Object](https://keepa.com/api-docs/statistics-object.html) | `stats.current`は同じtype indexで現在値を持つ | Product statsから価格・評価を取り、配列欠落／sentinel／不正値を検証。SDKの数値変換後値とraw値を混同しない |

Product Objectの一般表はRATINGをoffers依存として記す一方、Product Requestの`rating`欄は例外を明記する。
したがって「評価には常にoffers必須」とも「無料」とも扱わず、`rating=1`による既存値取得を採用案とする。
現行Python SDKで`stats + rating + history=False`の返却・単位をfixture契約試験で固定し、別承認の少量liveで照合する。
取得できない評価はUNKNOWN。offers取得や再課金を自動追加しない。

## 最小実装案：取得後の共通選別

1. 任意の`price_min_jpy/price_max_jpy/rating_min`を共通の値オブジェクトにまとめる。
   不正範囲、負値、下限>上限、不正評価を送信前に拒否。両条件なしの既存query引数と出力を変えない。
2. Expansion候補／Resolver選択ASINの既存商品取得へ必要な観測値を載せる。
   保存するのはASIN、provider、JP domain、AMAZON円価格、availability、平均評価、各取得状態、取得／提供元更新時刻、schema版。
   seed値や他ASIN値で穴埋めしない。時刻不明も明示し、現在価格保証へ昇格しない。
3. 市場非依存のpure判定で各項目をMATCH／OUT_OF_RANGE／UNKNOWNに分ける。
   UNKNOWN理由はNOT_CAPTURED、NO_AMAZON_OFFER、STALE、INVALID等。Amazon販売なしは観測根拠がある時だけ付ける。
   価格が不明のまま評価だけ範囲外なら両理由を保持し、集計は「不一致あり→条件外、それ以外の指定項目不明→未確認」とする。
4. 一致候補だけ既存Candidate変換器へ渡す。Safety資料も同じASIN集合・Candidate bytesへ再結合し、旧packetを失効する。
   Resolverのsource_id重複行・既存確認値を保持し、ASIN一意化で出所を落とさない。
5. 正常取得値を再利用し、条件変更だけではAPIを呼ばず再判定する。手動の「不足情報を取得」は対象件数と追加予算を示して実行する。
   refresh失敗は古い一致結果を表示・搬送しない。候補の選別はSafety判断とは別の責務とする。

最小の対象は`keepa_client.py`、`cache.py`の互換JSON保存、共通選別module、Expansion／Resolver UIとCSV搬送の接点、対応tests。
Guardrail／Battery／SLSの判定codeやCandidate schemaを変更しない。DB全面移行・別検索エンジン・自動巡回は不要。
Canopy TESTをKeepa同等と推定しない。新条件指定時は未対応を明示して停止し、無指定の既存テスト経路を維持する。

## cacheとCSV／UI契約

既存7日TTLはそのまま基本商品cacheの再利用基準とし、追加観測にも取得時刻と鮮度を表示する最小案。
商品cacheに価格・評価のschema／取得状態がない場合はNOT_CAPTUREDとし、0円・星0・合格へ変換しない。
条件指定時の旧search cache hitは候補ASINの再利用に限り、新観測の充足を検査する。無断で全cacheを更新しない。
新観測だけを追加する場合も既存のSafety Fact・出所を消さず、成功した値だけを永続化する。
filter条件・判定版・観測fingerprintを結果identityへ含める。未取得と取得済み欠損を分け、後者を毎回自動再取得しない。

通常画面は両入口に同じ「候補の絞り込み」部品を置き、下限／上限（円）、最低評価、適用、解除を共通化する。
初期値は指定なし。一致／条件外／未確認の件数、AMAZON参考価格、平均評価、取得時刻を表示する。
「条件一致Candidate CSV」は15列を維持。数値・条件・理由・更新時刻は別の「絞り込み確認CSV」に出す。
後者はsource_id／ASIN／条件fingerprint／Candidate SHAで対応付け、Gate入力や出品CSVと明確に区別する。
条件なし出力は従来どおり。一致0件・取得失敗では以前の一致CSV・Gate引継ぎを使わせない。
未知商品の出品可否や価格の税務判定をこの確認CSVに付与しない。

## Finder段階との比較・費用

| 方式 | 利点 | 制約・推奨 |
|---|---|---|
| 取得後判定 | Expansion／Resolver・cacheの両方に同じロジック。範囲外と欠損を説明できる | 範囲外商品も詳細取得する。既存ページ内の候補を選別するため結果が少なくても追加ページを自動取得しない。最小初版に推奨 |
| Finder先行絞り込み＋取得後再検証 | 条件外の詳細取得を減らせる可能性 | Resolverには効かない。未返却商品の欠損／範囲外件数は不明。検索時と取得時の値変化、fallback検索、cache key全経路を整合する追加工数。Beta後の最適化に推奨 |

新規Product取得に価格statsを加えるだけなら追加tokenはない。評価指定時は基本取得に最大+1 token／商品を予算へ加える。
旧cacheに必要値がなく追加取得する場合は基本1も再び必要で、評価込み最大2 tokens／商品を見込む。
同じ値のローカル再判定は追加APIなし。cache全件refresh、offers、Buy Box、履歴全取得は最小案に含めない。
50候補で評価追加なら最大約50 tokens増、旧cache50件の評価補完なら最大約100 tokensという計画例になる。
これはAPI価格表からの計算であり実測ではない。request回数の上限だけではtoken上限にならない。
SGの既存送信予約を保ち、追加token見積とPH側の有限実行計画も確認する。Keepa契約金額の換算・購入は別承認。

## 受入条件と事業判断

| ID | offlineで固定する受入 |
|---|---|
| F01 | 価格の下限／上限／両側／無指定、境界1000・5000、下限>上限、円単位を検証 |
| F02 | 星4.0／4.5、raw40／45、Sales Rankとの分離、配列不足・sentinel・不正値を検証 |
| F03 | 未取得／Amazon販売なし／範囲外を区別、片側条件なし、AND、双方欠損で誤一致しない |
| F04 | 旧cache／新cache／期限切れ／取得済み欠損、条件変更で追加APIなし、明示補完と予算停止 |
| F05 | ExpansionとResolverの同じ観測が同じ結果、PH／SG共通UI、Canopy無指定動作を保護 |
| F06 | 15列・source_id・重複行・Safety sidecar結合を保持。一致0件と条件変更で旧搬送無効 |
| F07 | Finder未使用の初版でページ追加なし。将来pushdownする場合は全検索／fallbackの同条件、query hash、未返却理由不明を試験 |
| F08 | 取得時刻・概算表示・確認CSVを検証。別承認の少量liveでAMAZON円／評価／tokensConsumedを照合。offlineだけで実値取得済みとしない |

| 候補 | 重要度・未実装時の実務影響 | 工数目安 | 推奨区分／Owner判断 |
|---|---|---|---|
| F1 価格帯 | 仕入れ価格帯の一次選別を省力化。なしでも手動選別可能だが候補が多いほど負担 | 共通取得・保存・UI・CSV基盤込み1.5〜2.5人日 | Beta前MUST（DEC-0138）。P1〜P4の後、P5の前に完成 |
| F2 平均評価 | 低評価候補の一次選別。なしでも商品確認時に手動確認可能、対象数次第で負担増 | F1の基盤共用で追加0.5〜1.5人日 | Beta前MUST（DEC-0138）。F1と同じ順序。常時最新保証は含めない |
| Finder最適化 | 詳細取得量を抑えられる可能性。初版の正確な選別には不可欠ではない | 追加1〜2人日 | Beta後。実測した候補件数・消費に必要性が出た場合 |

F1/F2合計2〜4人日は概算であり調査済み範囲の実装・offline回帰目安。実API受入・待ち時間を含まない。
OwnerはF1/F2のMUST採用を確定済み。候補数・鮮度・費用は実装と別承認の実商品受入で確認する。
F1/F2が未完成のままP5受入や実務Beta完成としない。

## MY税務確認との分離

Amazon円価格は仕入れ参考の選別値で、MYの課税判定額ではない。
MY稼働前の国別工程で、MY想定販売価格、貨物価格、送料・保険等、取引条件に基づく税務確認の要否と担当を整理する。
税率・閾値・免税可否を本書では確定しない。実際の確認時に公式資料と必要な専門確認を用いる。
今回、関税計算機能・MY runtime・税務判定ロジックは実装せず、Amazonフィルターへ混在させない。
