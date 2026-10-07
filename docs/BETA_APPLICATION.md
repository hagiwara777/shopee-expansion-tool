# PH / SG統一ベータ

普段の入口は `Shopee Beta` とし、1つのアプリ内で画面上部の「対象国」をPH / SGへ切り替える。
入口は `app_beta.py`。候補生成、出品前保安ゲート、Category Mapperの既存処理を再利用する。
MY / THは選択肢に含めず、市場runtimeの開始後に別scopeで追加する。

## 操作と国別情報

両国とも「ASIN Expansion」「ASIN Resolver」「出品前保安ゲート」「Category Mapper」の4工程を表示する。
候補生成は市場に依存しない。GateとMapperには上部で選択した国だけを渡し、工程内で国を再選択しない。
SG Mapperは専用ベータのAI候補・Brand確認・武器画像検査・手動準備CSV / TXTの処理へ接続する。
SG設定が欠落・不正ならSG Mapperを停止し、旧offline画面へ自動切替しない。

国を切り替えると未保存の入力、アップロード、表示中の候補・準備出力、一時tokenをクリアする。
SG runtimeを閉じて専用lockを解放し、国を戻したときは同じgrant / DB / claim / ledgerから再開する。
保存済みの確認を別国へコピーせず、再利用時は既存の現行catalog / 商品資料の照合を行う。
SG作業の再開後は最新catalogを明示取得する。切替・起動・再描画だけではAPIを呼ばない。

## 保存先・設定

PHのCategory / Brand DBは従来のuser-local保存先を使う。
PHのKeepa cacheとResolver Evidenceは既存PH保存rootをpathで指定して再利用する。
既存PH API設定はpathで参照し、共通processの環境変数へコピーしない。
SGの専用DB・grant・消費記録・claim・Bridge参照は[既存SG環境](SG_BETA_ENVIRONMENT.md)のまま保持する。
DB移行、過去確認の複製、credential書換え、新規API枠作成は行わない。

起動設定は `%LOCALAPPDATA%\ShopeeExpansionTool\Beta\deployment.json`。
schema_version=1と下記9項目を使用する。

| 項目 | 用途 |
| --- | --- |
| schema_version | 1 |
| repository_path / release_commit | 採用済みの固定共通コード |
| python_path | 既存Python環境 |
| sg_config_path | 既存SG専用環境の設定ファイル |
| ph_runtime_root / ph_api_env_path | PHの既存cache・Evidence保存先と既存API設定 |
| server_data_root | 国別データと重ならない共通server起動記録・private log |
| port | 8503（旧PH8501・SG8502の起動記録を上書きしない） |

共通設定とSG設定のコードcommit・Pythonを照合し、従来のSG preflightを再利用する。
コード変更中・未採用release・SG入力SHA不一致・保存先の重複・PH cache欠落では起動しない。
共通serverの停止は実際のlistener・コマンド・起動時刻を照合し、既存PH / SG serverを終了しない。

```powershell
.\scripts\Start-Beta.ps1 -CheckOnly
.\scripts\Install-BetaShortcut.ps1 -CheckOnly
.\scripts\Install-BetaShortcut.ps1
.\scripts\Start-Beta.ps1
.\scripts\Stop-Beta.ps1
```

設置はformal main採用後に行い、SGの固定release設定も同じ採用済みcommitへ合わせる。
専用SG serverで作業中なら、既存SG停止scriptで本人のserverだけを停止してから共通入口へ移る。
旧PH / SGショートカットを無断上書き・削除せず、復旧用として保持する。
普段は共通の1つを使い、同じSG取得枠を複数の画面で同時利用しない。

SGの少量商品・API取得枠・OpenAI上限1米ドル、Safety / Battery / SLS停止、人間Category / Brand確認、
武器画像用途、Seller Center手動属性・発送条件確認を維持する。
合成UIテストと、端末設置・実API・実務受入は別の確認である。
コード採用と環境反映の結果はrepo外Task Context / Git外Evidenceへ記録する。
復旧は共通serverのみ停止して旧入口へ戻す。DB・grant・消費記録・claimを削除しない。
