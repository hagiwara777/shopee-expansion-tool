# P5 live接続・商品資料更新・保存設計

DEC-0146。P5最小offline実装の設計・検証契約であり、live実行許可ではない。
[既存offline契約](P5_CONNECTION.md)、[実施承認票](P5_ACCEPTANCE_EXECUTION_PLAN.md)、
[P1](PREPARATION_VALIDITY_P1.md)／[P2](PERSISTENCE_P2.md)を再利用する。
実装、formal採用、保存先設置・固定release反映、実API・有料通信、実商品受入は別の承認境界とする。
新規設置の更新対応formatだけで、同じ固定selectionの資料世代を更新する。
旧ledger・旧固定ASIN modeの資料変更停止とdigestは維持し、自動移行しない。

### offline実装の接続点

- `p5_live_adapter.P5TrustedAdapter`は注入されたtrusted operatorの原承認照合・現在観測・参照解決を組成する。
  開始・操作・出力で再照合し、市場別固定配賦と全体上限を検査する。合成authorityはoffline permitを使う。
  productionの承認record loader・Windows設置inspectorは既定提供しない。
  DEC-0147のcode観測・承認済みShopee/Google参照resolverを明示注入できるが、原承認provider・
  端末process観測・実credential参照・設置への結合は未成立。詳細はP5_CONNECTIONを参照する。
  標準`--p5-config`から実行permitは作られず、PRIMARY_SOURCE_UNVERIFIEDのlive停止を維持する。
- `p5_material_updates`は元P5Ledgerへversion 1の`material_updates`を追記するP5専用部品。
  BEGIN→P2失効→INVALIDATED→取得→VALIDATED→P2 commit→COMMITTEDと進める。
  旧batch/selectionを保持し、P2のsource marker・世代・採用revisionと履歴を照合する。
  未完了intentは再起動でも停止し、自動復旧・再送・自動commit・返金を行わない。
  受信済みrowsは比較失敗時も保持する。変更したResolverには旧新Fact digest付きの新しい人間比較が必要。
- `p5_transport`の`fresh_selected_products`は更新intentの対象だけを、cache読取りを回避して取得する。
  通常の7日cacheと元ledgerの有限予約を維持し、Candidate15列とSafety資料を既存生成器で再結合する。
  固定時のF1/F2条件は同batchへ保持し、新世代の条件外・未確認商品はpoolへ進めない。
- `p5_setup`はvolume/alias/ACL/容量の観測契約、明示排他初期化、SQLite backupとmanifest、隔離復旧を扱う。
  実store IDの生成後にscopeを確定する。合成inspectorのPASSを実端末のACL/probe成功とは扱わない。
  trusted組成の運用出力・資料更新にはcheckpoint hookを必要とし、未結合なら停止する。
  復旧は旧scope/claim・UNKNOWNを保持する読取用コピーであり、live再開許可を返さない。
- `p5_ui`は更新対象・最大追加token・確認者・理由・再確認を表示する。描画だけで取得しない。
  crash/不整合は保存済みjournal・応答・消費・P2履歴のoffline照合へ止める。自動修復UIは設けない。

## 1. 保存契約

P5新規データはD固定ドライブを第一候補とする。正確な絶対path・volume identity・実shop対応は
非公開実施票へ固定し、共有文書では`P5_DATA_ROOT`を用いる。
`P5Scope.root = P5_DATA_ROOT`とし、run-idをrootにも重ねて指定しない。

```text
P5_DATA_ROOT/<run-id>/
  PH/<shop-id>/
    work.sqlite3        # P2、1市場・1shop・固有store ID
    keepa.sqlite3       # このscope専用。PH/SGで共有しない
    ledger.json         # 全API予約、実測、探索、固定selection、資料更新履歴
    claim.json          # 元scope digest。更新時も変更しない
    inputs/             # 原CSV、商品資料世代。上書きせず参照・SHAを保存
    evidence/           # sanitized観測・承認票・操作記録
    exports/            # session・商品revision・資料世代付きCSV/TXT
    backups/<checkpoint-id>/
  SG/<shop-id>/         # 同構成、別scope/credential参照/有限枠
```

SQLiteのjournal/WAL/SHM、ledgerのatomic replace用一時ファイル、process leaseも同じshopディレクトリに置く。
tempを同volumeに置き、volumeを跨ぐrenameでatomic性を仮定しない。秘密・token・画像本体/base64は保存しない。
画像は既存のメモリ限定契約を維持し、必要な参照・検査bindingだけを保持する。
最初は各市場1shop。同市場複数shopのUI切替・Bridge拡張は追加しない。
全ショップCSVは準備対象shop以外も含む当該市場全件を要求し、保存分離を重複照合の省略理由にしない。

### 設置前と設置時の検査

read-only調査ではDはFixed/NTFS、候補の親・P5ディレクトリは未作成だった。
D直下はAuthenticated Users等へ広い権限を持つため、継承したままの運用採用は不可。
観測日時・空きbytes・ACL原観測・存在検査はGit外Evidenceへ置く。read-only ACL確認は書込み成功の証明ではない。

別承認の設置では、次をすべて満たしてから新規ファイルを排他的に作る。

1. 固定NTFSとvolume identityを再確認し、全祖先のreparse point/junction/symlink、UNC、SUBST等の別名を拒否する。
   canonical pathとvolume/file identityで、既存Git/worktree/.venv/SQLite/cache/outputs/ledger/claim、
   他run・他市場・他shopとの同一・包含・alias重複を検査する。計画どおりの同shop内`backups/`は許容するが、
   backupファイルと稼働ファイルの同一identityや、他保存先へ抜けるaliasを拒否する。文字列prefixだけで判定しない。
2. 実行ユーザー、SYSTEM、管理者に限定した専用ACLを明示設定し、親の広い継承を除く。
   共有データ利用者が必要なら実名主体と権限をOwner票へ追加する。Everyone等の広い書込みを許可しない。
   credential参照先をこのrootへコピーしない。
3. 承認済み新規隔離probeでcreate/read/fsync/同directory rename/排他lock/SQLite transactionを検査する。
   probeの作成・処置も設置承認内で行う。今回probe・フォルダ・実運用DBを作成しない。
4. 設置承認後にP2を作成し、実store IDを観測して非公開票へ結合し最終scopeを確定する。
   permit注入はその後の具体票に対する別の実行承認後だけとする。
   `BetaWorkStore.create`はstore IDを内部生成するため、仮IDの事前埋込みで一致を装わない。
   API権限はまだ注入せず、cache/claim/ledgerを新規排他作成して整合を検査する。
   途中作成失敗は残存物を保持して停止。自動再初期化・既存DB複製・移行はしない。

現在の実保存先候補と既存C上の作業領域は場所が分かれるが、最終的なalias非重複と
専用ACL・書込み・lockは設置前後の検査が必要。Dの採用はこの条件付きで可能とする。

### backup・復旧・容量

- session終了・対象資料更新前・出力操作前をcheckpointとする。全writer/API送信を停止し、
  P2とcacheをSQLite backup APIで整合的に複製する。ledger/claim、資料世代、scope、保存revision、
  events/copy_operations/copy_locks件数、schema/store ID、市場/shop、各SHA、累積予約/actualをmanifestへ保存する。
  実行中DB本体だけの単純コピーはしない。未確定API予約・更新intent・UNKNOWNをそのまま記録する。
- 同じD上のbackupは論理破損対策でありD故障対策ではない。初回にこの限界をOwnerへ明示し、
  独立媒体/別volume backupがなければその未実施を記録する。Cへの大量backupを既定にしない。
  独立backup先の追加はpath・ACL・保存範囲を別承認する。
- 復旧は新規隔離コピーでintegrity_check、manifest/SHA、履歴連続性、商品/予約/lock件数を検査する。
  旧本体を上書きしない。scope/claimを新runへ作り替えず、旧runのlive再開は停止したままにする。
  同pathの本体交換が必要なら別の明示復旧承認を要する。別pathの復旧コピーから通信はしない。
- 古いledger/claimへ戻して枠を増やさない。最新予約記録と外部実測に不明があれば残枠0扱いで停止し、
  PENDING/UNKNOWNは外部結果の明示解決まで保持する。checksumは悪意ある全体巻戻しを防ぐ署名ではない。
- 初回の内部運用値はD残空き20 GiB未満で警告、10 GiB未満で新送信/新出力を停止とする。
  D空きはさらに、次操作の最大書込み見積＋整合backup＋一時複製を含む必要量を上回ることを要求する。
  run合計5 GiBで警告、10 GiBで停止する少量受入用上限とし、超過時に自動削除しない。
  計測不能、容量不足、fsync/rename/backup失敗は停止。保留・UNKNOWNの観測と履歴参照は残す。
  起動前・各送信前・資料更新/backup/出力前に再計測し、Cも2 GiB未満なら新作業を停止する。
  これらは端末保護値で、C01〜C12/F1/F2に新しいBeta MUSTを追加するものではない。
  大量pytestはD上の別の新規テスト領域を別途確認して計画する。P5運用rootをpytest tempに使わない。

## 2. trusted live adapterの最小境界

追加対象はP5専用のcomposition adapter一つとする。汎用認証基盤・新署名基盤は作らない。
標準`--p5-config`、JSON、環境変数、UI checkbox、`authorization_ref`文字列だけからpermitを発行しない。
UIは取得等の意図を渡すだけで、認可主体にはならない。

### 許可元と照合

trusted起動担当が、現在の具体的実施票に対するOwnerの明示原文・日時・許可操作・期限/終了条件を
確認したrepo外承認recordを読み、検査結果をメモリ内の実行権限として注入する。
recordは今回の設計で作成する空欄票とは別であり、record存在・APPROVED自己申告だけを承認証明にしない。
現在のGitHub actor/承認搬送も独立したhuman-origin proofではない既存Trustモデルの限界を維持する。
同じOSユーザーが任意Pythonを書換える攻撃への隔離保証は追加しない。Owner承認確認を担当するtrusted operatorと
runtimeの境界であり、Python objectそのものを人間承認の暗号学的証明と称さない。

起動担当は次を完全一致で検査し、不一致・欠損・期限切れ・撤回判明時はpermitを注入しない。

| 結合項目 | 必須照合 |
|---|---|
| 実施対象 | repository identity、Owner参照、票version/digest、run、PH/SG、shop、操作allowlist、終了条件 |
| コード実体 | formal採用済み固定releaseのfull commit、実行コードtree/対象ソースdigest、実起動entrypoint・端末識別・loopback port。設定に書いたrelease値の単純返却は禁止 |
| 保存 | canonical root/volume/ACL、store ID/schema、市場/shop、cache/ledger/claim identity、元scope digest、更新方式version |
| 商品と資料 | immutable seed/Finder query/Resolver入力、固定selectionと履歴、更新対象ASIN部分集合、leaf、全shop manifest、一次仕様参照 |
| 認証 | credential参照名と対応市場/expected shop、Bridge参照・A:C読取、Google認証方式。秘密本文は許可票に含めない |
| 予算 | 市場別requests/要求商品数/Keepa tokens/OpenAI USD/画像/Bridge/auth枠、操作別回数、再取得分、累積ledgerとの残枠一致 |
| 出口 | read-only取得、資料更新、P2保存、準備CSV/TXTを操作別に許可。外部投入・実出品は初回0、AUTO_RULE permitは注入しない |

PH/SGの上限を固定分配し、その和を全体上限以下にする。残枠の市場間融通はしない。
各scopeの永続ledgerを真実とし、UI残数を信頼しない。片市場停止で他市場の予算を再配賦しない。
全体を共有する新ledgerは不要。複数processでも二重openを既存leaseで拒否する。

### 生成・実行の順序

1. importは副作用なし。config表示・初期描画は非秘密設定の読取だけとし、通信・実DB/ledger初期化を行わない。
   明示startで承認/一次仕様/release/保存先を確認する。
2. 許可後だけ承認済み参照からcredentialを解決する。既存`P5Secrets`をメモリに注入し、
   `from_environment`/ADC/legacy tokenへのsilent fallback、secret書込み・移動を追加しない。
3. `P5Runtime`、`make_keepa_client`、`make_catalog_client`、画像provider等を既存bounded transportで構成する。
   liveはdefault transportのみ。fake/replayを公式に昇格しない。
4. Shopeeの各明示API操作の直前に、有限auth/Bridge枠を確認して最新tokenをread-only取得し、expected shopを再照合する。
   strict Brandは各物理pageをShopee予約へ、各page前のBridge読取も別枠へ計上する。取得失敗後に再送しない。
   MapperはShopee refreshを行わない。現在は手動Bridge更新部品だけなのでこの順序の接続が必要。
5. 各物理send前に操作の許可、実行コード/target、scope/claim、対象/leaf、計画、残枠、容量を再検査し永続予約する。
   自動retry/redirect/fallback/自動購入は0。timeout・不明消費・actual超過で予約を保持して停止する。
   不許可操作は残枠があっても0 send。再描画・フィルター変更・市場切替だけでは送信しない。
6. P1現在根拠→P2 transaction commit前→bytes返却前に、許可・資料世代・保存revision・SG正式gateを再照合する。
   permitは同process/session内だけで使い、再起動時に承認・期限・元ledgerを再検査する。新枠を作らない。

一次資料はCategory/Brand/Attributeの現行本文・版/取得日・対象App/shop権限・全件/paging・rate制限・
request/responseを確認した記録を必要とする。参照URLが3つあるだけでは不足。
Attributeの`category_id_list`とサンプルの`category_ids`、値の配列/文字列形式の不一致は
公式本文の照合で解消するまで`PRIMARY_SOURCE_UNVERIFIED`。試しのlive送信で解消しない。
DEC-0147では自動Attribute取得を商品準備の必須前提にしない方針を保持するが、上のlive停止は解除しない。
現production adapterはAttribute操作を明示拒否する。NOT_FETCHED/FAILED/FETCHED空とSeller Center最終確認を
区別し、この方針をP5運用許可やBeta完成条件の変更に読み替えない。

## 3. 再取得時の商品資料世代

固定するものはscope/claim、seedと検索条件、Resolver source_id/input_title/origin、選択ASIN集合、
選択者/選択理由/旧同一性確認、予算・消費・P2操作履歴・出品進行/lockである。
更新できるものは**既選択ASINの現在の商品資料**だけ。Finder再検索、未選択ASIN追加、
ASIN差替え、source_id付替え、新scope/ledgerでの枠復活は拒否する。

旧batch/selectionは上書きしない。同じledger内へversion付き`material_updates`を追加し、
元selection/batch digest、対象ASIN、parent/current generation、旧新資料SHA、送信予約ID、
P2の期待/結果revision、session、失効理由、操作者を結合する。
旧ledgerでこの欄がない場合の固定再搬送は従来どおり。更新機能への自動変換はしない。
新規P5設置時だけ更新対応formatを選び、旧runで更新が必要なら別の明示移行設計まで停止する。
既存P5Scope.digest・固定ASIN modeの形式は変更しない。

### 更新transactionの手順とcrash停止

ledgerとP2 SQLiteには分散transactionがないため、次のwrite-ahead intentでfail closedにする。

1. 対象部分集合・現在世代・P2 revision・許可された再取得回数と予算を表示して明示実行する。
   対象にPENDING/UNKNOWN投入lockがあれば取得前に停止し、先に既存復旧手順で明示解決する。
2. 元ledgerのlease下で`BEGIN`更新intentをfsync/atomic保存し、sessionの対象Fact/確認/出力を先に失効する。
   P2にも一transactionで対象の準備失効とintent ID・世代を履歴追記する。
   双方の無効化成功前にはAPI送信しない。保存失敗は旧readyへ戻さず停止する。
3. 送信前予約→P5 bounded Product取得。7日cacheの通常契約は維持し、cacheの削除や時刻偽装はしない。
   fresh再取得が必要ならP5明示操作内だけでcache readを回避する最小経路を追加する。
   cache hit再搬送と実API再取得を区別し、hitをF08 live成功へ扱わない。offers/強制updateは送らない。
4. 応答ASIN/domain=5・項目別OWN_PRODUCT出所、件数、完全性、時刻・tokensConsumedを検証する。
   選択集合からの差替え・欠損・他商品・不明消費は停止し、予約を返さない。
5. 固定selectionの該当部分集合からCandidate15列と全Safety sidecarを一式再生成し、最終bytes SHAとASIN集合を結合する。
   部分失敗では対象更新全体を採用しない。旧資料は履歴に保持し、現資料として戻さない。
6. `VALIDATED`世代をledgerへ保存→P2へ新資料/失効/要再確認を期待revision付き全件transactionで保存→
   ledgerの`COMMITTED`とP2結果revisionを保存する。両方一致後だけ新世代をcurrent候補にする。
   取得成功だけでreadyにしない。Safety・全shop・必要な同一性・Category→Brand確認を経る。
7. 全起動/保存/出力境界は、未完了intent、世代/parent/SHA/P2 revision不整合を拒否する。
   `BEGIN`後・send後・P2 commit後・最終ledger保存前のどのcrashでも旧/新bytesを返さない。
   自動再送・自動commit・intent消去はしない。保存済み応答/予約/P2履歴のoffline照合と明示復旧を要する。
   外部結果が不明ならUNKNOWNのまま停止する。API消費記録のrollbackで復旧しない。

### 失効と再確認

| 変更・操作 | 失効対象と再要求 |
|---|---|
| 対象商品再取得開始（同一内容を含む） | 対象旧ready/出力/Category/Brand確認を失効。旧記録は候補・履歴だけ。新世代にHUMAN Category→Brandを再要求 |
| title/brand/型番/仕様/同梱/文章変更 | 対象Safety、分類、必要画像/SG本体確認bindingを失効し既存validatorで再判定。Resolver同一性の現在有効性も失効し、旧sourceとの人間比較を再要求。旧CONFIRMEDを削除しない |
| 価格/評価/取得時刻だけ変更 | F1/F2を再判定し旧一致出力を失効。意味上同一商品ならResolver旧同一性を履歴根拠にできるが、新世代の内容比較結果を記録。上のCategory/Brand再確認は省略しない |
| Category一覧の更新開始/変更/失敗 | 当該sessionのcatalog receipt、Category確認、全従属Brand/Attribute/許可を失効。公式完全取得後にCategory→Brandを再確認 |
| Brand更新/失敗 | 同leafのBrand receipt/確認を失効。Categoryの有効性は別に検査し、Brand未発見をNo Brandにしない |
| 属性更新/空tree/失敗 | leafの属性観測と関連出力を失効。FETCHED空とNOT_FETCHED/FAILEDを区別。Seller Center必須入力0件を推定しない |
| 全shop CSV更新/欠落 | 当該市場の重複判定/準備出力を失効し全shop資料を再要求。CSV不在でLISTEDを巻き戻さない |
| 市場/shop切替・再起動 | 新session、旧ready/公式receipt/確認を復元しない。固定selection・累積消費・P2履歴とlockを維持 |
| 無関係な別商品の追加/更新成功 | 非対象商品の同session有効根拠を維持。共有catalog/全shop資料の更新ならその影響範囲を適用 |

Safety BLOCK/REVIEW/EXCLUDE、manual_exclude/body_excluded、Battery/SLSを更新・分類メモで解除しない。
画像対象外/NO_SIGNALへ全商品の説明・画像人間確認を再導入しない。必要な疑義だけ従来契約で確認する。
フィルター条件外・未確認となっても固定selectionを置換せず、その商品を準備poolから外す。
固定24時間TTLや自動定期更新は追加しない。初回は3つの明示sessionと操作別再取得計画で鮮度を扱い、
長時間放置・資料更新が必要なら出力を止めて明示再確認する。cache7日を公式Brandの有効期間へ流用しない。

## 4. 実API前の最小実装差分とoffline合格条件

| 差分 | 対象候補・受入条件 |
|---|---|
| trusted composition | 新`modules/p5_live_adapter.py`と既存P5起動部品への明示注入。承認照合・実コード観測・credential参照解決のfake interfaceで検証。UI/JSON/env単独では開始不可 |
| 設置preflight | P5専用新規setup。volume/path/ACL/非重複/空き/backup検査、排他初期化・store ID観測→scope/claim。constructorで作成しない |
| 商品資料更新 | `p5_candidates.py`の旧selectionを残し、version付き更新journalと現世代検査。`p5_runtime.py`で失効/世代/P2整合を検査。旧modeのdigest/固定再搬送は維持 |
| 明示fresh取得 | P5内に限るselected Product取得、`p5_transport.py`の既存予約/実測を再利用。cache read回避と通常取得を分離し、全sendは同じ元ledgerへ計上 |
| P2/UI接続 | 既存`ClassificationWorkflow`/`BetaWorkBench`の失効・履歴・revisionを再利用し、必要なP5 intent/generation検査だけ追加。`p5_ui.py`に対象差分・追加枠・再確認・復旧理由を表示。新汎用Workflowなし |

現行P5には送信前token予約/actual記録、strict公式取得、P1/P2出力が既にある。これらを重複再実装しない。
必要な差分はtrusted組成、設置の安全検査、選択後更新、Bridge前置、明示fresh経路とその接続に限定する。
T01〜T08は既存P1〜P4・有限transport・storeの保護を再利用した最小差分の検証条件であり、
新しい汎用認証/監査/backup製品やBeta完成条件の追加要求ではない。

| offline試験 | 必須期待値（PH/SG双方、合成データ・通信禁止） |
|---|---|
| T01 許可 | 票/Owner参照/期限/撤回/operation/scope/shop/credential/release/実コード/target/保存不一致は開始・send・出力拒否。文字列だけの偽許可も拒否 |
| T02 予算 | 両市場合算以下の固定配賦、物理send毎予約、Bridge/auth/page/画像再取得も計上。timeout/部分応答/actual欠損/超過・別client・再起動で返金0、retry0 |
| T03 選択 | 更新対象は既選択部分集合だけ。Finder再検索・未選択追加・source_id/ASIN差替え・新ledger逃避を拒否。旧batch/selection/scope digest不変 |
| T04 更新失効 | 同内容再取得、文章/brand/root/価格/評価/同梱の変更ごとに上表を確認。A更新で無関係Bを失わず、Resolver同一性UNKNOWN/MISMATCHは停止 |
| T05 crash/並行 | 上の各永続化境界の保存失敗・終了、二重更新、旧revision、欠損journal/lockを注入。半端な世代でready/bytesなし、消費/履歴/UNKNOWN維持、再送なし |
| T06 保存/復旧 | 新規限定・alias/ACL/容量不明の拒否、DB/cache/ledger/claim非重複、部分初期化停止、整合backupから隔離復旧。古いbackupの予算復活拒否 |
| T07 根拠/画面 | strict全件/10page上限、Attribute未取得/空/失敗、mock公式昇格拒否、更新表示・再描画0send、HUMAN→Brand、P1/P2 commit前/bytes前再検証 |
| T08 保護 | P5既存tests、P1〜P4/F1/F2、Candidate15列/Safety SHA、PH/SG protected、UNKNOWN/5状態、旧scope/旧DB/既存入口不変 |

実装後は必要な対象pytest、mandatory全offline・PS5.1/7・protectedとreviewを現在対象へbindする。
大量suiteはD上の新規隔離テスト領域の確認後に実施し、ログ/bytesの上限を設ける。
テスト合格は実API・公式資料現行性・F08 live・C12・Owner受入の代替にしない。
HUMAN初回ではC04限定AUTO_RULEの実務成立を未達として残す。実出品・外部ツール投入は0。

## 5. 次の単一作業と停止

次の単一作業は、非公開実行票の未結合項目と一次仕様・trusted operator実装・設置検査を照合し、
設置・credential参照利用・liveへの具体的な別承認を成立させること。offline成功だけで実行へ進まない。
実対象、一次資料、現在価格、Google auth有限回数、release、ACL/probe/backupが未確認なら実行票はBLOCKED。
shop・ジャンル・seed・既出品状況・Resolver URLのOwner原指示は、非公開票で指定と参照を回収し、
最新資料/SHA/同一性・認証との実行Evidence結合と分ける。指定済みでも実行承認やcurrent証明にはならない。
非公開票の未結合はこの最小offline実装のblockerとしないが、live前には必要な全結合を要求する。
空欄を過去SG枠・推測ASIN・fixture・便宜的Categoryで埋めない。具体的票とtechnical gatesが揃ってから
Ownerへ該当操作だけの実行承認を求める。詳細の記入欄・停止条件は実施承認票を参照する。
