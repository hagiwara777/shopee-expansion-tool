# NG台帳

Soraが「停止」「要確認」を出す根拠を、1か所で見るためのフォルダです（DEC-0185）。

| ファイル | 内容 |
|---|---|
| `LEDGER.md` | 全体の索引。グループ別・国別の件数と、保安ルール・コード内ルールの一覧 |
| `ledger.csv` | 全行（ブランド、国別辞書、仲間内報告、SLS発送可否を含む）。表計算ソフトで絞り込める |
| `overlaps.csv` | 自分たちで書いたルールの中で、同じ語が2か所以上にあるもの（自動生成） |
| `overlaps_accepted.txt` | 意図的な重なりとして認めた語（人が書く）。ここに無い重なりが増えるとテストが失敗する |

- どちらも `python scripts/build_ng_ledger.py` が自動で作ります。**直接編集しません。**
- 判定を変えるときは、`LEDGER.md` の「元ファイル」欄にあるファイルを直してから、スクリプトを実行します。
- `guardrails/` に新しいファイルを足して台帳に載せ忘れると、テストが失敗します（載せ忘れ防止）。
- ClaudeやCodexに頼むときは「`NG/LEDGER.md` を見て」と伝えれば、全体を把握できます。

## Claudeのリサーチskillでの使い方

リサーチskill（投げ網・sold帯・一本釣り）は、商品名による先回りの除外にこの台帳を使います（手書きの語リストは持ちません）。

- `ledger.csv` の行のうち、対象国（`markets` が `ALL` か対象国を含む）で `action` が `BLOCK` のものを「除外」、`REVIEW` は「残して注意を書く」。
- 保安ルールの `target` は語を「、」で区切った全語。ブランド行の `target` はブランド名。
- SLS発送可否の行は、集めるカテゴリ・商品群を選ぶときに避ける目安に使う。
- 最終判定は常にSoraの保安ゲート。台帳による除外は手間を減らすための先回りにすぎない。

## NGを足す・変えるときの手順（この順番だけを使う）

1. **既存の行を探す**：`ledger.csv` で語・ブランド・ASINを検索する。すでにあれば、その行の元ファイルを直す（新しく書き足さない）。
2. **書く場所を種類で決める**（1つのNGは1か所だけに書く）：

   | NGの種類 | 書く場所 |
   |---|---|
   | 語で止める／要確認（全ての国・国別） | `guardrails/policy/rules.json`（既存のルールに語を足すのが基本。新しいまとまりだけ新しいID） |
   | 止めすぎを防ぐ除外（「〜ケース」など） | `modules/safety_policy.py` の除外（`_mask_official_gap_exclusions`） |
   | 自分の方針で止めるブランド | `guardrails/brand_monitoring/company.json` |
   | Shopee公式のIPR／Counterfeitリスト | `guardrails/brand_monitoring/` の各リスト（公式の更新時だけ） |
   | 仲間内で報告されたASIN・ブランド | `guardrails/community_ng/` |
   | 成分で止める | `guardrails/deterministic_block_rules_v2.csv` |

   国別の禁止ブランド・危険語（`guardrails/*_sg.csv`／`*_ph.csv`）は既存分の保守だけに使い、新しいNGは`rules.json`に書く。

   **保安ルールには必ず `scope` を付ける**（DEC-0188）。値は次の2つだけとし、欠落・不正値は読込エラーにする。

   | scope | 方針と対象欄 |
   |---|---|
   | `item`（物そのもの） | SLS発送区分の商品群、食品の種類、マスク等、商品名かカテゴリに出る物の種類を止める。`fields` は元からあった `title`／`category` だけを残し、説明文の `text` と成分の `ingredients` を入れない。既存のブランド／ASIN一致ルールはその対象欄を維持する |
   | `content`（中身・表示） | 医薬・成分NG・電池・引火性・エアゾール・武器・アダルト・酒類・たばこ・金融・公的物品・違法品等、違法やペナルティにかかわる表示を広めに止める。既存の `fields` を維持し、指定された説明文・成分も照合する |

   卵・食用油・牛乳そのものを止める `item` ルールでは、加工食品の説明や原材料にその語があるだけでは止めない。
   既存の `title`／`category`／`brand`／`asin` だけのルールは対象欄を変えず `item` とする。
   `COMMON-GENERAL-TEXT-*` は、別の意味もある語を説明文では要確認にする既存方針のため `content` を維持する。
   SGの肉・ラード・きのこ等を原材料に含む食品の停止は `content` のまま維持する。
   Owner指定の例外として `SG-ANIMAL-FAT`／`SG-MUSHROOM` にだけ `ingredients` を追加する。
   動物性脂肪の成分欄は食品判定が成立したときだけ有効（石けん等は対象外）とし、商品名・説明文は従来の `always` を維持する。
   きのこの `mushroom_food` 条件は変えず、他の `content` ルールの対象欄は広げない。
   保存表示の `COMMON-COLD-FOOD-LABEL`、酸化剤成分の `COMMON-TRANSPORT-OXIDIZER-INGREDIENT` も `content` とする。
   全ルールの区分・対象欄は `rules.json`、区分の一覧は再生成した `ledger.csv`／`LEDGER.md` を参照する。

3. **台帳を作り直す**：`python scripts/build_ng_ledger.py`。同じ語の重なりが新しくできたと表示されたら、1つにまとめる。意図的な重なり（例：商品名は停止・説明文は要確認）だけ `overlaps_accepted.txt` に足し、PRに理由を書く。
4. **テスト**：止まってほしい商品名と、止まってほしくない似た商品名（止めすぎ防止）の両方をテストに足す。
5. **判断記録**：Ownerの判断で足したNGは `docs/DECISION_LOG.md` に新しいDEC番号で残す。

FROMAXのNG登録は台帳の外にある。Soraで止まったASINは、FROMAXにも登録するようOwnerに伝える。
