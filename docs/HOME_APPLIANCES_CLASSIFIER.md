# Home Appliances分類補助ツール

保存済みの商品ファイルを読み、商品ごとの候補分類・理由・根拠を一覧CSVへ出す独立CLIです。
画面・DB・cache・API取得は追加していません。既存Safety Shadow V3とは別のルールです。

| 分類 | 意味 |
|---|---|
| A / NON_ELECTRIC_ACCESSORY | 非電動の部品・付属品・消耗品等の候補。出品許可ではありません |
| B / EXCLUDE_POLICY_CANDIDATE | 本体・電源・電池・無線等の当社取扱対象外候補。法律上の販売禁止ではありません |
| C / UNKNOWN | 実体・電源・同梱品・出所が未確認。推測でAへ通しません |

## 使い方

1. このツールのフォルダーでPowerShellを開きます。保存済みのJSON／JSONLを用意します。
2. 次のコマンドの入力ファイル名と出力ファイル名だけを置き換えて実行します。
   Pythonと既存requirementsの導入済み環境を使用します。
3. 作成したCSVをExcel等で開き、「分類結果」列をA／B／Cで絞り込みます。
   Aにも既存のSafety・Gate・Category・Brand・発送条件の確認が必要です。

```powershell
.\.venv\Scripts\python.exe scripts/classify_home_appliances.py --input "保存した商品.json" --source-format keepa_response --output "outputs/家電分類.csv"
```

仮想環境が別の場所にある作業ツリーでは、先頭をその環境のPythonのパスへ置き換えます。
空白を含むPythonのパスには `& "Pythonの絶対パス"` を使います。
新しい出力名を使ってください。既存CSVを上書きせず、入力エラーではCSVを作りません。
ファイルシステムがhard linkを提供しない場合は出力を停止するため、通常のローカルNTFS保存先を使用します。

複数の保存ファイルも、加工せず続けて指定できます。

```powershell
.\.venv\Scripts\python.exe scripts/classify_home_appliances.py --input "商品1.json" "商品2.json" --source-format keepa_response --output "outputs/家電分類2.csv"
```

## 入力

UTF-8（BOMあり／なし）のJSON、または拡張子 `.jsonl` の1行1JSONに対応します。
JSONは単一商品、商品配列、既存の `{"products": [...]}` 応答を直接使えます。
1実行は合計50MiB・10,000商品まで。CSVや業務SQLiteからの取得は行いません。

| --source-format | 使用できる内容・確認条件 |
|---|---|
| keepa_response | 保存したKeepa Product応答。同名title／brand／categoryTree／description／features／shortDescription／itemHighlightsを使用。商品自身のdomainId=5が必要 |
| saved_fact | 既存ProductFacts.to_dict()の `{asin, fields}` 形式。各fieldのvalue／origin／source_asin／acquired_market／evidence_ref／fetched_atをそのまま検証 |
| cache_snapshot | 既存cacheの比較用JSON。旧cacheを確認済みFactと認めず、全件Cを出す |

`saved_fact`は既存`modules/sg_beta_facts.py`のadapter・validatorを再利用します。
保存済みFactの非空の使用項目にはOWN_PRODUCT、同一ASIN、JP、非空evidence_ref、時差付き取得日時が必要です。
seed・他商品・市場不明・出所不明の非空項目はCです。使用項目の出所矛盾を黙って捨ててAにしません。
Keepa原応答の欠けた取得時刻は「未記録」とし、ファイル更新日時・API timestamp・lastUpdateで補いません。
任意の説明項目が欠けた場合は不足列へ表示し、肯定的な実体根拠がなければCです。
ブランド欠損だけでは出品可否を判断せず、分類に必要な商品名・カテゴリが欠ける場合はCです。

`--source-format`とファイル内provenanceは入力者の申告であり、API送信元の電子署名ではありません。
内容hashは入力の取り違え確認用です。old cacheや研究の参照ラベルをKeepa原応答と偽って入力しないでください。
研究用ZIP・分類結果CSVは利用入力ではなく、既知商品の再評価資料です。
研究の古い24商品はタイトル中心の履歴で、完全な項目別Factへ自動変換しません。

ASIN形式不正、JSON重複key、NaN、Fact構造不正、日時不正、重複ASINは入力エラーです。
同一ASINの同じ行も矛盾するスナップショットも、自動で最新に統合しません。
比較したい別スナップショットは別のコマンド／出力名で処理します。
市場・対象ASIN・Fact出所の不一致はCとして根拠を残します。
エラー時は終了コード2と理由コードだけを表示し、商品本文・API設定を端末へ出しません。

## CSV

UTF-8 BOM付きで、ASIN、商品名、ブランド、カテゴリ、分類結果、分類名、理由コード、判断根拠、
不足情報、ルール版、出所、取得時刻、注意事項を出します。数式として読まれる先頭文字は表示用に保護します。
出所は入力形式・入力番号・内容SHA-256です。絶対パスや認証値を出しません。
既存Candidate CSV・Gate CSVとは異なる専用列で、正式入力として接続しません。

表示例（合成例、主要列のみ）:

| 商品名 | 分類結果 | 判定理由コード | 判断根拠の例 |
|---|---|---|---|
| 掃除機用交換フィルター | A | POSITIVE_PASSIVE_SOLD_OBJECT | titleの「フィルター」が販売対象を示す |
| 浄水ポット＋カートリッジ（液晶メモあり） | B | PURIFIER_BODY_WITH_OWN_DISPLAY | title/detailsの「液晶メモ」が本体電子機能を示す |
| 商品セット | C | INSUFFICIENT_POSITIVE_IDENTITY | 販売対象・電源・実際のセット内容が不足 |

## ルールと検証の限界

版は `HOME_APPLIANCES_V3_1`。2026-10-14の研究用RESEARCH_V3とV2を独立モジュールへ移し、
交換カートリッジと浄水器本体セット、改行・空白付き包装内容、曖昧な部品自身の電源を限定的に補います。
ASIN・ブランド・型番別の正解表は使いません。研究に含まれた台所・浄水・充電器・スマートプラグの境界も扱います。
その他カテゴリの汎用分類へ拡張せず、確認できないカテゴリ文脈はCです。

研究72商品・73スナップショットは既知商品の回帰です。V3修正材料を含むので、
その一致結果から未知商品の精度や正式運用可能性を保証しません。
曖昧な名称、複雑なセット、否定表現、対象機器と自商品の電源を取り違える表現は残る制約です。
ルール語の未検出を電池不存在・Safety PASSと扱いません。
追加研究やルールの無制限な追加は今回の範囲外です。

開発確認:

```powershell
python -m pytest tests/test_home_appliances_files.py -q
$env:HOME_APPLIANCES_RESEARCH_ZIP = "研究資料のclassification-continuation/gpt_review.zip"
python -m pytest tests/test_home_appliances_research_replay.py -q
```

研究ZIPと隣接acquisitionファイルを指定したlocal検証だけで実データを再生します。
CIでは研究資料がない2テストを明示skipし、合成の入力・境界・CSV回帰を実行します。
商品本文・研究CSV・DB・cache・生成出力はGitへ保存しません。

## 後続工程の境界

今回の完成は独立CLIの技術的完成です。Safety・Battery・SLS・Gate処分を変更せず、
Aから出品許可、BからSafety BLOCKを作りません。Expansion／Mapperへの組込み、
他カテゴリ展開、GUI、DB／保存基盤改修、API／有料AI、稼働環境反映は後続の別判断です。
CLIと新規出力の使用を停止すれば既存フローへ戻れます。コード復旧は通常revertとし、既存DB等の復旧は不要です。
