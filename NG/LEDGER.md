# NG台帳（自動生成・編集しない）

Soraが「停止」「要確認」を出す根拠の一覧です。`python scripts/build_ng_ledger.py` が
`guardrails/` のファイルとコード内のルールから作ります。**このファイルを直接直しても判定は変わりません。**
直すときは「元ファイル」を直し、もう一度このスクリプトを実行します。全行は `NG/ledger.csv` にあります。
保安ルールの `scope` は `item`（物そのもの）／`content`（中身・表示）です。他の元資産にはこの区分を付けず空欄にします。

## 全体（グループ別の件数）

| グループ | 停止 | 要確認 | その他 | 元ファイル |
|---|---:|---:|---:|---|
| 保安ルール | 134 | 38 | 0 | `guardrails/policy/rules.json` |
| コード内のルール | 5 | 3 | 0 | `modules/battery_presence.py`<br>`modules/guardrails.py`<br>`modules/home_appliances_classifier.py`<br>`modules/prelisting_sg_body_safety.py`<br>ほか4件 |
| ブランド（IPR） | 138 | 0 | 0 | `guardrails/brand_monitoring/ipr.json` |
| ブランド（Counterfeit） | 1525 | 0 | 0 | `guardrails/brand_monitoring/counterfeit_my.json`<br>`guardrails/brand_monitoring/counterfeit_ph.json`<br>`guardrails/brand_monitoring/counterfeit_sg.json`<br>`guardrails/brand_monitoring/counterfeit_th.json`<br>ほか1件 |
| ブランド（自社方針） | 12 | 0 | 0 | `guardrails/brand_monitoring/company.json` |
| ブランド（商品名の確認） | 0 | 47 | 0 | `guardrails/brand_monitoring/title_review.json` |
| ブランド（別表記） | 0 | 0 | 77 | `guardrails/brand_monitoring/aliases.json` |
| 国別の禁止ブランド | 13 | 0 | 0 | `guardrails/prohibited_brands_sg.csv` |
| 国別の危険語 | 0 | 104 | 0 | `guardrails/risk_keywords_ph.csv`<br>`guardrails/risk_keywords_sg.csv` |
| 電池の確認 | 0 | 16 | 0 | `guardrails/sls_shared/battery_review_rules.csv` |
| 成分・事実による停止 | 7 | 0 | 0 | `guardrails/deterministic_block_rules_v2.csv` |
| 仲間内報告（ASIN） | 46 | 0 | 0 | `guardrails/community_ng/marketplace_asin_blocks.csv` |
| 仲間内報告（ブランド） | 54 | 0 | 0 | `guardrails/community_ng/marketplace_brand_blocks.csv` |
| SLS発送可否（カテゴリ） | 1167 | 171 | 0 | `guardrails/sls_market_categories/markets` |

## 国別の件数（停止／要確認）

| 国 | 停止 | 要確認 |
|---|---:|---:|
| 全ての国 | 222 | 74 |
| MY | 671 | 27 |
| PH | 469 | 28 |
| SG | 668 | 139 |
| TH | 352 | 128 |
| TW | 746 | 49 |
| VN | 2 | 0 |

## 保安ルール

| ID | 国 | 動作 | scope | 対象 | 根拠 | メモ |
|---|---|---|---|---|---|---|
| COMMON-DRUG | ALL | 停止 | content | CBD、大麻、マリファナ、ヘンプ、Hemp、ガンビル、Gambir、Sativa ほか5語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-RYUKAKUSAN | ALL | 停止 | content | 龍角散 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-GENERAL-TITLE-other | ALL | 停止 | item | 偽物、fake、replica、コピー品、アダルト、adult only、R18、18禁 ほか7語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-GENERAL-TEXT-other | ALL | 要確認 | content | 偽物、fake、replica、コピー品、アダルト、adult only、R18、18禁 ほか4語 | 自分の方針 | DEC-0167; Ownerの出品方針による要確認 |
| COMMON-GENERAL-TITLE-medical_or_therapeutic | ALL | 停止 | item | 医薬品、medicine、処方箋、prescription | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-GENERAL-TEXT-medical_or_therapeutic | ALL | 要確認 | content | 医薬品、medicine、処方箋、prescription | 自分の方針 | DEC-0167; Ownerの出品方針による要確認 |
| COMMON-GENERAL-TITLE-tobacco_or_vape | ALL | 停止 | item | タバコ、cigarette | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-GENERAL-TEXT-tobacco_or_vape | ALL | 要確認 | content | タバコ、cigarette | 自分の方針 | DEC-0167; Ownerの出品方針による要確認 |
| COMMON-GENERAL-TITLE-alcohol | ALL | 停止 | item | アルコール、alcohol | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-GENERAL-TEXT-alcohol | ALL | 要確認 | content | アルコール、alcohol | 自分の方針 | DEC-0167; Ownerの出品方針による要確認 |
| COMMON-GENERAL-TITLE-weapon | ALL | 停止 | item | 武器、weapon、弾薬 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-GENERAL-TEXT-weapon | ALL | 要確認 | content | 武器、weapon、弾薬 | 自分の方針 | DEC-0167; Ownerの出品方針による要確認 |
| COMMON-COSMETIC-INGREDIENT | ALL | 停止 | content | アゼライン酸、ハイドロキノン、ヒドロキノン、レチノール、ナイアシンアミド、アルブチン、トランサミン、トラネキサム酸 ほか10語 | 自分の方針 | DEC-0167 / DEC-0168 / DEC-0169; 商品名・通常説明は停止。見出しで確認した成分一覧の区間だけはREVIEWとし、区間外のBLOCKを優先。 |
| COMMON-DIPHENHYDRAMINE | ALL | 停止 | content | ジフェンヒドラミン、塩酸ジフェンヒドラミン、diphenhydramine、diphenhydramine hydrochloride | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-GROWTH | ALL | 停止 | content | 育毛、発毛、発毛促進、hair growth、hair loss | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-CONDOM | ALL | 停止 | content | コンドーム、condom、condoms | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| PH-SG-COMMUNITY-EISAI-ALIAS | PH/SG | 停止 | item | Eisai | 自分の方針 | DEC-0179; 既存Community NG「エーザイ」のOwner指定英字別名。公式IPRへの追加ではない。 |
| COMMON-SUPPLEMENT | ALL | 停止 | content | サプリ、サプリメント、健康食品、dietary supplement、food supplement | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-SUPPLEMENT-CATEGORY | ALL | 停止 | item | サプリ、サプリメント、健康食品、健康食品・サプリメント、ダイエットサプリ、ダイエットサプリメント、フィッシュオイル、機能性表示食品 ほか9語 | 自分の方針 | DEC-0179; Ownerの出品方針に基づく共通停止。 |
| COMMON-POWERBANK | ALL | 停止 | content | モバイルバッテリー、power bank、powerbank | Shopee公式 | DEC-0167; Ownerの出品方針による停止。旧PH-D073/PH-D074/PH-D075の停止を共通化。。SLS輸送確認。 |
| COMMON-BATTERY-SINGLE | ALL | 停止 | content | リチウム電池単体、リチウムイオン電池単体、交換用電池、ボタン電池、コイン電池、乾電池、ノートPC用バッテリー、カメラ用バッテリー ほか12語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止。SLS輸送確認。 |
| COMMON-LITHIUM-SIGNAL | ALL | 要確認 | content | リチウム電池、リチウムイオン電池、lithium battery、lithium ion battery | 自分の方針 | DEC-0167; Ownerの出品方針による要確認。SLS輸送確認。 |
| COMMON-WEAPON | ALL | 停止 | content | スタンガン、電気スタンナー、催涙スプレー、stun gun、stun guns、pepper spray、firearm、firearms ほか13語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-WEAPON-DECORATION | ALL | 停止 | content | 剣、刀、銃、武器、ナイフ、sword、gun、weapon ほか1語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| PH-WEAPON-DECORATION | PH | 停止 | content | 剣、刀、銃、武器、ナイフ、sword、gun、weapon ほか1語 | Shopee公式 | DEC-0181; PH公式の輸入禁制品（武器付きのキーチェーン・ペンダント・フィギュア等）をBLOCK。SGは共通ルールの扱いを維持。 |
| COMMON-FIRE-FUEL | ALL | 停止 | content | 花火、爆竹、火薬、ライター、マッチ、着火剤、燃料、オイルライター用オイル ほか7語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止。SLS輸送確認。 |
| COMMON-DIGITAL | ALL | 停止 | item | デジタルコード、オンラインコード、ダウンロード版、ギフト券、プリペイドカード、e-voucher、電子ギフト券、商品券 ほか17語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-AEROSOL | ALL | 要確認 | content | スプレー缶、エアゾール、エアロゾル、LPG、DME、高圧ガス、窒素ガス、火気と高温に注意 ほか16語 | 自分の方針 | DEC-0164/0167; SLS輸送確認：エアゾール・高圧ガス。正式な発送適合の保証ではない。 |
| COMMON-STYLING-SPRAY | ALL | 要確認 | content | ヘアスタイリング、スタイリング仕上げ、ヘアセット剤、仕上げ剤、まとめ髪スタイリング | 自分の方針 | DEC-0167; Ownerの出品方針による要確認。SLS輸送確認。 |
| COMMON-DRY-SPRAY | ALL | 要確認 | content | ドライシャンプー、ヘアスプレー、電動本体、電動ハンドル、電動カミソリ | 自分の方針 | DEC-0167; Ownerの出品方針による要確認。SLS輸送確認。 |
| COMMON-TRANSPORT-FLAMMABLE | ALL | 要確認 | content | 高濃度アルコール、消毒用エタノール、引火性、flammable liquid | 自分の方針 | DEC-0167; Ownerの出品方針による要確認。SLS輸送確認。 |
| COMMON-TRANSPORT-FLAMMABLE-LIQUID | ALL | 停止 | content | 火気注意、火気厳禁、引火性、flammable liquid、引火性液体、引火性の液体、flammable liquids | 自分の方針 | DEC-0179; Ownerの出品方針に基づく共通停止。 |
| COMMON-TRANSPORT-OXIDIZER | ALL | 要確認 | item | 漂白剤、オキシ、キッチンハイター | 自分の方針 | DEC-0167 / DEC-0170; SLS輸送確認。注意書きの漂白剤の明確な使用禁止だけを除外し、別の肯定表示は維持。; DEC-0188: 商品名・カテゴリで物の種類を照合 |
| COMMON-TRANSPORT-OXIDIZER-INGREDIENT | ALL | 要確認 | content | 過酸化水素、ヘアカラーの2剤、hydrogen peroxide | 自分の方針 | DEC-0167 / DEC-0170; SLS輸送確認。注意書きの漂白剤の明確な使用禁止だけを除外し、別の肯定表示は維持。; DEC-0188: 中身・保存表示を従来の対象欄で照合 |
| COMMON-TRANSPORT-CORROSIVE | ALL | 要確認 | content | 塩酸、強アルカリ、腐食性、hydrochloric acid | 自分の方針 | DEC-0167; Ownerの出品方針による要確認。SLS輸送確認。 |
| COMMON-TRANSPORT-TOXIC | ALL | 要確認 | content | 毒物、劇物 | 自分の方針 | DEC-0167; Ownerの出品方針による要確認。SLS輸送確認。 |
| COMMON-TRANSPORT-BIO | ALL | 要確認 | content | 放射性、病原体、生体、radioactive、pathogen | 自分の方針 | DEC-0167; Ownerの出品方針による要確認。SLS輸送確認。 |
| COMMON-TRANSPORT-CHARCOAL | ALL | 要確認 | content | 活性炭、activated carbon、activated charcoal | 自分の方針 | DEC-0167; Ownerの出品方針による要確認。SLS輸送確認。 |
| COMMON-TRANSPORT-VALUABLES | ALL | 要確認 | content | 貴金属、宝石、現金、切手、カード類、precious metal、gemstone、cash ほか1語 | 自分の方針 | DEC-0167; Ownerの出品方針による要確認。SLS輸送確認。 |
| COMMON-COLD-FOOD | ALL | 要確認 | item | 納豆、キムチ、チルド、冷蔵食品、冷蔵品、生麺、生パスタ | 自分の方針 | DEC-0167; Ownerの出品方針による要確認; DEC-0188: 商品名・カテゴリで物の種類を照合 |
| COMMON-COLD-FOOD-LABEL | ALL | 要確認 | content | 要冷蔵、冷蔵保存、腐敗しやすい、変質しやすい、perishable、keep refrigerated、クール便 | 自分の方針 | DEC-0167; Ownerの出品方針による要確認; DEC-0188: 中身・保存表示を従来の対象欄で照合 |
| COMMON-SAMPLE | ALL | 要確認 | item | サンプル、試供品、小分け、非売品サンプル、量り売り、sample、samples | 自分の方針 | DEC-0167; Ownerの出品方針による要確認 |
| COMMON-MASK | ALL | 停止 | item | マスク、不織布マスク、立体マスク、N95、respirator、surgical mask、face mask | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-PETFOOD | ALL | 停止 | item | ペットフード、犬用フード、猫用フード、pet food、dog food、cat food | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-FORMULA | ALL | 停止 | item | 粉ミルク、乳児用調製粉乳、infant formula、ステージ1粉乳、ステージ2粉乳、3歳以下の乳製品 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-INFANT-DAIRY-UNKNOWN | ALL | 要確認 | item | 乳幼児用乳製品、幼児用乳製品、toddler milk | 自分の方針 | DEC-0167; Ownerの出品方針による要確認 |
| COMMON-ANIMAL | ALL | 停止 | content | 野生動物製品、動物製品、象牙、剥製、wildlife product、animal product、べっ甲、鼈甲 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-LOTTERY | ALL | 停止 | content | 宝くじ、スロットマシン、lottery ticket、slot machine、パチスロ実機、スロット実機、パチンコ実機 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-FINANCE | ALL | 停止 | content | 株券、株式、有価証券、クレジットカード、デビットカード、通貨、紙幣、記念硬貨 ほか4語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-OFFICIAL | ALL | 停止 | content | 政府のバッジ、警察バッジ、軍のバッジ、勲章、警察制服、軍服、政府文書、身分証明書 ほか11語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-MERCURY | ALL | 停止 | content | 水銀体温計、水銀を含む、mercury thermometer | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-MERCURY-UNKNOWN | ALL | 要確認 | content | 水銀、mercury | 自分の方針 | DEC-0167; Ownerの出品方針による要確認。SLS輸送確認。 |
| COMMON-ALCOHOL-DRINK | ALL | 停止 | content | アルコール飲料、alcoholic beverage、alcoholic beverages、酒類、ビール、ワイン、日本酒、梅酒 ほか15語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-TOBACCO | ALL | 停止 | content | 電子タバコ、電子たばこ、タバコ用アクセサリー、電子タバコ用アクセサリー、tobacco、vape、electronic cigarette、electronic cigarettes ほか16語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-ADULT-TOY | ALL | 停止 | content | 大人のおもちゃ、アダルトグッズ、adult toy、sex toy、自慰用、アダルト用品、アダルト商品、性玩具 ほか2語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-ADULT-CATEGORY | ALL | 停止 | item | アダルト、アダルト商品、アダルト用品、アダルトグッズ、Adult Products、Adult Store | 自分の方針 | DEC-0179; Ownerの出品方針に基づく共通停止。 |
| COMMON-SLS-PERFUME | ALL | 停止 | item | 香水、フレグランス、香水・フレグランス、perfume、perfumes、fragrance、fragrances、オードパルファム ほか13語 | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-NAIL | ALL | 停止 | item | マニキュア、ネイルポリッシュ、ネイルケア、つけ爪、付け爪、ネイルシール、ネイル用具、ネイルチップ ほか6語 | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-NAIL-COAT | ALL | 停止 | item | ネイル用ベースコート、ネイル用トップコート、nail base coat、nail top coat | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-HAIRCOLOR | ALL | 停止 | item | ヘアカラー、白髪染め、白髪かくし、染毛剤、カラートリートメント、カラーシャンプー、カラーオンリタッチ、Hair Colour ほか1語 | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-SETTING | ALL | 停止 | item | メイクセッティングスプレー、メイクのセッティングスプレー、メイクキープスプレー、セッティングスプレー、setting spray | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-OIL | ALL | 停止 | item | ベビーオイル、エッセンシャルオイル、baby oil、essential oil、Essential Oils | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-DIFFUSER | ALL | 停止 | item | ディフューザー、加湿器、オイルバーナー、diffuser、humidifier、oil burner | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-SANITIZER | ALL | 停止 | item | 手指消毒剤、手指消毒、hand sanitizer、hand sanitiser | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-LAUNDRY | ALL | 停止 | item | 洗濯洗剤、laundry detergent、Laundry Detergent、洗濯用洗剤、洗たく洗剤、洗たく用洗剤、衣料用洗剤、衣類用洗剤 ほか21語 | 自分の方針 | DEC-0167 / DEC-0180; Ownerの方針による衣料用洗剤・柔軟剤の共通停止。 |
| COMMON-SLS-LAUNDRY-CATEGORY | ALL | 停止 | item | 洗濯・仕上げ剤 | 自分の方針 | DEC-0180; Ownerの方針による洗濯・仕上げ剤カテゴリの共通停止。 |
| COMMON-SLS-PAINT | ALL | 停止 | item | 油絵の具、油絵具、oil paint | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-CAROIL | ALL | 停止 | item | 自動車用オイル、エンジンオイル、ブレーキフルード、クーラント、モーターオイル、engine oil、motor oil、brake fluid ほか9語 | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-COIN | ALL | 停止 | item | コイン、coin、coins | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 |
| COMMON-SLS-PLANT | ALL | 停止 | item | 植物、plants | 自分の方針 | DEC-0167; SLS表2026-09-17のNO商品群を検出。AmazonカテゴリによるShopeeカテゴリ自動割当・ALLOW生成は行わない。。SLS輸送確認。 DEC-0168; 商品名・カテゴリに限定し植物由来・植物性・植物エキス・植物オイル・植物アロマを除く。 |
| COMMON-SLS-PLANT-OTHER | ALL | 停止 | item | 種子、園芸用土、培養土、種まき用、生きた動物、生体販売、seeds、gardening soil ほか5語 | 自分の方針 | DEC-0167 / DEC-0168 / DEC-0170; 種子は商品名・カテゴリのみ、種子油・種子エキス・種子オイルを除外。他の土・生体等の対象欄と停止は維持。SLS輸送確認。 |
| COMMON-SLS-FOOD | ALL | 停止 | item | 食用油、牛乳、乳製品、鶏卵、生卵、卵、豆腐、アイスクリーム ほか29語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| SG-GUM | SG | 停止 | item | チューイングガム、chewing gum、bubble gum、ガム | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| SG-MEAT | SG | 停止 | content | 肉入り、牛肉入り、豚肉入り、鶏肉入り、ビーフジャーキー、ポークジャーキー、サラミ、ソーセージ ほか9語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| SG-RADIO | SG/MY/TH/TW | 停止 | content | 通信機器、無線機、トランシーバー、walkie talkie、two-way radio | 自分の方針 | DEC-0167; Ownerの出品方針による停止 DEC-0189; 指定された追加国にも適用。 |
| SG-SPECIFIC | SG | 停止 | content | 護身用ペン、護身用バトン、護身用スティック、自己防衛用スティック、self defence baton、self defense pen、ダガー、銃剣 ほか19語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| SG-AMULET | SG | 停止 | item | お守り | 自分の方針 | DEC-0168; SGのお守り商品だけを停止。お守りください／お守り下さいを除く。 |
| SG-KITCHEN-KNIFE | SG | 停止 | content | 包丁、kitchen knife、chef knife | 自分の方針 | DEC-0129 / DEC-0167; SGの包丁本体を停止し、付属品の本体・同梱確認を維持する。 |
| SG-LASER | SG | 停止 | content | レーザーポインター、laser pointer | 自分の方針 | DEC-0167; Ownerの出品方針による停止。SLS輸送確認。 |
| SG-FOOD | SG | 停止 | content | 未殺菌乳、殺菌していない乳製品、non-pasteurised dairy、野生キノコ、wild mushroom | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| SG-NASAL | SG | 停止 | item | 鼻のケア、鼻腔洗浄、鼻洗浄、ベビーオーラルケア、鼻吸い器、車用芳香剤、車用香水、車載スピーカー ほか12語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止。SLS輸送確認。 |
| PH-ORAL | PH | 停止 | item | 歯ブラシ、ハブラシ、歯磨き粉、歯みがき粉、歯磨剤、デンタルフロス、マウスウォッシュ、矯正用品 ほか12語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| PH-GAMBLING | PH | 停止 | item | トランプ、サイコロ、ルーレット、ポーカーチップ、カジノチップ、playing cards、dice、roulette ほか1語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| PH-NEEDLE | PH | 停止 | content | ダーマローラー、マイクロニードル、タトゥー用針、眉タトゥー用針、tattoo needle、microblading needle、derma roller、microneedle | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| PH-OTHER | PH | 停止 | content | 免税品、ペット用の薬、動物用医薬品、pet medicine、ナンバープレート、政府のステッカー、ICCステッカー、テロをテーマにした玩具 ほか15語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| PH-CERTIFICATION | PH | 停止 | content | PSマーク、ICCマーク、PS認証、ICC認証 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| PH-USED | PH | 停止 | content | ベビー用品、下着、化粧品、コンタクトレンズ、baby product、underwear、cosmetics、contact lens ほか3語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| PH-SLS | PH | 停止 | content | 潤滑剤、性機能向上、肥料、投資用貴金属、投資用プラチナ、投資用金、投資用銀、投資用ダイヤ ほか23語 | 自分の方針 | DEC-0167; Ownerの出品方針による停止。SLS輸送確認。 |
| TH-TW-FOOD | TH/TW | 停止 | item | 食品、食品・飲料、food、food & beverages、grocery、スナック、飲料 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 |
| COMMON-MEDICAL-DISPLAY | ALL | 停止 | content | COVID-19 test kit、COVID19 test kit、HIV test kit、OTC、OTC drug、OTC drugs、OTC medicine、condom ほか48語 | 自分の方針 | DEC-0159 / DEC-0164 / DEC-0167; 医薬品・医療機器・医薬部外品の肯定表示によるOwnerの出品除外。直接の否定文を区別する。 |
| COMMON-MEDICAL-SCAR-CARE | ALL | 停止 | content | 傷あとケア、傷跡ケア、傷あとケアテープ、傷跡ケアテープ、術後ケア、手術後ケア、手術後の傷あと、シリコーンジェルシート ほか9語 | 自分の方針 | DEC-0179; Ownerの出品方針に基づく共通停止。 |
| COMMON-CONTACT-LENSES | SG/PH | 停止 | content | contact lenses、コンタクトレンズ、カラコン、カラーコンタクト、カラーコンタクトレンズ | Shopee公式 | DEC-0159 / DEC-0164 / DEC-0170; 医療機器表示停止を維持。注意書きで外す・着用者への明確な指示だけを除外。 |
| COMMON-CONTACT-LENSES-OTHER-MARKETS | MY/TH/TW | 停止 | content | contact lenses、コンタクトレンズ | 自分の方針 | DEC-0159; 全市場の医療機器を出品除外とするOwner方針。 |
| CONTACT-LENS-SINGULAR | SG | 停止 | content | contact lens | Shopee公式 | DEC-0159 / DEC-0164; 既存の医療機器表示停止と出典を維持。 |
| CONTACT-LENS-SINGULAR-OTHER-MARKETS | MY/TH/TW | 停止 | content | contact lens | 自分の方針 | DEC-0159; 全市場の医療機器を出品除外とするOwner方針。 |
| PH-CONTACT-LENS-SINGULAR | PH | 停止 | content | contact lens | 自分の方針 | DEC-0159; PHのレンズ本体を停止し、空ケースだけを本体とみなさない。 |
| PH-OTHER-COLOR-CONTACT | PH/MY/TH/TW | 停止 | content | カラコン、カラーコンタクト | 自分の方針 | DEC-0159; 既存PHのカラーコンタクト停止を維持。 |
| COMMON-QUASI-FACT | ALL | 停止 | content | 医薬部外品、指定医薬部外品、薬用、有効成分、quasi-drug、quasi-drugs、quasi drug、quasi drugs ほか1語 | 自分の方針 | DEC-0159 / DEC-0164 / DEC-0167; 医薬品・医療機器・医薬部外品の肯定表示によるOwnerの出品除外。直接の否定文を区別する。 |
| COMMON-PENALTY-ASIN | ALL | 停止 | item | B000FQTRS0 | ペナルティ経験 | DEC-0167; Own Shopee penalty and delist case for Kaminomoto S-II / S-2 |
| COMMON-PENALTY-TITLE | ALL | 停止 | item | 薬用加美乃素S-II、薬用加美乃素S-2、加美乃素S-II、加美乃素S-2、Kaminomoto S-II、Kaminomoto S-2 | ペナルティ経験 | DEC-0167; Own Shopee penalty and delist case for Kaminomoto S-II / S-2 |
| SLS-CATEGORY-EVIDENCE-ALL-BLOCK | ALL | 停止 | item | Automobiles > Automobile Spare Parts > Electronics > Batteries & Accessories、Automobiles > Automobiles、Automobiles > Automotive Oils & Lubes > Antifreezes & Coolants、Automobiles > Automotive Oils & Lubes > Automotive Fluids > Brake Fluids、Automobiles > Automotive Oils & Lubes > Automotive Fluids > Others、Automobiles > Automotive Oils & Lubes > Automotive Fluids > Transmissions Fluids、Automobiles > Automotive Oils & Lubes > Fuel Additives & Savers、Automobiles > Automotive Oils & Lubes > Greases & Lubricants ほか144語 | Shopee公式 | DEC-0167; source-lock master SHA-256 35f7bab5da9c5dd3d9b62456035916a9fce62a153d6bcfcaa82c221dc117dbc9; 具体的な商品分類の完全パス一致のみ。ShopeeカテゴリID割当・SLS ALLOWを生成しない。。SLS輸送確認。 |
| SLS-CATEGORY-EVIDENCE-ALL-REVIEW | ALL | 要確認 | item | Health > Others、Health > Personal Care > Others | Shopee公式 | DEC-0167; source-lock master SHA-256 35f7bab5da9c5dd3d9b62456035916a9fce62a153d6bcfcaa82c221dc117dbc9; 具体的な商品分類の完全パス一致のみ。ShopeeカテゴリID割当・SLS ALLOWを生成しない。。SLS輸送確認。 |
| SLS-CATEGORY-EVIDENCE-SG-BLOCK | SG | 停止 | item | Automobiles > Automobile Interior Accessories > Amplifiers, Speakers & Subwoofers、Automobiles > Automobile Interior Accessories > Perfumes, Air Fresheners & Purifiers、Food & Beverages > Dairy & Eggs > Others、Health > Medical Supplies > Nasal Care、Health > Medical Supplies > Over-the-counter Medicine、Mom & Baby > Baby Healthcare > Baby Oral Care、Mom & Baby > Baby Healthcare > Nasal Care、Spare Parts and Accessories for Vehicles > Spare Parts for Automobiles > Additive and Lubricant ほか9語 | Shopee公式 | DEC-0167; source-lock master SHA-256 35f7bab5da9c5dd3d9b62456035916a9fce62a153d6bcfcaa82c221dc117dbc9; 具体的な商品分類の完全パス一致のみ。ShopeeカテゴリID割当・SLS ALLOWを生成しない。。SLS輸送確認。 |
| SLS-CATEGORY-EVIDENCE-PH-BLOCK | PH | 停止 | item | Fashion Accessories > Investment Precious Metals > Diamond、Fashion Accessories > Investment Precious Metals > Jade、Fashion Accessories > Investment Precious Metals > Others、Fashion Accessories > Investment Precious Metals > Platinum & K Gold、Fashion Accessories > Investment Precious Metals > Silver、Health > Sexual Wellness > Condoms、Health > Sexual Wellness > Lubricants、Health > Sexual Wellness > Performance Enhancement ほか11語 | Shopee公式 | DEC-0167; source-lock master SHA-256 35f7bab5da9c5dd3d9b62456035916a9fce62a153d6bcfcaa82c221dc117dbc9; 具体的な商品分類の完全パス一致のみ。ShopeeカテゴリID割当・SLS ALLOWを生成しない。。SLS輸送確認。 |
| SLS-CATEGORY-EVIDENCE-PH-REVIEW | PH | 要確認 | item | Health > Sexual Wellness > Others | Shopee公式 | DEC-0167; source-lock master SHA-256 35f7bab5da9c5dd3d9b62456035916a9fce62a153d6bcfcaa82c221dc117dbc9; 具体的な商品分類の完全パス一致のみ。ShopeeカテゴリID割当・SLS ALLOWを生成しない。。SLS輸送確認。 |
| COMMON-POWERCORE-SIGNAL | ALL | 要確認 | content | PowerCore | 自分の方針 | DEC-0167; 既存SG PowerCoreの電池疑義を維持し共通化。。SLS輸送確認。 |
| PH-KITCHEN-KNIFE | PH | 停止 | item | kitchen knife、chef knife、包丁 | 自分の方針 | DEC-0167; 既存PH-D070～PH-D072の包丁停止を維持。 |
| COMMON-TRANSPORT-PESTICIDE | ALL | 停止 | content | 殺虫剤、農薬、除草剤、pesticide、pesticides、insecticide、insecticides、殺虫 ほか10語 | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| COMMON-ALCOHOL-CATEGORY | ALL | 停止 | item | お酒 | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| COMMON-ALCOHOL-STRENGTH | ALL | 停止 | content | アルコール分 | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| COMMON-DISEASE-TEST | ALL | 停止 | content | HIV、抗原検査キット、PCR検査キット、PCR 検査キット、新型コロナ 検査キット、新型コロナ検査キット | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| SG-GENERAL-KNIFE | SG | 停止 | content | ナイフ、knife | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| SG-WEAPON-ADDITIONAL | SG | 停止 | content | モデルガン、模造刀、居合刀、ガスガン、電動ガン、ガスブローバック、特殊警棒、警棒 ほか6語 | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| SG-WEAPON-PART | SG | 停止 | content | マガジン、弾倉、銃身 | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| SG-ELECTRIC-VEHICLE | SG | 停止 | content | 電動キックボード、電動アシスト自転車、e-bike | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| SG-PETFOOD | SG | 停止 | item | ドッグフード、キャットフード、ペットフード、猫用おやつ、犬用おやつ、ペット用おやつ、ペットのおやつ、犬のおやつ ほか7語 | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| SG-ANIMAL-FAT | SG | 停止 | content | ラード、牛脂、ヘット | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。; DEC-0188: 成分欄も照合（食品のみ） |
| SG-MAGNETIC-PUTTY | SG/MY/TH/TW | 停止 | content | マグネットパテ、磁石スライム、magnetic putty | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 DEC-0189; 指定された追加国にも適用。 |
| SG-RESTRICTED-ELECTRONICS | SG | 停止 | content | レーダー探知機、スクランブラー | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| SG-HUMAN-HAIR | SG | 停止 | content | 人毛、human hair | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| SG-MUSHROOM | SG | 停止 | content | しいたけ、椎茸、きのこ、キノコ、まいたけ、舞茸、しめじ、なめこ ほか4語 | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。; DEC-0188: 成分欄も照合（食品のみ） |
| PH-TOY-WEAPON-DIRECT | PH/MY/TW | 停止 | content | 水鉄砲、BB弾 | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 DEC-0189; 指定された追加国にも適用。 |
| PH-TOY-WEAPON-CONTEXT | PH/MY/TW | 停止 | content | 銃、ピストル、ライフル、ガン | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 DEC-0189; 指定された追加国にも適用。 |
| PH-TATTOO | PH | 停止 | content | タトゥーマシン、タトゥー針、アートメイク、刺青 | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| PH-PET-DRUG | PH | 停止 | content | ノミ、ダニ、駆虫薬 | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| PH-COSMETIC-MASK | PH | 停止 | item | フェイスマスク、シートマスク、フェイスパック、シートパック | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 |
| SG-PETFOOD-CATEGORY | SG | 停止 | item | ペット用品 | 自分の方針 | DEC-0182; SGのペットフード発送禁止（2026-03-30〜）。ペット用品配下のフード・おやつ類カテゴリを停止。 |
| SG-MEDICAL-PROTECTIVE | SG | 停止 | content | 医療用手袋、医療用グローブ、検査用手袋、診察用手袋、メディカルグローブ、防護服、防護ガウン、サージカルガウン ほか2語 | 自分の方針 | DEC-0182; SGで医療機器扱いとなる医療用手袋・防護服類をOwner方針で停止。 |
| SG-DISPOSABLE-GLOVE | SG | 要確認 | item | ニトリル手袋、ニトリルグローブ、使い捨て手袋、使い捨てグローブ、使い捨てゴム手袋、使い捨てビニール手袋、ディスポ手袋、ディスポーザブル手袋 ほか1語 | 自分の方針 | DEC-0182; 使い捨て手袋は医療用の場合SGで医療機器扱い。用途（医療用か否か）を確認。 |
| PH-OUTDOOR-KNIFE | PH | 停止 | content | アウトドアナイフ、サバイバルナイフ、フォールディングナイフ、折りたたみナイフ、折り畳みナイフ、ハンティングナイフ、シースナイフ、タクティカルナイフ ほか9語 | 自分の方針 | DEC-0182; PHで刃物（包丁以外）を停止。研ぎ器の語は除く。 |
| SG-MEAT-PROCESSED | SG | 要確認 | item | ビーフ、ポーク、チキン、牛肉、豚肉、鶏肉、ハンバーグ、ミートボール ほか13語 | 自分の方針 | DEC-0182; SGは肉類・肉入り加工食品の持込制限あり。肉の有無を確認（ジャーキー等の明示語は従来のSG-MEATでBLOCK）。 |
| COMMON-SLS-AROMA | ALL | 停止 | item | アロマオイル、精油、aroma oil | Shopee公式 | DEC-0186; SLSで発送不可（NO）のShopeeカテゴリに当たる商品群を語で止める（カテゴリ番号は使わない）。 エッセンシャルオイル類。配合・香り表示は除く。 |
| COMMON-SLS-SETTING-SPRAY | ALL | 停止 | item | メイクキープミスト、メイクキープスプレー、フィックスミスト、フィクシングミスト、セッティングスプレー、セッティングミスト、化粧崩れ防止ミスト、化粧崩れ防止スプレー ほか1語 | Shopee公式 | DEC-0186; SLSで発送不可（NO）のShopeeカテゴリに当たる商品群を語で止める（カテゴリ番号は使わない）。 メイク仕上げ用スプレー（Setting & Finishing Spray）。 |
| COMMON-SLS-ADULT | ALL | 停止 | item | 大人のおもちゃ、ラブグッズ、sex toy、sex toys | Shopee公式 | DEC-0186; SLSで発送不可（NO）のShopeeカテゴリに当たる商品群を語で止める（カテゴリ番号は使わない）。 Sexual Wellness > Sex Toys。 |
| COMMON-SLS-CAR-CHECK | ALL | 要確認 | item | カーワックス、車用ワックス、洗車、カーシャンプー、ガラス撥水、撥水剤、油膜取り、ガラコ ほか6語 | Shopee公式 | DEC-0186; SLSで発送不可（NO）のShopeeカテゴリに当たる商品群を語で止める（カテゴリ番号は使わない）。 SLSで「Shopeeと要確認」の車用品（洗車・ワックス・撥水・タイヤ・燃料系）。 |
| SG-TOY-GUN | SG | 要確認 | content | ウォーターガン、トイガン、おもちゃの銃、ゴム鉄砲、輪ゴム銃、toy gun、トイブラスター、toy blaster ほか1語 | Shopee公式 | DEC-0186; SLSで発送不可（NO）のShopeeカテゴリに当たる商品群を語で止める（カテゴリ番号は使わない）。 Toys > Blasters & Toy Guns。既存のSG判断（水鉄砲は要確認）に合わせ要確認。 |
| SG-SLS-BATTERY-TOOL | SG | 要確認 | item | バッテリー充電器、バッテリーチャージャー、バッテリーテスター | Shopee公式 | DEC-0186; SLSで発送不可（NO）のShopeeカテゴリに当たる商品群を語で止める（カテゴリ番号は使わない）。 Vehicular Tools > Battery Tools。充電器単体は既存の電池判断に合わせ要確認。 |
| PH-PRECIOUS-REVIEW | PH/TH | 要確認 | item | 純金、純銀、翡翠、ヒスイ、ジェイド | Shopee公式 | DEC-0186; SLSで発送不可（NO）のShopeeカテゴリに当たる商品群を語で止める（カテゴリ番号は使わない）。 PHのInvestment Precious Metals（投資用の金・銀・翡翠）。宝飾品か投資用かを確認。 DEC-0189; 指定された追加国にも適用。 |
| COMMON-SLS-VEHICLE | ALL | 停止 | item | 自動車本体、車両本体、中古車、中古バイク、バイク本体 | Shopee公式 | DEC-0187; Shopee販売規制ガイド（SG p4／PH p9）の品目で、代表商品名が止まらなかったもの。 車・バイク本体（SGの販売禁止品目「車」、SLSのAutomobiles／MotorcyclesもNO）。 |
| COMMON-OFFICIAL-REVIEW | ALL | 要確認 | item | 迷彩服、自衛隊、軍用、米軍、暗視スコープ、ナイトビジョン、運転免許証 | Shopee公式 | DEC-0187; Shopee販売規制ガイド（SG p4／PH p9）の品目で、代表商品名が止まらなかったもの。 政府・警察・軍の制服に酷似した品、軍事機器。ファッションの迷彩柄や免許証ケースと区別するため要確認。 |
| SG-MAGNETIC-CLAY | SG/MY/TH/TW | 停止 | content | 磁性粘土 | 自分の方針 | DEC-0167; Ownerの出品方針による停止 DEC-0189; この語だけ対象国を拡張。 |
| SG-LOCK-PICKING | SG/MY/TW | 停止 | content | 錠前破り | 自分の方針 | DEC-0167; Ownerの出品方針による停止 DEC-0189; この語だけ対象国を拡張。 |
| SG-PICKING-TOOL | SG/MY/TW | 停止 | content | ピッキングツール | 自分の方針 | DEC-0181; Ownerの指定商品群を停止。 DEC-0189; この語だけ対象国を拡張。 |
| MY-HALAL-FOOD | MY | 停止 | content | 豚、豚肉、ポーク、pork、ラード、lard、豚脂、豚骨 ほか29語 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。食品だけに適用。ハラール認証の有無を推定しない。 |
| MY-PORK-OTHER | MY | 要確認 | item | 豚毛、猪毛、boar bristle | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| MY-SUGAR-RICE | MY | 停止 | item | 砂糖、上白糖、グラニュー糖、三温糖、米、お米、白米、玄米 ほか3語 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。米の語境界と食品条件を使う。米粉・米ぬか・米国等を除く。 |
| MY-RICE-SNACK | MY | 要確認 | item | 米菓、せんべい、煎餅、あられ、おかき | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| MY-KNIFE | MY | 停止 | item | 包丁、kitchen knife、ナイフ、knife、短剣、dagger | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| MY-EYEWEAR | MY | 停止 | item | メガネ、眼鏡、めがね、老眼鏡、リーディンググラス、ブルーライトカットメガネ、ブルーライトカット眼鏡、PCメガネ ほか4語 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。ケース・拭き・クロス・クリーナー・チェーン・ストラップ等の付属品を除く。 |
| MY-WEIGHT-GAIN | MY | 停止 | content | 体重増加、増量、weight gain | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。増量だけは体重増加用ビタミン等の文脈に限定し、通常の増量包装を除く。 |
| MY-SYRINGE-SHAPE | MY | 停止 | item | 注射器型、注射器の形、シリンジ型、syringe pen | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| MY-RELIGIOUS | MY | 停止 | content | コーラン、クルアーン、Quran、Koran、アッラー、Allah | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| MY-TW-SPY-CAMERA | MY/TW | 停止 | item | 隠しカメラ、スパイカメラ、小型カメラ 盗撮、hidden camera、spy camera | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| MY-SAFETY-HELMET | MY | 要確認 | item | 安全ヘルメット、作業用ヘルメット、工事用ヘルメット、hard hat | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。自転車・バイク用は除く。 |
| MY-APHRODISIAC | MY | 停止 | content | 精力剤、精力増強、強精 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| TH-TW-COSMETICS | TH/TW | 停止 | item | ビューティー、ラグジュアリービューティー、化粧水、乳液、美容液、美容クリーム、フェイスクリーム、洗顔 ほか21語 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。カテゴリは最上位のビューティー2区分だけ。その他の語は商品名で判定。 |
| TH-TW-DRUGSTORE | TH/TW | 要確認 | item | ドラッグストア | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。最上位カテゴリだけ。別の停止があれば停止を優先。 |
| TH-ELECTRIC | TH | 停止 | item | 家電&カメラ、パソコン・周辺機器、大型家電、AC100V、コンセント式、電源コード、USB給電、ACアダプター | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。カテゴリは指定の最上位3区分だけ。その他の語は商品名で判定。 |
| TH-CAR-PARTS | TH | 停止 | item | 車&バイク | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| TH-CHEMICAL | TH | 要確認 | item | 洗剤、除菌剤、殺菌剤、消臭剤、芳香剤、接着剤、塗料、溶剤 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。ライセンス対象の範囲が広いため要確認。 |
| TH-LICENSE-OTHER | TH | 停止 | item | ドローン、drone、トランシーバー、無線機、walkie talkie、GPS、GPSトラッカー、発信機 ほか20語 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| TW-HEALTHCARE | TW | 停止 | item | ヘルスケア、医療、衛生用品 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。カテゴリのどの階層でも指定語を含めば停止。 |
| TW-BABY | TW | 停止 | item | ベビーフード、離乳食、チャイルドシート、ベビーカー、ウォーキングチェア、歩行器、ベビーチェア、ハイチェア ほか3語 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| TW-HAIR-IRON | TW | 停止 | item | ヘアアイロン、カールアイロン、ストレートアイロン、コテ、hair iron | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。コテは商品名・カテゴリがヘア用を示す場合だけ。 |
| TW-SUNGLASSES | TW | 停止 | item | サングラス、sunglasses | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| TW-BLADE | TW | 停止 | item | 包丁、ナイフ、刃物、刀、剣、おもちゃの刀、日本刀、ダーツ ほか5語 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。パチンコは玩具の投石器を示す文脈だけ。 |
| TW-BLADE-REVIEW | TW | 要確認 | item | はさみ、ハサミ、カッター、カミソリ | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| TW-FLEA | TW | 停止 | item | ノミ取り、ノミ・ダニ、蚤、flea | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| TW-BEAUTY-DEVICE | TW | 停止 | item | 光美容器、LED美顔器、美顔器、脱毛器、光脱毛 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| TW-TAMPON | TW | 停止 | item | タンポン、tampon | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| TW-LICENSE-ELECTRIC | TW | 停止 | item | USBメモリ、USB電源、USB充電器、ACアダプター、テレビ、テレビボックス、冷蔵庫、エアコン ほか12語 | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |
| TW-SAFETY-HELMET | TW | 停止 | item | 安全ヘルメット、ヘルメット | 自分の方針 | DEC-0189; Shopee販売規制ガイド2026-08-13版とOwner決定2026-11-13。 |

## コード内のルール

| ID | 国 | 動作 | scope | 対象 | 根拠 | メモ |
|---|---|---|---|---|---|---|
| CODE-QUASI-DRUG | ALL | 停止 |  | 医薬部外品・薬用・有効成分・medicated などの表示（否定文は区別） | 自分の方針 | QUASI_DRUG_TERMS |
| CODE-HOME-APPLIANCE | ALL | 停止 |  | 家電本体・電動の商品（未確定は要確認。受動的な付属品は対象外） | 自分の方針 | DEC-0166 |
| CODE-BATTERY-PRESENCE | ALL | 停止 |  | 電池入り・電池付属の商品（電池別売の明記は区別） | 自分の方針 | 電池入りは出品しない |
| CODE-SG-BODY | SG | 要確認 |  | SGの本体・実同梱の確認が必要な商品 | 自分の方針 | SG本体確認 |
| CODE-MARKET-NG-INCOMPLETE | ALL | 要確認 |  | 国別の禁止設定が未完成の国だけ、通過候補を要確認にする | 自分の方針 | DEC-0183／0184／0189（SG・PH・MY・TH・TWは設定済み） |
| MY-VOLUMETRIC | MY | 要確認 |  | 容積重量kg＝縦cm×横cm×高さcm÷6000 が実重量kgを上回る商品 | 自分の方針 | DEC-0189; 梱包値を優先、商品値へfallback。欠損時は通過を妨げずサイズ情報なしと記録 |
| CODE-SLS-CATEGORY-PH | PH | 停止 |  | Shopeeカテゴリ確定後、SLSで発送不可のカテゴリ（Sora保安ゲートには未接続） | Shopee公式 | カテゴリ対応画面のみ |
| CODE-SLS-CATEGORY-SG | SG | 停止 |  | Shopeeカテゴリ確定後、SLSで発送不可のカテゴリ（Sora保安ゲートには未接続） | Shopee公式 | カテゴリ対応画面のみ |

## 成分・事実による停止

| ID | 国 | 動作 | scope | 対象 | 根拠 | メモ |
|---|---|---|---|---|---|---|
| PH-V2-INGREDIENT-GABA-001 | ALL | 停止 |  | ingredient_safety: GABA | 仲間内報告 | DEC-0042; Owner operational BLOCK; not a Shopee official prohibition claim |
| PH-V2-INGREDIENT-GABA-002 | ALL | 停止 |  | ingredient_safety: GABA | 仲間内報告 | DEC-0042; Owner operational BLOCK; not a Shopee official prohibition claim |
| PH-V2-INGREDIENT-GABA-003 | ALL | 停止 |  | ingredient_safety: GABA | 仲間内報告 | DEC-0042; Owner operational BLOCK; not a Shopee official prohibition claim |
| PH-V2-INGREDIENT-GABA-004 | ALL | 停止 |  | ingredient_safety: GABA | 仲間内報告 | DEC-0042; Owner operational BLOCK; not a Shopee official prohibition claim |
| PH-V2-INGREDIENT-GABA-005 | ALL | 停止 |  | ingredient_safety: GABA | 仲間内報告 | DEC-0042; Owner operational BLOCK; not a Shopee official prohibition claim |
| PH-V2-INGREDIENT-GABA-006 | ALL | 停止 |  | ingredient_safety: GABA | 仲間内報告 | DEC-0042; Owner operational BLOCK; not a Shopee official prohibition claim |
| PH-V2-PRODUCT-TEXT-HEMP-001 | ALL | 停止 |  | product_text: hemp | 自分の方針 | DEC-0050; DEC-0167 Owner-approved common literal substring BLOCK for product text; includes hemp-free and hempseed |

## 一覧に載せていない細目

ブランド、国別辞書、仲間内報告、SLS発送可否（発送不可・要確認のカテゴリ）は件数が多いため、
上の表は件数だけです。1件ずつの内容は `NG/ledger.csv` を表計算ソフトで開いて絞り込みます。
SLS発送可否は、Shopeeのカテゴリが確定した後のカテゴリ対応画面でだけ使われ、Soraの保安ゲートには接続していません。
SLSの表はSG・PH・MY・TH・TWを載せています（VN・BRは保存済みで後続工程）。

## 同じ語が2か所にある場合

自分たちで書いたルール（保安ルール・国別辞書・電池・成分・自社方針ブランド）で、同じ語が複数の行にあるものは
`NG/overlaps.csv` に出ます。新しい重なりができるとテストが失敗します。1つにまとめるか、意図的な重なり
（例：商品名は停止・説明文は要確認）なら `NG/overlaps_accepted.txt` に語を足します。
