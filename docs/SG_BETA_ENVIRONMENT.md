# SGベータの利用環境

普段のPH / SG切替には[統一ベータ](BETA_APPLICATION.md)を使う。以下はSG専用保存設定と旧入口の契約。
旧入口は専用の `SG Beta` ショートカットから起動する。PHの起動先・DBと分離し、
画面は `http://127.0.0.1:8502` を使用する。PHの8501は変更しない。
正式採用されたコードをcommit単位で固定し、変更中の作業用コードでは起動しない。

## 起動と使用データ

ローカルの専用設定は `%LOCALAPPDATA%\ShopeeExpansionTool\SG-Beta\deployment.json`。
設定にはコード・Python・既存API設定・Google reader・承認済み取得枠・保存先のpathを記録する。
秘密値をコピーせず、既存のAPI設定とreaderを参照する。
SGのAccess Tokenは既存の自動更新Bridgeから操作ごとに読み、Mapper側でrefreshしない。

初回資料は同じ専用フォルダの `inputs` に置く。画面で次のファイルを読み込む。

1. `prelisting_gate_eligible_sg_resolver.csv`（Expansion入口なら対応するSG eligible CSV）。
2. `candidate.csv`、`product_text.csv`、`raw_images.json`。

元の全商品一覧はOwnerが確認した最新SG CSVとそのSHAをGit外で保持する。
ファイル名だけで同名の別CSVを採用しない。入力4ファイルのSHA、Candidateとsidecar、
SG Gateの対象ASINを起動前に照合する。過去のCategory / Brand確認やPH DBは移植しない。
商品・説明・画像の内容一致について全商品の追加人間確認は要求しない。
画像処理は国別root設定による武器疑義の確認に限定する。

起動後はcatalogの明示取得、Category候補の確認、Brand / No Brand確認、
必要な武器画像検査、準備CSV / TXTの出力を行う。Seller Centerの属性・発送条件は手動確認する。
起動・再描画だけではAPIを呼ばない。費用枠0ではAI機能を実行しない。

## 固定コードと永続API枠

設定はschema_version=1、marketplace=SG、port=8502を必須にし、次を持つ。

| 設定 | 用途 |
| --- | --- |
| release_commit / repository_path | origin/mainへ採用済みで、変更のない固定コード |
| python_path | 既存のPython環境 |
| grant_path | 明示承認済みのSG shop・商品・取得数・OpenAI費用枠 |
| api_env_path / google_credentials_path | 既存設定の参照先。秘密値を含めない |
| data_root | コード外のSG専用DB・消費記録・claim・起動記録・private log |
| inputs_dir / gate_filename / input_sha256 | 初期資料4ファイルの対応とSHA |

1枠最大3商品・OpenAI上限1米ドルを維持する。Shopeeのcatalog、Brandページ、属性も
枠に記録した上限を送信前に計上する。失敗・再起動・コード更新で予算を戻さない。
同じ取得枠は永続claimで一つのDBへ結合する。新しいDBへ同じ枠を移して使い直せない。
消費記録・claim・DBの欠落や不一致は停止し、再初期化で復旧しない。
枠を追加する場合は、Ownerの新しい対象・取得数・費用承認を新しいgrantへ記録する。
設定ファイルを作成しただけではAPI実行の承認にならない。

## 設置・確認・停止

Codexは正式採用済みreleaseの専用checkout、初期資料、設定、未使用の承認枠を整え、
次を順に実行する。採用前のbranchを正式releaseとして設定しない。

```powershell
.\scripts\Start-SGBeta.ps1 -CheckOnly
.\scripts\Install-SGBetaShortcut.ps1 -CheckOnly
.\scripts\Install-SGBetaShortcut.ps1
.\scripts\Start-SGBeta.ps1
```

CheckOnlyはDB初期化・API実行をしない。初期設定・固定コード・資料照合が不成立なら起動を止める。
ショートカット起動で失敗した場合はメッセージを表示し、別のコードやPHへ切り替えない。
同じ設定のSG serverが動いている場合はその画面を開く。別processが8502を使っていれば停止する。

```powershell
.\scripts\Stop-SGBeta.ps1
```

停止は記録したSG processの起動時刻・コマンド・portを照合して行う。PH processを止めない。
利用を戻す場合はSGを停止して専用ショートカットを外し、承認済み旧releaseへの設定変更を検証する。
DB・過去grant・消費記録・claimは保持する。永続データを削除して予算を復元しない。
SG Stateの停止・変更は正式な承認手順で行う。MY / THの市場利用を有効化しない。
固定releaseは自動更新しない。正式Stateや規則を変更した場合は、SGを停止して
変更を含む採用済みreleaseへ利用設定を更新する。別checkoutの変更だけでは稼働中SGへ反映されない。
