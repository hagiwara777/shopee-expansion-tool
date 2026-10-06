# SGベータ版の採用候補

固定PH Betaと同じく、確認した商品をCategory・BrandごとにCSV / TXTへまとめ、
Seller Centerや既存出品ツールへ手動入力する。自動出品は含めない。
全商品の説明・画像を人間が確認する機能はない。画像の用途は武器疑義のみ。

入口は `app_sg_beta.py`。既存のSG workflow・自動更新Bridge・永続取得記録を再利用する。
通常PH DBやショートカットを変更せず、承認済み対象のSG用DBで確認を保持する。
再起動でAPI枠を戻さず、資料変更・取得失敗・現行ID不一致は古い確認を使用しない。
現在の取得契約は1枠最大3商品・OpenAI上限1米ドル。通常利用の無制限枠へ変更しない。

```powershell
.\scripts\Start-SGCandidate.ps1 -BetaRelease -PythonPath <python.exe> `
  -LiveGrantPath <承認済み取得枠.json> -ApiEnvPath <既存API設定>
```

`-CheckOnly`はimport確認のみ。起動・API実行・正式採用を行わない。
既存の開発入口は再生modeとlisting_ready=FALSEのまま残す。

## 出力条件

- SG Gate ELIGIBLE、現在のSG Categoryと明示Brand / No Brand確認。
- 現在のSLS ALLOW候補と既存の説明Safety / Shared Battery判定。
- 国別設定で対象外なら画像不要。対象商品は武器検査の完了・疑義なし、
  または武器疑義・判断不能に対する根拠付きの人間判断が必要。
- 認証・catalog・画像処理の全体失敗は出力停止。

ベータCSVは準備対象の商品だけにlisting_ready=TRUE、
output_scope=SG_BETA_MANUAL_PREPARATIONを付ける。このTRUEは手動出品準備の対象という意味で、
商品全体の安全保証、Seller Centerの属性入力完了、自動出品許可ではない。
既存のSG Category確認objectは単独でlisting_readyをTRUEにしない。
属性未取得と取得済み0件を区別する。属性取得を新たな自動準備完了条件にはしない。

## 正式採用・反映

正式StateでSG operation ACTIVE、development_policy ALLOWED、既存PH / SG保護capability
ACCEPTEDが成立し、blocking open itemがない場合だけ、ベータ入口と出力を利用できる。
毎回現在のStateを読み、出力生成の前後にも確認する。環境変数・画面checkboxで解除しない。
現在のSG INACTIVEは今回のlocal実装・合成テストで変更しない。

今回の変更をreview可能なGit対象へ確定し、mandatory technical gatesとOwnerの最終承認を経て
正式採用する。StateのACTIVE化・普段の起動先への反映は、対象releaseと戻し方を確定して実施する。
実APIの新規確認は具体的対象・取得数・費用枠への承認を得てから行う。
以前の使い切ったgrantやledgerを再利用・リセットして追加実行しない。
停止時はSG入口を閉じ、SG Stateを承認済みの手順で戻す。通常PH環境と過去の記録を保持する。

ローカル・合成検証は実務受入の代替ではなく、実装候補の完成と正式環境の完成を区別する。
