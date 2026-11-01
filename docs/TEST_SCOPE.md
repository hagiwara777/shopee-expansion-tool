# 通常テストと保全した旧機能テスト

Owner指示F／DEC-0163により、使わない機能だけを確かめるテストを通常実行から分ける。
商品判定・辞書・安全条件・テストの期待値は変更せず、元のテストと資料をその場所に保全する。

通常実行は以下とする。`pytest.ini`でSora本体の`tests`を対象にし、`conftest.py`が
`tests/test_scopes.json`の明示されたテスト関数だけを通常実行から外す。

```powershell
python -m pytest -q
```

使わない機能だけのテストは、必要なときに別に実行できる。

```powershell
python -m pytest -q --test-scope=retired
python -m pytest -q --test-scope=retired tests/test_sg_beta_process_identity.py
python -m pytest -q --test-scope=all
```

`active`が既定、`retired`が保全した旧機能のみ、`all`が両方である。
パラメータ違いの各ケースは同じ関数の分類に従う。ファイル名のprefixや「P5」等の語で自動除外しない。
未登録・新規のテストは通常実行に残る。選別設定の欠損・不正時は収集を失敗させる。
除外したケースはpytestの`deselected`として表示し、成功・skipとして数えない。

先行適用する廃止指定はP5の受入・trusted起動・実行許可・専用台帳・Windows観測、
Shopee API／token／Google認証／Bridge、Category・Brand ID確定・Category AI・属性、
P2〜P4の実務画面・準備pool・出品状態管理、seed ASINからのExpansion候補収集、画像AI、Evidence Batchである。
これは試験範囲の指定であり、製品コードや画面の削除、環境の再構成・導入、稼働版更新は行わない。
製品の入口・役割の正式整理は別の指示Cで扱う。

Shopee調査CSV取込、Resolver、Keepaの商品取得と資料搬送、保安ゲートの辞書・成分・説明文・電池・
監視ブランドを残す。同じテストが廃止機能とこれらの両方を確認する場合は残す。
共通型や合成入力を使うだけの旧機能テストと、共通の取得結果・判定・安全条件まで確認するテストを区別する。
判断できないものは通常実行に残し、`retained_mixed`／`retained_uncertain`へ理由を記録する。

残した主な混在・判断保留の対象は次のとおり。全関数の選別と理由の正本は同じ設定ファイルである。

|残す対象|理由|
|---|---|
|P4の再起動A群→Resolver B群の結合確認|旧画面操作と通常Resolver・候補資料・Gateの受渡しを同時に確認する。長時間でも残す。|
|P5の候補・SDK・画面の一部|Keepaの取得事実、成分等の世代対応、Resolver同一性、Gateの除外も確認する。|
|P2・P3・SG初期ベータの一部|電池・Safety停止、資料の出所、重複／市場分離を同時に確認する。|
|P5受入rehearsal|Resolverの資料搬送との分離を断定せず、全件残す。|
|P1／準備有効性・出力契約・product review|廃止画面だけでなく共通の現在根拠・Safety・CSV条件も扱い、今回の指定だけで外さない。|
|SG継続取得・beta環境・commerce Keepa adapter|旧機能と共通のKeepa予算・実消費・失敗時停止・cacheが混在する。|
|ExpansionからGateへのhandoff|成分・説明文の同一性と入力変更時の失効も確認する。|
|SLS Categoryの各確認|カテゴリ依存だが既存の輸送・電池・市場分離の安全条件を扱うため残す。|
|画像Fact・画像対象policy・Gateでの扱い|画像AIの通信テストとは分け、現行Gateが読む安全条件は残す。|
|家電ファイル分類・研究replay、Canopy TEST|今回の廃止指定だけでは扱いを確定できないので推測で外さない。|

指示Gの失敗2件は`test_sg_beta_process_identity.py`のパラメータ違いである。
旧ベータの専用起動・停止のWindows観測だけを確かめ、通常app.pyの起動・Resolver・Gate・Keepaを
確かめないため、`retired`へ分類する。待受状態や起動確認コードを修正したものではない。

CIはSora本体を1回実行し、固定版commerce-api-coreのテストを別stepで1回実行する。
`work/ci/commerce-api-core/tests`を通常のSora本体へ混ぜず、時間・件数・成功／失敗／skipを別に数える。
Soraの6つのmandatory checkとPH／SGの保護対象は維持する。

```powershell
python -m pytest -q work/ci/commerce-api-core/tests
```

作業中は変更に関係するテストだけを実行する。最終差分を固めてから統合前の通常全体テストを1回実行する。
途中の無用なpushで全体CIを繰り返し起動しない。失敗した場合は該当原因と関連テストを確認し、
再実行が必要なら理由と最小範囲を報告する。未実行・実行中・除外をPASSへ読み替えない。
全体が実行中なら繰り返し完了確認を続けず作業を区切る。Ownerの連絡または明示依頼された完了通知で結果を確認する。

時間比較は同じ単位で行う。旧#159 CIはSora本体3,851ケース＋共通部品40ケース、
全3,891ケースのうち3,888成功・3skip、pytest部分44分33秒（CIジョブは約46分）だった。
旧mainローカルは3,851ケース、3,845成功・4失敗・2skip、41分11秒だった。
旧#158の約29分は別の版の参考値で、同じケース数の比較としない。
新しい時間・件数はGit外の比較記録とCIの`test-timing`資料へ記録する。
過去のケース時間を足した見積りを、新しい全体実行の実測と扱わない。
