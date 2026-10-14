# SG通常継続利用

共通実務Betaの完成条件は[DEC-0137の設計](PRACTICAL_BETA_COMPLETION.md)を参照する。
本書の少量2商品群計画は維持し、[PH・SG受入計画](PH_SG_BETA_ACCEPTANCE_PLAN.md)の保存・再起動・追加・失効・状態管理と合わせて実施する。
通常継続利用のコードや旧受入を、新共通操作の実務受入と同一視しない。

DEC-0134の方式。`app_beta.py`のSGを同じ4工程で使い、新商品群ごとのCodex設定変更を不要にする。
コード採用、8503への反映、API実行、実商品受入は別の境界である。

## オーナーの操作

1. 対象国SGを選び、Mapperで「SGの作業を開始」。再起動・国切替後は最新Categoryを明示取得する。
2. 共通Expansion／Resolverで候補を取得し、最新の全ショップ既出品資料で通常SG Gateを実行する。
3. Mapperへ正式SG ELIGIBLE CSVの全件と、元Candidate・成分Safety・商品文章・未評価画像を読み込む。
   本体疑義がある付属品は、同じCandidate・商品文章へ結合したSG本体確認記録も必要。
   「確認資料を読み込む」→「Category確認を開始」。4件以上を選別・切抜きする必要はない。
4. 今回の商品情報と現在のSG catalogを見てCategoryを採用する。以前の保存値は候補に限る。
   対象CategoryのBrandを完全取得し、商品ごとにBrand／No Brandを明示確認する。
5. 武器画像の対象判定と必要な検査・人間判断を行う。Safety／Battery／SLSの停止は解除しない。
6. 完成した商品だけのCSV／TXTを取得する。未確認商品は残せる。
7. 次の商品群のGateと関連資料を同じアップロード欄へ差し替え、3から繰り返す。

資料変更・削除・読込失敗ではCategory／Brand確認・画像評価／判断・AI候補・属性・出力・checkboxを失効する。
同一資料の再描画では今回の状態を保つ。同一ASINでも情報変更時は確認を継承しない。
新商品群でCategory一覧は現在runtimeの取得成功分を利用できる。Brandは商品群ごとに完全取得を要する。
再起動・国切替後は保存時刻だけでcurrentへ戻さない。再確認は保存済み記録を削除する操作ではない。

準備CSVのTRUEは手動準備対象。Seller Center必須属性・商品固有の発送条件の確認、入力、出品は人間が行う。
未取得属性を0件・入力完了として扱わない。全商品安全保証、自動出品、画像AI精度保証は含まない。

## 一度だけ整える承認・保存設定

通常利用は新しい`SGContinuousPolicy`へ結合する。旧`SGLiveRunGrant`を拡大・リセットしない。
商品のASINと資料SHAは毎回の受付で検証し、通常利用の起動設定へ埋め込まない。
承認単位で専用DBは1つ。商品群ごとのDB、認証系列、Grant作成は不要。
旧GrantのDB・ledger・claim、PH保存先と認証は保持し、過去確認を移植しない。

Policyは以下の項目だけを持つ。shop・Bridge・各上限・承認参照は別承認時に具体化する。
設定ファイル／authorization_ref自体はOwner承認の証明にならない。

|項目|契約|
|---|---|
|operation_id|一つの承認単位。再使用・保存先移動・Policy変更で枠を復活させない|
|shop_id / bridge_spreadsheet_id|既存のSG shopとBridgeへ照合。Mapper refreshなし|
|catalog_request_limit / attribute_request_limit|累積0～10,000回。不要APIは0|
|brand_total_page_limit|商品群・Categoryをまたぐ累積0～10,000ページ|
|brand_page_limit|1取得最大1～50ページ。完全取得不能ならcurrentにしない|
|keepa_request_limit|累積0～10,000 HTTP送信。429・失敗後の自動retry、redirectなし|
|openai_limit_usd|Ownerが別承認で指定する有限額。0可。既存の保守的予約方式を使い、失敗・timeoutを返却しない|
|authorization_ref|具体的なOwner承認の参照|

これらは実用推奨値ではなく実装上限。実行承認では必要量・契約・費用を個別に確認する。
Keepa送信数と画面の推定tokenは金額・実token上限ではない。Keepa費用全体の厳密上限は保証しない。
旧限定Grantの1 USD上限を通常Policyへ二重適用しない。OpenAI枠0でも画像対象商品は検査なしで進めない。
未知モデル・未対応requestは拒否する。通常予算の追加・更新も別承認であり、自動補充しない。
SDKの候補検索・商品解析は共通で、SG通常利用時だけ同じ送信を有限記録で保護する。
PHの既存候補生成経路、旧SG限定検証には新budgetを自動適用しない。

別承認後、採用済みコードのCLIで新規専用保存先を一度だけ初期化する。CLIはAPIを呼ばない。
claimはコード外の`%LOCALAPPDATA%/ShopeeSG/continuous-claims`へ保存される。

```powershell
python -m modules.sg_continuous_runtime --policy <承認済みpolicy.json> --run-path <SG専用data_root/continuous> --initialize
```

初期化失敗もclaimを保持して停止する。claim／ledger／DBの削除、手編集、復元不明の再初期化で直さない。
復旧は確認済みbackupとOwner判断で行う。claim／ledgerのchecksumは事故検出であり、悪意ある巻戻しの署名保証ではない。
OS lockにより同じ保存先の2tab／2processの二重送信を防ぐ。送信前に永続化し、永続化失敗なら送信しない。

SG専用deploymentはschema_version=2、mode=continuous。共通Beta deploymentのschema_version=1は維持する。
SG設定は下記11項目を持つ。固定release・clean code・formal main由来・SG ACTIVE・保存先分離を従来どおり検査する。

`schema_version, mode, marketplace, release_commit, repository_path, python_path, policy_path,
api_env_path, google_credentials_path, data_root, port`

SGはmarketplace=SG、port=8502という保存設定契約を維持する。普段の共通serverは8503。
`inputs_dir / input_sha256 / gate_filename / grant_path`はschema_version=2へ入れない。
起動前検査・作業開始は既存記録を照合するだけで、欠落時に初期化しない。
schema_version=1は従来の最大3商品・固定入力SHA・指定Categoryの限定検証。自動mode切替やfallbackはない。

## 候補生成で残す制約

Expansionは1／3／5ページ、1ページ50候補、商品照会batch50件。既存診断fallbackは最大3検索で、
SG通常利用では診断・token照会・SDK内部送信も同じ永続送信枠を消費する。
Resolverは利用者が選択した重複除去後ASINを照会する。自動的な次商品群取得はない。
共通bounded transportは送信失敗後の同じactionを停止し、次の明示actionでも消費を戻さない。

Research CSV adapterはPH／shopee.ph固定の任意補助。SGは既存のタイトル貼付入力でResolverを使えるため、
今回はadapterの市場対応をBeta後改善へ送る。検索本体と操作の市場別複製を避ける。
PH固定30件のEvidence評価は通常利用の完成条件にせず、SG評価をPH実行として保存しない。

## 受入・rollback

offlineは4件と150候補、A→B、同一ASINの情報変更、完成分出力、checkbox失効、失敗・上限・
再起動・並行起動・記録破損・保存失敗、PH・旧SG・Safety回帰を検証する。
synthetic成功は実商品受入やlive接続の代替ではない。

実務受入はDEC-0137の共通P1〜P4を整え、P5で固定release反映・有限API枠／保存先・少量2商品群を別承認する。
現在の8503・秘密情報・実商品を開発中に変更しない。
rollbackは通常利用を停止し、共通入口のSG設定を承認済み旧限定方式へ戻すか、対象codeを通常revertする。
通常利用DB・旧DB・Policy／Grant・ledger・claimを保持し、消費を戻さない。PHの起動・データを維持する。
