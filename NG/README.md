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
3. **台帳を作り直す**：`python scripts/build_ng_ledger.py`。同じ語の重なりが新しくできたと表示されたら、1つにまとめる。意図的な重なり（例：商品名は停止・説明文は要確認）だけ `overlaps_accepted.txt` に足し、PRに理由を書く。
4. **テスト**：止まってほしい商品名と、止まってほしくない似た商品名（止めすぎ防止）の両方をテストに足す。
5. **判断記録**：Ownerの判断で足したNGは `docs/DECISION_LOG.md` に新しいDEC番号で残す。

FROMAXのNG登録は台帳の外にある。Soraで止まったASINは、FROMAXにも登録するようOwnerに伝える。
