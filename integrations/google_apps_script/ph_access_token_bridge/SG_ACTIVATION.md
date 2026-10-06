# SG自動同期の反映準備

`SgSync.gs`は既存のPH Apps Script projectへ追加する候補コード。
ローカル検証だけでGoogle側へ反映・実行・共有・トリガー作成を許可しない。
対象へのOwner明示承認後に以下を実行する。

## PHを維持する構成

- 元管理シートでのRefresh Token更新責務は既存在庫管理ツールに維持する。
- PHの`Code.gs`、`syncPhAccessToken`、既存5分トリガー、PH Bridgeを変更しない。
- SGは新しい専用Spreadsheetへコピーする。共通read-only Sourceを同じ形式で再利用する。
- 既存Sourceは全行を検証するため、同一BridgeでのSG空欄がPH取得も停止させ得る。
  SGの無効化・更新を別ファイルへ分けてこの影響を避ける。既存BridgeのSG行を編集・削除しない。
- SG専用Bridgeはtab `Bridge`、A1:C1が`marketplace`, `shop_id`, `access_token`。
  2行目はSG、既存SG shop ID、空のtoken。PH / MY / TH行を入れない。
- 共通Sourceのcontract・認証優先順位を変更しない。通常SG runtimeは有効化しない。

## Google側で承認対象となる操作

1. 新しいSG専用Spreadsheetを作成する。トークン値は手動コピーしない。
2. 既存の読み取りService Accountへ、このSG専用ファイルだけのViewer権限を付ける。
   公開共有、Refresh Token / Partner Keyの共有、新規credential作成は行わない。
3. 特定済みの既存PH同期projectへ`SgSync.gs`を別ファイルとして追加する。
   元の`Code.gs`と既存Script Propertiesは保持する。
4. Script Propertiesへ`SG_BRIDGE_SPREADSHEET_ID`と`SG_EXPECTED_SHOP_ID`を追加する。
   SG shop IDは既存のローカル設定へ照合し、Ownerに値の転記を要求しない。
5. `syncSgAccessToken`を一度実行し、SGのshop binding・元表とのtoken一致を
   値を表示・保存せずに確認する。初回同期前の空欄は未稼働として扱う。
6. 一致・既存SourceでのSG読取成功を確認してから`installSgFiveMinuteTrigger`を一度実行する。
   SG用5分トリガーが1件、既存PH用が1件のままであることを確認する。
7. 時間主導のSG自動実行2回とtoken一致・reader bindingを確認する。
   PH自動実行とPH readerも再確認する。Googleの追加権限要求があれば内容を確認して止まる。
8. 新SG Bridgeを既存の隔離検証processだけで指定する。通常設定・通常起動先を変更しない。
   許可済みの最大3商品・OpenAI上限1米ドルの実API検証は別結果として記録する。

この承認対象はGoogle側のSG認証受渡し経路の追加であり、formal main merge、deploy、
SG ACTIVE化、出品準備の正式出口開放、自動出品を含まない。

## 失敗時の扱いと戻し方

同期は元表のB列でSGを一意に検索し、当該行のC / Eだけを読む。DのRefresh Tokenは読まない。
設定済みexpected shop、Bridge shop、元表shopを照合する。別shopへ追随しない。
SG tokenを先に空欄にして読戻し確認し、その後に取得・書込み・一致確認する。
取得・検証・書込みの失敗ではSG tokenを再度空にし、秘密を含まない失敗だけを報告する。
PH / 元表をSG targetとして指定した場合、書込み前に拒否する。PH行を含むtargetも編集しない。

Googleが書込みを全面拒否する場合やlock取得不能では、古いSG tokenの消去を保証できない。
3列contractでは同期時刻やtoken有効期限も独立証明できない。失敗を最新値として扱わず、
回復確認までSG側の利用を停止する。この制約はPHの既存Minimum Betaと同種である。

戻す際はSG用トリガーだけを無効化し、書込み可能ならSG専用Bridgeのtokenを空にする。
SG reader利用を止める。PH project・既存PHトリガー・PH Bridgeは保持する。
追加ファイルとSG用Script Propertiesは不要になった後にOwner管理下で取り除ける。
既存tokenの別Bridgeへのfallbackは行わない。

## ローカル検証

`node --test tests/js/ph_access_token_bridge.test.js tests/js/sg_access_token_bridge.test.js`

PH / SGの取得・照合・失敗・対象分離・トリガー重複拒否を合成データで確認する。
ローカル結果はGoogle側の稼働成功を証明しない。実行結果はGit外Evidenceへ保存する。
