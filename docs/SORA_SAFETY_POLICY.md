# Sora共通保安ルール（DEC-0167）

## 現行の対象と操作

ASINの出所にかかわらず、取得済みの同じ商品資料でSG／PHを判定する。
共通方針、選択国の規則、個別ASIN／既存Community NGを合成し、BLOCK > REVIEW > SAFEを維持する。
Gateではそれぞれ停止（EXCLUDE）、要確認（REVIEW）、通過（ELIGIBLE）へ対応する。
通過は全商品の安全・販売許可・発送適合の保証ではない。

判定ルールの変更と入口の変更は別工程である。この版の通常画面は従来のResolver／ASIN確認を使う。
直接入力を主役にする画面、FROMAX CSV取込、500件上限、途中取得の残件再開、既出品CSVのエラー表示は
次の独立工程とし、この版には含めない。現在の上限は100 ASINである。

## 設定と照合欄

| 資産 | 役割 |
|---|---|
| `guardrails/policy/rules.json` | 共通・市場別の商品語、対象欄、段階、条件、Decision参照 |
| `guardrails/deterministic_block_rules_v2.csv` | GABAの既存6表記とhempをCOMMON_BLOCKで評価 |
| `guardrails/risk_keywords_sg.csv` / `risk_keywords_ph.csv` | 共通へ移していない市場固有の既存疑義規則 |
| `guardrails/brand_monitoring/` | 公式IPR、国別Counterfeit、自社共通禁止10ブランドと承認済み別表記 |
| `guardrails/community_ng/` | 元資料の市場範囲を保持した個別ASIN・ブランドNG |
| `guardrails/sls_shared/battery_review_rules.csv` | 既存16語の電池疑義。確定BLOCKを解除しない |

商品名は`product_title`、説明文は`description / features / shortDescription / safetyWarning / itemHighlights`、
成分欄は`ingredients / activeIngredients / specialIngredients`を指す。説明文を成分Factへ転記しない。
Candidate固定15列、成分・文章のASIN集合／内容対応の検査、電池・家電の既存判定は維持する。
設定欠損・不正を空リストへ置換せず、判定を停止する。

| 群 | 対象・扱い |
|---|---|
| 薬物・龍角散 | 商品名・説明・成分で共通BLOCK。hemp-free／hempseedも従来どおり止める |
| 一般語 | 偽物・fake・replica・医薬品・medicine・処方箋・prescription・タバコ・アルコール・武器等は商品名BLOCK、説明REVIEW |
| 成分NG | ナイアシンアミド、レチノール等の新規群は商品名・説明のみ。成分欄だけでは止めない |
| 既存成分停止 | ジフェンヒドラミンはPHも商品名・説明・成分までBLOCK。GABAは既存の成分・商品名照合を共通化 |
| 医療・医薬部外品 | 明確な区分表示、薬用、有効成分等の肯定表示はBLOCK。直接の否定文を除く |
| 輸送 | 明確な燃料・火薬・着火品・電池・SLS NOの商品群をBLOCK。エアゾール、LPG／DME等の疑義はREVIEW |
| 整髪 | ヘアスタイリング等だけなら停止理由を作らず、スプレー／エアゾールとの組合せをREVIEW |
| サンプル | サンプル・試供品・小分けは全市場REVIEW。メーカーのつめかえ用だけでは止めない |
| マスク | 口鼻を覆う衛生・防塵・医療用はBLOCK。美容用ヘアマスク・シートマスク・フェイスパックはこの規則の対象外 |
| 装飾品の武器 | 模型の剣・銃も、フィギュア・キーホルダー・ペンダントへの付属／形状が明示されればBLOCK。関連不明ならREVIEW |
| 条件不明 | レーザー出力や認証等は、必要条件が確認できればBLOCK、対象疑義はあるが不明ならREVIEW |

「アルコールフリー」「ノンアルコール」「alcohol-free」「fake lashes」「つけまつげ」は、
該当する出現箇所を一般語照合から除外し、REVIEWにも数えない。同じ文章の別の肯定表示や別ルールは維持する。
AHA・ビタミンA等の短い英数字は境界を確認する。ハイライター、マスカラのトップコート、
食品由来成分のシャンプーなどを、燃料・ネイル・食品本体と推測しない。

## ブランド

主要ブランド名の完全一致、全半角・大小・アクセント・空白／中点／長音の既存正規化、括弧外優先を維持する。
Owner承認済みの別表記は既存36件に41件を加えた77件。ミルボン→Milbon、ポケモン→PokemonはSGにだけ効く。
別表記の追加は参照先の国別範囲を広げない。インテグレート、KATE、エリクシールを親会社名から停止しない。

Louis Vuitton、Gucci、Chanel、Hermes、Prada、Rolex、Cartier、Tiffany、Burberry、Diorを
自社共通禁止として扱う。Tiffany & Co、Christian Diorも同じ自社方針の表記として保持する。
公式IPR／Counterfeitを書き換えて自社方針を公式禁止に見せない。
承認済みのプラダ、ロレックス、ティファニーは共通自社方針を参照する。

## SLS表とAmazonカテゴリの境界

Owner提供2026-09-17版CSVはsource-lock masterのSHA-256
`35f7bab5da9c5dd3d9b62456035916a9fce62a153d6bcfcaa82c221dc117dbc9`と一致する。
SGのNO 171件、PHのNO 174件を、元の市場範囲付きの具体的な禁止商品群の根拠にする。
既存SLS正規化資産・manifest・source-lockは変更しない。

商品語とAmazonカテゴリの具体的ノード／完全パスの一致は、商品群を識別する保安の手がかりとして使う。
「ヘアケア・カラー・スタイリング」全体をヘアカラーと扱わない。`Others`単独、広い`Health`だけでは止めない。
Health > Others、Health > Personal Care > Others等の完全な広義パスでも、確定BLOCKを出さずREVIEWとする。
該当語・分類がないことは、対象外やSLS発送可の証明ではない。

AmazonカテゴリからShopeeカテゴリIDを生成・保存・自動割当せず、SLS ALLOWも生成しない。
元表のCategory ID、YES、数量条件による自動通過は行わない。既存Mapperの正式SLS評価器は再開しない。
SGの食品63カテゴリの5kg未満、PH17カテゴリの1〜2個は注文数量判定と切り離し、表示は後続の入口工程で扱う。

## 検証とOwnerのlive比較

offlineテストは、両市場の明示語・対象欄・条件、共通評価へのMY等の模擬入力、国別範囲、
成分例外、否定文・別意味、全NOカテゴリの保安信号、既存電池・家電・資料搬送を確認する。
MY／TH／TWの通常画面・API・運用は開始しない。TH／TWの食品停止設定はofflineで確認する。

提供ZIPは旧判定と一部の商品名を持つが、全商品の説明文・成分・カテゴリFactは含まない。
ルベル100件の旧SGは98通過／2要確認／0停止、PHはSG通過分98件だけであり、同一母集団ではない。
ヘアスタイリング単独解除だけなら要確認2→1の見込みだが、全改修後の件数を実測として報告しない。
SG調査62行から旧確認48行・Gate46商品へ至った旧実行と、Ownerの新しいlive実行の件数を区別する。

Ownerはルベル100件とSG調査62件をliveで再判定する。コード版・入力件数・国・取得回数と4出力を対応させ、
通過→停止、通過→要確認、要確認→通過／停止をASINごとに比較する。
特にB00MGEF832（ヘアスタイリング単独）、B0744HJHWV（LPG／DME）、
B0DW8VGF6R（ナイアシンアミド）、B01DXC965G（ブランド欄ミルボン）と、
マスク・整髪料・ネイル等の過剰停止を確認する。取得Factが変わった差はルール差と区別する。
SG一般医薬品語の旧BLOCK→新REVIEWは合成例で確認し、実例はlive資料で同じ事実が確認できた場合だけ記載する。

新ルールもFROMAXの部分一致へ無条件に変換しない。条件・否定文・分類・ブランド／ASINの停止は注意CSVへ分ける。
実API・実商品処理・稼働版更新・実出品はofflineテストと別。formal mergeは現行mandatory gatesとOwner最終承認を要する。
