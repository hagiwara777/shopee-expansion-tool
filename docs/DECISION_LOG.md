# DECISION LOG

この文書は、現在進捗ではなく、再開時に必要となる重要判断を残す追記型ログです。
日常的な件数・進捗は `docs/CURRENT_WORK.md` に記録します。

## 運用規則

- IDは `DEC-0001` の形式で連番にする。
- 既存エントリは原則として上書きしない。判断を変える場合は新しいIDで追記し、
  変更元のIDを参照する。
- 各エントリには日付、背景、決定、理由、影響、再検討条件を記録する。
- 会話全文、商品データ、秘密情報、日常的な進捗は記録しない。

## DEC-0001 — 管理文書の役割分担と優先順位

- 日付: 2026-07-26
- 背景: 会話コンテキストが失われても、正式な事実と作業手順を区別して再開する必要がある。
- 決定: Gitのコミット・ref、`AGENTS.md`、`CURRENT_WORK.md`、`DECISION_LOG.md`、
  `PROJECT_ROADMAP.md`、`README.md`、将来のsnapshot、テスト結果の順で役割を分ける。
- 理由: 同じ情報を複数の文書へ詳細に重複させず、更新漏れを減らすため。
- 影響: 現在地点は `CURRENT_WORK.md`、理由を伴う判断はこのログ、長期工程は
  `PROJECT_ROADMAP.md` を正本とする。
- 再検討条件: 文書の役割が不足する、または新しい正本が必要になったとき。

## DEC-0002 — 完全一致とバリエーション一致を分ける

- 日付: 2026-07-26
- 背景: 元Shopee商品とAmazon候補の同一性を集計する際、同一シリーズの差分を
  完全一致と混同するおそれがある。
- 決定: `MATCH` と `VARIANT_MATCH` を別区分にし、`VARIANT_MATCH` を完全一致率に
  含めない。
- 理由: 評価指標の意味を保ち、後から商品仕様差を確認できるようにするため。
- 影響: `UNCERTAIN`、`MISMATCH`、候補なしも別集計する。
- 再検討条件: ユーザーが評価指標または判定区分の変更を承認したとき。

## DEC-0003 — 評価完了と成功判定を分ける

- 日付: 2026-07-26
- 背景: 分類と集計が終わった事実だけでは、Resolverの価値や完成を判断できない。
- 決定: 評価完了は分類・集計・記録の完了とし、成功基準は現時点で未決定とする。
- 理由: 評価実施の完了と事業・機能上の成功を混同しないため。
- 影響: 評価完了だけでResolverの成功や完成を宣言しない。
- 再検討条件: ユーザーが成功基準を明示的に決定したとき。

## DEC-0004 — AI Shadow開始には評価完了と明示承認を要する

- 日付: 2026-07-26
- 背景: AI実験へ早く移ると、固定30件評価の根拠と結果を確認できない。
- 決定: 固定30件評価の完了、集計結果のユーザー確認、ユーザーの明示承認がそろうまで
  Category Mapper / AI Shadowを開始しない。
- 理由: 評価の途中で工程を進めず、判断可能な材料を残すため。
- 影響: 同一性監査未完了の候補はAI Shadowへ渡さない。
- 再検討条件: 上記3条件を満たし、ユーザーが次工程を承認したとき。

## DEC-0005 — 実運用結果とGit・テスト証跡を区別する

- 日付: 2026-07-26
- 背景: 固定30件、9元商品、13候補、Keepa確認、PH Gate結果は現在地点に必要だが、
  Git・テスト・CIで再確認された証跡ではない。
- 決定: これらをユーザー確認済みの実運用結果として `CURRENT_WORK.md` に採用し、
  Git・テストで証明済みとは扱わない。
- 理由: 現在地を失わず、根拠の種類を混同しないため。
- 影響: 実運用結果だけからコード機能の対応市場やテスト成功を主張しない。
- 再検討条件: 対応するGit証跡、テストレポート、またはCI成果物を確認したとき。

## DEC-0006 — 将来のCONTEXT_SNAPSHOTは派生物とする

- 日付: 2026-07-26
- 背景: Git状態は変化し、手編集のsnapshotは正本文書とずれるおそれがある。
- 決定: 将来の `CONTEXT_SNAPSHOT` は正本から再生成できる派生物とし、snapshot本体は
  Git管理しない方針とする。
- 理由: 生成日時や作業ツリー状態による不要な差分と、情報露出を減らすため。
- 影響: snapshot単独を現在地点や判断の正本として扱わない。
- 再検討条件: snapshotの再現性や保持方法に不足が見つかったとき。

## DEC-0007 — READMEの市場記載は第1段階で変更しない

- 日付: 2026-07-26
- 背景: READMEの「Prelisting Gateは現在SGのみ対応」という記載と、ユーザー確認済みの
  PH Gate結果の関係は未解決である。
- 決定: 管理基盤Ver1・第1段階では原因調査、README修正、PH対応のコード確認を行わない。
- 理由: 現在地点の管理整備と、コード・仕様の検証を混ぜないため。
- 影響: PH対応のコード上の事実は未確認として扱う。
- 再検討条件: ユーザーが対応市場の調査またはREADME更新を明示承認したとき。

## DEC-0008 — CONTEXT_SNAPSHOTを再生成可能な引継ぎビューとする

- 日付: 2026-07-26
- 背景: 新しいChatGPTまたはCodexが会話履歴なしで現在地を短く確認できるビューが必要である。
- 決定: オーナー判断として、`CONTEXT_SNAPSHOT` は正本ではなく、Gitと管理文書から
  再生成する派生物とする。snapshot本体はGit管理しない。
- 理由: 正本を一元化し、生成物に秘密情報、絶対パス、商品本文、URL、ASIN一覧を
  含めないため。
- 影響: 引継ぎではsnapshotを利用できるが、矛盾時はGitと正本文書を優先する。
- 再検討条件: snapshotの安全性、再現性、または引継ぎ情報の不足が確認されたとき。

## DEC-0009 — 二層運用キット v1を3作業で試行する

- 日付: 2026-07-28
- 背景: ChatGPTとCodexの往復で、会話コンテキスト、貼り先、作業単位が増え、再開と
  検収の負担が高くなっている。
- 決定: ChatGPTは目的・理由・対象外・完了条件を`WORK_BRIEF`で整理し、Codexは現状確認、
  Plan、実装、検証、Git確認を担う二層運用にする。情報は種類別にGit、`AGENTS.md`、
  `CURRENT_WORK.md`、`DECISION_LOG.md`、`PROJECT_ROADMAP.md`を正本とする。Codexは
  5項目の完了報告を返し、最初の3作業でユーザー操作と混乱の削減を評価する。
- 理由: 新しい外部管理ツールや複雑なControl Planeを増やさず、現在の管理文書とGit安全規則を
  活用して、実際の操作負担を減らすため。
- 影響: 個別のBriefと会話ログはGit保存しない。新規Codexタスクは成果・目的、branch / worktree、
  module、役割が変わる場合だけ作成する。mainへの直接pushは原則行わず、恒久変更はfeature
  branchで扱う。Skill、Scheduled task、追加の作業票体系は3作業の評価まで導入しない。
- 再検討条件: 3作業後の評価で、貼り先の迷い、正本の再入力、marketplace・moduleの混同、または
  ユーザー操作の過多が確認されたとき。問題がなければ、現行の最小構成を維持する。

## DEC-0010 — Handoff Contract v1を正式運用する

- 日付: 2026-07-28
- 背景: Evidence Gate Liteを3作業で試行し、正本不整合、古いorigin/main、証拠不足を実装前に
  停止できた。一方で、チャット切替後に最新の現在地とGit外成果物を安全に再構成する契約が必要になった。
- 決定: GitHub mainへの記録を条件付きで引継ぎに十分とし、FORMAL提案とWORK_BRIEFにはEvidence
  Gateを必須とする。Codex開始時はfetch、formal commit、remote、worktreeを照合し、Git外成果物は
  最小索引だけをmainへ残す。正本更新時に古いBriefは失効する。
- 理由: ChatGPTとCodexが独立して根拠を確認し、新規タスクが古いlocal main、誤ったworktree、
  古いBriefから開始することを防ぐため。
- 影響: mainへの自動mergeは行わない。オーナーをSHAやworktreeの技術監査担当にせず、FORMAL Gateと
  同期ゲートで検査可能な条件を明示する。
- 再検討条件: 3作業程度の正式運用で往復回数、貼り先迷い、Gate漏れ、成果物再添付負担が改善しない場合。

## DEC-0011 — テンプレートv0.1.1 finalの正本SHAを再確定する

- 日付: 2026-07-29
- 背景: Git外成果物索引の`ef44…`とローカル実物の`d150…`が不一致だった。読み取り専用監査では、`ef44…`と一致する実物、producer記録、owner acceptance記録を確認できなかった。
- 決定: 正式SHAを`d150be6a552d0ef212f0ee4965f11f0c8f324eacbf3d8c56e05db07efd8d616e`とし、`ef44…`は索引誤記として修正する。
- 理由: オーナー一次記録の部分SHA `D150BE…D616` と完全一致する実物を一意に確認した。同一成果物パッケージのGuideは正本登録SHAと一致した。
- 影響: テンプレートSHA不一致による証跡監査の停止を解消する。固定30件の後続証跡は別途監査し、Resolver成功または21件再評価成功を意味しない。
- 再検討条件: `ef44…`と一致する実物および明確なowner acceptanceの一次証拠が新たに発見された場合。

## DEC-0012 — 固定30件回収TSVを歴史的Resolver実行入力として受け入れない

- 日付: 2026-07-29
- 背景: 完全SHAとproducer記録を持つ固定30件TSVを回収した。初回exportはR形式IDを持つが、TSVはJPH形式IDを持つ。ResolverはJPH IDを引き継がず、入力行からR IDを新規採番する。行順仮説ではタイトル一致が0/30だった。source map、生成プロンプト、run manifest等の実行記録は未発見だった。
- 決定: 回収TSVを歴史的初回exportの実行入力として正式受入しない。回収TSVは固定30件選定コホートの入力候補として保持する。初回export、13候補CSV、9件・21件区分をTSVへ推測接続しない。新しい一次証拠がない限り、歴史的JPH→R対応探索を保留する。次工程候補を、回収TSVによる再現可能な新規固定30件基準実行案の作成とする。
- 理由: 完全SHAとproducer chainだけでは、特定のResolver実行に使われたことを証明できない。決定論的な行順仮説が30/30でタイトル不一致だった。推測による対応はHandoff Contractと停止条件に反する。新規実行でsource mapと工程証拠を残す方が再現性を確保できる。
- 影響: 既存の9件・21件区分に基づく再評価バッチ準備は停止を継続する。回収TSV自体を破棄しない。外部AI、Keepa、実運用は別Briefとオーナー明示許可が必要。Resolver成功判定を意味しない。
- 再検討条件: 対象実行のsource map、生成プロンプト、run manifest、完全な対応表等の一次証拠が新たに発見された場合。オーナーが回収TSVを今後の新規基準入力として正式採用した場合。

## DEC-0013 — 新規固定30件基準実行の設計パッケージを承認する

- 日付: 2026-07-29
- 背景: 歴史的初回exportと回収TSVの対応は未証明である。現行Resolverはsource map、prompt、応答、export、batch再開情報を永続的な証拠として保存しない。現行Excelは人間向け工程記録には利用できるが、JPH→R対応や全成果物台帳の専用構造が不足する。設計ゲートで `RESOLVER_CHANGE_REQUIRED` と判定した。
- 決定: 回収TSVを新規固定30件基準実行専用の正式基準入力として採用し、受入状態を `OWNER_ACCEPTED_FOR_NEW_BASELINE_ONLY` とする。歴史的初回exportの入力とは扱わない。Resolverの証拠永続化改修を許可し、機械可読Evidence Manifestを全成果物台帳の正本候補とする。Excelは人間向け工程記録として最小補強する。外部AI、Keepa、実データ実行、21件再評価、実運用はまだ許可しない。
- 理由: 新規実行では入力から最終成果物までを一意に逆追跡できる必要がある。session stateだけでは中断・再開や後日監査に耐えない。Excelだけで証拠台帳を管理すると手入力・構造変更のリスクが高い。証拠永続化と検索精度改善を分けることで改修範囲を限定できる。
- 影響: 次工程はResolver証拠永続化改修とテンプレート最小補強になる。外部APIや実データは改修・テスト・実画面受入後に別決裁する。過去の9件・21件区分は新batchへ流用しない。Resolver成功基準は引き続き未決定とする。
- 再検討条件: 実装調査で複数moduleの共有インターフェース変更が必要と判明した場合。Evidence Manifestだけでは業務再開に不足すると判明した場合。オーナーの実画面確認で操作性または証拠確認に不足があった場合。外部AI・Keepa・実データ実行を承認する段階。

## DEC-0014 — PH ASIN Resolver証拠永続化実装をPR正式化へ進める

- 日付: 2026-07-30
- 背景: DEC-0013で承認したResolver証拠永続化実装について、作業branch上の技術検収、Resolver関連122件および全pytest 696件の確認、オーナーによる新規batch作成・prompt保存・再起動後のManifest再開・artifact表示の実画面確認が完了した。Git外のExcel／Guide rev2も技術検収とオーナー受入を完了した。
- 決定: `feature/ph-asin-resolver-evidence-persistence` の実装を技術成果として受け入れ、指定差分をcommit・通常pushし、main向けPRの正式検収へ進める。外部AI、Keepa、実商品、固定30件基準実行は引き続き別決裁まで許可しない。
- 理由: 入力から成果物までを追跡するsource map、Evidence Manifest、SHA、artifact chain、checkpoint、resume、rollbackの実装と、オーナー受入済みの人間可読実行記録を、main統合前のPRとして明確に区別して検収可能にするため。
- 影響: 証拠保存機能の完成はResolverの成功を意味しない。Resolverの本質的成功は英字商品名から正しいASINへ到達できることであり、ASIN到達性能は未評価である。正式成果はmain統合後に確定し、検索精度・商品同一性ロジック・Category Mapper／AI Shadow・SG／MY／THをこの変更へ混在させない。
- 再検討条件: PR差分・CIの正式検収、main統合、main統合後のformal commit確認、または外部AI・Keepa・実商品を伴う新規固定30件基準実行の別決裁時。

## DEC-0015 — 事業全体フローとResolverの中核価値を正式化する

- 日付: 2026-07-30
- 背景: 現行正本はPH Resolverの再評価準備を中心としていた。オーナーは、Resolver／ExpansionからGate、Category Mapper、既存出品ツールへ至る事業全体フローを明確化した。証拠保存機能の完成と、英字商品名からASINへの到達成功を混同してはならない。既存出品ツールの正式入力契約と自動接続方式は未確認である。
- 決定: Resolverの中核価値は、英字商品名から正しいASINへ到達することとする。Evidence Manifest、SHA、source map、中断再開は到達性能を測定・監査する補助機能であり、成功の代替ではない。商品候補生成は、英字商品名からASIN候補を生成するResolverと、既知ASINから関連ASIN候補を生成するExpansion Toolの2入口とする。候補はGuardrail／出品前保安ゲートで選別し、Category MapperはShopee Category ID、Brand ID、必須属性情報を確認・準備する。既存出品ツールへの正式入力契約と自動接続は別設計ゲートまで未確定とする。PHで端から端までの成立を確認してからSGとMYへ展開し、SGとMYの順序は現時点で固定しない。THは別途優先順位判断とする。Workflow実装、自動連携、自動出品、外部API実行はこの決定では承認しない。
- 理由: 各moduleの事業上の役割を明確にし、局所機能の完成を事業成功と混同しないため。PHで業務成立と測定方法を確認してから横展開する方が、市場固有差分を管理しやすいため。未確認の出品ツール契約を正本上の実装済み事実にしないため。
- 影響: `PROJECT_ROADMAP.md`を候補生成、候補選別、出品準備、市場展開の構造へ更新する。`CURRENT_WORK.md`の次工程を本正本差分の検収へ更新する。外部AI、Keepa、実データ、固定30件実行は引き続き別決裁とする。Category Mapper AI Shadowはオーナー明示承認まで開始しない。Resolver成功基準は新batchの工程別証拠がそろうまで未決定とする。
- 再検討条件: 既存出品ツールの正式入力仕様を確認したとき。PH Gate対応の不整合を解消したとき。PHの端から端までの受入結果が得られたとき。SGまたはMYの市場固有設計へ着手するとき。Workflowまたは自動出品を検討するとき。

## DEC-0016 — FORMAL作業単位とGPTチャット切替基準を正式化する

- 日付: 2026-07-31
- 背景: FORMALな作業の途中でチャットを切り替えると、根拠、差分、検収、PR、統合後確認が
  分断される。従来のRunbookには切替条件があったが、FORMAL作業単位の閉鎖とWORK_BRIEFの
  検査可能な欄を一意に定義していなかった。
- 決定: FORMAL作業単位は、同じ目的の設計、実装、修正、検証、技術検収、PR、main統合、
  統合後確認または読み取り専用結果の受入までとする。PR-backed FORMAL work unit（PRを伴うFORMAL作業）はGit管理対象の変更を
  成果とし、対象PRのmain統合、ChatGPTによる統合後formal main commitのGitHub直接確認、
  CURRENT_WORK.mdの統合後現在地と次の単一作業への更新の3条件がそろった時だけ閉鎖する。
  no-PR FORMAL work unit（PRを伴わないFORMAL作業）は、読み取り専用監査、BRIEF_GATE: STOP、EVIDENCE_PACKAGE: STOP、
  Git変更を成果としない技術検収、またはGit外成果物だけの正式検収とする。これらでは空commit
  または形式だけのPRを作成しない。ChatGPTによる基準formal main commitのGitHub直接確認、
  読み取り専用結果またはSTOP結果の正式受入、CURRENT_WORK.mdの作業後現在地と次の単一作業への
  更新の3条件がそろった時だけ閉鎖する。更新不要な場合は、ChatGPTによる
  CURRENT_WORK更新不要時の正式確認を3番目の条件の代替とする。同一作業の途中ではGPTチャットを
  切り替えず、閉鎖後に次のFORMAL作業を始める前に新しいGPTチャットへ切り替える。チャットの長さ、
  体感的な重さ、日付変更、module変更、新しいCodexタスクの作成は切替条件にしない。現在チャットが
  技術的障害で使用不能な場合だけ例外的な途中切替を許可し、これは閉鎖ではなく同一作業の継続とする。
  GPTチャット切替とCodexタスク切替は別判断とする。
- 理由: 作業の正式な切れ目を会話量や担当者の感覚ではなく、GitHub mainと正本文書で検査可能に
  し、引継ぎ時に未統合の作業事実を正式成果と混同しないため。
- 影響: WORK_BRIEFはGPT chat disposition、result target GPT project、result target GPT chat、
  FORMAL_WORK_UNIT_CLOSED、CHAT_HANDOFF_GATEを必須欄とする。FORMAL_WORK_UNIT_CLOSED: YESは、
  PRを伴うFORMAL作業またはPRを伴わないFORMAL作業の適用される3条件を満たした場合だけ使用する。
  両方式ともGitHub main、ChatGPT正式受入、CURRENT_WORKで検査可能にし、欄の欠落、空欄、不正値、
  矛盾する組合せ、またはCHAT_HANDOFF_GATE: STOPを検出した場合、Codexは編集、commit、pushを
  行わずBRIEF_GATE: STOPとする。静的検証で正常な継続・新規チャット組合せを受理し、異常な
  組合せとSTOP中の変更許可を拒否する。商品機能、外部API、業務インターフェース、ロードマップの
  工程順は変更しない。
- 再検討条件: 3件程度のFORMAL作業で、チャット切替漏れ、Brief欄の不整合、または技術障害時の
  例外運用が安全に扱えないことを確認したとき。GitHubまたはChatGPTの運用制約が変わるとき。

## DEC-0017 — 三つの独立ツールと出品支援ツール完成優先を正式化する

- 日付: 2026-07-31
- 背景: 現行正本は候補生成、候補選別、出品準備を中心としており、Shopee事業で開発する対象が三つの独立ツールであること、ならびに現在の投資順序を明示していなかった。外部既存出品ツールの正式入力契約は未確認であるが、その未確認範囲と、ASIN、Shopee Category ID、Shopee Brand IDの取得・確認を省力化する中核開発は区別する必要がある。
- 決定: Shopee事業で開発する対象は、出品支援ツール、出品後商品改善ツール、Amazon仕入れ支援ツールの三つの独立ツールとする。出品支援ツールはASIN、Shopee Category ID、Shopee Brand IDの調査・取得・確認を省力化する。出品後商品改善ツールはShopeeへ出品済みの商品リストの編集・改善を省力化する。Amazon仕入れ支援ツールはAmazonでの商品購入・仕入れを省力化する。三つのツールは相互連携せず、一つのツールの出力を他のツールの正式入力契約としない。ツール間に実行順序、API接続、自動連携、共有状態管理を設けない。現在は一つ目の出品支援ツール完成を最優先とする。この優先は開発順序であり、三ツール間の技術的依存関係を意味しない。二つ目・三つ目の本格設計・実装は、一つ目の完成受入後に優先順位を再判断する。外部出品ツールへの自動投入は別境界とし、外部契約未確認だけを理由に三項目の取得・確認に関する中核開発全体を停止しない。出品支援ツールの完成条件は次の設計ゲートで確定する。
- 理由: 三ツールの事業目的、利用者シナリオ、入力・出力、実行工程を混同せず、限られた開発投資を現在の中核目的へ集中させるため。未確認の外部出品ツール契約を、手作業で既存ツールへ入力できる情報を準備する工程の停止理由にしないため。
- 影響: Resolver、Expansion、Prelisting Gate、Category Mapperは原則として出品支援ツールの内部工程として扱う。二つ目・三つ目の詳細な入力、出力、機能、権限、完成条件は今回確定しない。三ツール間の共有インターフェース、共通データモデル、業務接続は設計しない。各ツールのリポジトリ配置または内部ライブラリ再利用も今回決めない。外部出品ツールへの自動投入、自動出品、ShopeeまでのE2E受入には別の設計、証拠、承認を必要とする。
- 再検討条件: 出品支援ツールの完成定義、残課題、利用者シナリオ、受入条件を設計するとき。一つ目の完成受入後に二つ目または三つ目の優先順位を判断するとき。外部出品ツールへの自動投入、自動出品、またはE2E接続を検討するとき。

## DEC-0018 — 軽量開発運用 v1へ移行する

- 日付: 2026-08-02
- 背景: GPTとCodexの必須往復、チャット・タスクのルーティング欄、読み取り専用作業にも及ぶ一律STOPにより、個人利用ツールの可逆な開発まで管理手続きで停滞した。オーナーは非エンジニアであり、目的、理由、利用方法、満足条件、禁止事項、実物確認を担当し、技術判断は技術側が担う必要がある。
- 決定: DEC-0009、DEC-0010、DEC-0016のうち、GPT必須中継、Handoff Contract、FORMAL作業閉鎖、GPTチャット切替を現役ルールとする部分を廃止し、軽量開発運用 v1へ置き換える。Codexは読み取り、branch作成、範囲内のローカル編集、テスト、検証済み差分のローカルcommitを直接進められる。費用、有料API、外部サービスへのlive書込み、復元不能操作、pushとDraft PR、merge、deploy、大幅な目的・責務変更は事前承認を必要とする。WORK_BRIEFは高リスク、複数範囲、外部影響、または目的の曖昧さがある場合だけ使用する。
- 理由: 手戻りを完全に排除するのではなく、小さく可逆な変更を早く確認して安全に直す方が、個人利用かつ顧客データ・決済を扱わない本ツールの実際のリスクに比例するため。技術方式をオーナーへ選ばせず、Codexが事業上の違いと推奨案へ翻訳するため。
- 影響: 過去の決定とGPT検収履歴は歴史的事実として保持する。GPTは完成定義、大きな設計、優先順位、批判的レビュー、非技術的翻訳で必要な場合だけ利用する。Git、テスト、CI、commit SHAは技術証拠として維持し、GPTによるSHA確認を成果成立の必須条件にしない。商品機能、外部API、業務インターフェース、三ツールの優先順位は変更しない。
- 再検討条件: 外部利用者、顧客データ、決済、本番自動書込み、法的義務、または誤りの影響範囲が増えたとき。軽量運用により秘密情報混入、無承認の外部操作、ユーザー変更の上書き、または重大な品質低下が発生したとき。
## DEC-0019 — 候補生成と市場別出品判断の責務を分離する

- 日付: 2026-08-03
- 背景: オーナーは、既知ASINから関連候補を広げるExpansionと、英字商品名からASIN候補を探すResolverを、出品先市場に依存しない候補生成機能として位置付けた。当初はSGの出品数を増やす目的で候補生成を開発したが、SGでアカウント保護上の問題が生じたため、PH向けの市場別機能を追加した。PHを製品全体の名称として扱うと、候補生成までPH専用または未完成と誤解するおそれがある。
- 決定: ExpansionとResolverは、出品先市場に依存しない候補生成の二入口とする。候補の出品可否、Guardrail、既出品照合、Category ID、Brand ID、必須属性は対象市場ごとの後段処理とする。PHは最初の実画面・実業務受入を行う市場であり、候補生成機能をPH専用とする意味ではない。Expansion画面に残るSG固定の一次判定は、候補生成と市場別判断の現行差分として監査対象にする。
- 理由: 市場固有の安全規則を候補生成へ固定せず、同じ候補生成機能を市場別の安全ゲートへ渡せるようにするため。SGの運用上の制約を受け、候補を安全と誤認させず、対象市場の規則で明示的に判定することを優先するため。
- 影響: 出品支援ツールv1の完成定義はExpansionとResolverの両方を中核として扱う。PHの受入完了はSG、MY、THの受入完了を意味しない。外部API、実商品、外部サービスへの書込み、自動接続、自動出品はこの決定では承認しない。
- 再検討条件: 候補生成自体に対象市場固有の一次資料、検索条件、法令適合性が必要と確認されたとき。対象市場のGate、Category / Brand確認、既出品照合の実業務受入結果が得られたとき。自動接続または自動出品を検討するとき。

## DEC-0020 — SG一次判定出力は利用状況が不明な間も保全し、対象を明確化する

- 日付: 2026-08-03
- 背景: 境界監査により、Expansion画面にはSG辞書による一次判定と`SAFE`のみの既存CSVが残る一方、対象市場を選ぶ出品前保安ゲート用の共通候補CSVもあることを確認した。オーナーは既存SG一次判定CSVの現在の実務利用状況を確認できなかった。
- 決定: 既存のSG一次判定CSVは削除せず、内容・形式・ファイル名を変えない。画面とREADMEで、これはSG専用の補助的な一次判定であり、SGを含む対象市場の出品可否は出品前保安ゲートで市場を選んで判断することを明確化する。
- 理由: 実務利用の可能性が不明な出力を廃止して既存作業を壊すより、可逆な表示上の明確化で市場横断の誤解を減らす方が安全だから。
- 影響: ExpansionとResolverを市場非依存の候補生成として扱うDEC-0019は維持する。外部API、実商品、外部サービスへの書込み、既存CSVの移行、自動連携、自動出品は承認しない。Gate結果CSVのschema version再検証は別の未完了差分として残す。
- 再検討条件: SG一次判定CSVの現行利用状況が確認できたとき。オーナーの画面確認で表示が誤解を招くと分かったとき。対象市場別Gateの実業務受入が完了したとき。

## DEC-0021 — 出品支援ツールの正式フローをGate中心に一本化する

- 日付: 2026-08-03
- 背景: オーナーは、出品支援ツールの完成形を「ExpansionまたはResolverで候補ASINを集める」→「出品したい国を選んで保安ゲートで確認する」→「Category・Brand情報を準備する」と確認した。Expansion画面に残るSG一次判定と`SAFE`のみ・監査CSV出力は、この流れの外にあり、非エンジニア利用者に保安ゲート後の結果と誤認させるおそれがある。
- 決定: ExpansionとResolverは候補生成とGate用候補CSVの出力だけを担当する。Expansion画面のSG固定一次判定、`SAFE`のみCSV、SG一次判定監査CSVは画面から外す。市場別のGuardrail、既出品照合、最終のELIGIBLE / REVIEW / EXCLUDE判定は、対象市場を明示して実行する出品前保安ゲートだけで行う。DEC-0020の既存出力保全方針は、この正式フローの決定により置き換える。
- 理由: 候補生成と出品可否判断を一つの分かりやすい手動フローに分け、途中のSG専用出力を最終判断と誤解しないようにするため。
- 影響: Guardrail辞書、GateのSG／PH対応、既出品照合、Category MapperのPH Gate ELIGIBLE入力条件、既存CSVのGate用ファイル名は維持する。外部API、実商品、外部サービスへの書込み、自動連携、自動出品は承認しない。Gate結果CSVのschema version再検証は別の未完了差分として残す。
- 再検討条件: オーナーの画面確認で正式フローが分かりにくいと分かったとき。旧SG一次出力に不可欠な実務用途が確認されたとき。対象市場別Gateの実業務受入が完了したとき。

## DEC-0022 — 通常のResolver画面から内部Evidence Batchを非表示にする

- 日付: 2026-08-03
- 背景: オーナーの画面導線確認で、`Evidence Batch（PH固定30件基準実行用）`は通常の英字商品名からASINを探す業務に不要であり、最初から表示すると通常フローの理解を妨げると分かった。
- 決定: 通常のASIN Resolver画面ではEvidence Batchの作成、再開、状態確認、一時停止、完了のUIを表示しない。証跡保存・再開の内部機能と既存のEvidence Manifestは削除せず、明示的な開発設定がある場合だけUIを表示する。
- 理由: オーナーが確認した正式フローである「候補生成 → 市場別Gate → Category／Brand準備」を、過去の固定30件評価用の内部操作で中断しないため。
- 影響: 通常のResolverは従来どおり候補生成を行う。通常利用者にEvidence Batch、formal main commit、Evidence Manifestの入力を求めない。外部API、実データ、外部書込み、自動連携、自動出品は承認しない。
- 再検討条件: 固定30件評価または証跡保存・再開を、通常業務でオーナー自身が操作する必要が生じたとき。通常の候補生成に証跡機能を再統合する事業上の目的が承認されたとき。

## DEC-0023 — 通常のCategory Mapper画面からカテゴリ同期管理を非表示にする

- 日付: 2026-08-03
- 背景: オーナーの画面確認で、PHカテゴリ一覧の最終同期日時、件数、キャッシュ、API状態、および手動同期は、Category／Brand候補を準備する通常業務に不要であり、画面の理解を妨げると分かった。
- 決定: 通常のCategory Mapper画面では、PHカテゴリ同期の状態表示と手動同期ボタンを表示しない。Category／Brand候補を作るCSV入力と推薦機能は維持する。同期管理機能と既存キャッシュは削除せず、明示的な開発設定がある場合だけ表示する。
- 理由: オーナーが確認した正式フローである「候補生成 → 市場別Gate → Category／Brand準備」を、日常操作に不要な内部管理情報で中断しないため。
- 影響: Category MapperはPHのみのまま維持する。通常利用者にカテゴリ同期、キャッシュ、API状態の判断を求めない。外部API、実データ、外部書込み、自動連携、自動出品は承認しない。
- 再検討条件: カテゴリ情報の更新可否や更新時期を、オーナーが通常業務で判断する必要が生じたとき。Category／Brand候補の品質問題がカテゴリ情報の更新不足に起因すると確認されたとき。

## DEC-0024 — PH Guardrailは一発アウト候補の遮断を最優先にする

- 日付: 2026-08-03
- 背景: オーナーは、Shopeeの実務では完全にアウトな品以外は実際に出してみなければ分からないことがあり、すべてのペナルティ可能性を事前に遮断することは現実的でないと確認した。
- 決定: PH Guardrailの第一目的を、過去の自社ペナルティ事例または明確な禁止・高危険根拠を持つ一発アウト候補の遮断とする。規約の全カテゴリを自動判定すること、ELIGIBLEを出品承認と扱うこと、根拠のない広範なBLOCK化は目的にしない。完全にアウトとは言えない候補はREVIEWとして理由を示し、作業者が試すかを判断する。
- 理由: 過剰な事前フィルタで候補を失うより、アカウントへの大きな影響が想定される候補を確実に避け、現実の出品結果から段階的に学習する方が実務に適合するため。
- 影響: 次の文書作業は、全規約対応表ではなく、現在のBLOCKルールの対象語、根拠、期待するEXCLUDE、将来の実務結果を記録するPH Guardrail Block Register v1とする。今回、辞書ルール、Gateの判定、実商品、Shopeeへの書込みは変更しない。
- 再検討条件: 実際の出品で新しい一発アウト事例、重大な見逃し、またはREVIEWの扱いが実務を著しく妨げることを確認したとき。

## DEC-0025 — Keepa活用は実装前のBLOCKルール分析に限定して開始する

- 日付: 2026-08-04
- 背景: オーナーは、Keepaの追加情報で一発アウト候補をより確実に検出できるかを確認したい。一方、現行コードはKeepa由来のASIN、商品名、ブランド、AmazonカテゴリをGate用に保存・利用しており、親ASIN、識別番号、成分、警告等のAmazon.co.jpでの取得可否、欠損率、効果は未確認である。GPT、Claude、Codexの検討により、Keepa機能、Safety Snapshot、schema変更、低リスク高速レーン、GPT補助、ルール管理UIを同時に始めない方針で一致した。
- 決定: 現在のPH BLOCK 31ルールについて、追加Keepa情報が既存一発アウト検出を改善し得るかを読み取り専用で分析する。この分析資料はレビュー用であり、Guardrail辞書CSVを置き換える運用正本としない。DEC-0024で提案されたBlock Registerは独立した運用正本として作らず、この分析資料へ具体化する。Keepa API、有料利用、実商品、Shopee書込み、辞書、Candidate CSV、Gate結果CSV、Gate判定、商品コードは変更しない。分析後、少数項目の効果が見込まれる場合だけ、小規模・上限付きKeepa読み取り確認を別途提案する。
- 理由: 未確認の詳細項目を前提に複数の新機能を作るより、現行の一発アウト基準に対する改善仮説を先に絞り、誤停止・REVIEW増加・欠損の危険を明示する方が、アカウント保護と出品速度の両方に適合するため。
- 影響: `docs/PH_GUARDRAIL_KEEPA_FIELD_IMPACT_ANALYSIS_DRAFT.md` をレビュー用資料として作成する。Gateの外部API非呼出し、既存schema、PHブランド辞書の空許容、REVIEWを手動でELIGIBLEへ書き換えない原則は維持する。
- 再検討条件: 独立レビューで分析の根拠または結論に問題が見つかった場合。実Keepa応答で親ASIN・識別番号等の取得可否や誤停止リスクが確認された場合。実務で新しい一発アウト事例または重大な見逃しが発生した場合。

## DEC-0026 — Guardrail禁止辞書を共通BLOCKと市場別BLOCKへ再設計する

- 日付: 2026-08-14
- 背景: 現行Guardrailは市場別辞書を前提としているが、オーナー提供の一次・実務資料を基準に、当社が出品しない対象と追加確認で販売可能性が残る対象を分け、禁止判定を単純化する必要がある。既存辞書は正解として固定せず、後続工程の比較・移行対象として扱う。
- 決定: BLOCK辞書は`COMMON_BLOCK`と市場別の`PH_BLOCK`、`SG_BLOCK`、`MY_BLOCK`等に分離し、選択市場の実効BLOCKを`COMMON_BLOCK ∪ 選択市場BLOCK`とする。市場別BLOCKは追加禁止だけを担当し、COMMON_BLOCKを解除しない。禁止辞書に一致した対象は必ずBLOCKとし、BLOCKからREVIEWへ降格する経路を設けない。BLOCKはShopee上で理論上販売可能かではなく、当社として出品しないと確定した対象を意味する。Shopeeが明確に販売禁止としている対象、輸出入または配送上当社運用で扱えない対象、現地ライセンスが必須で当社が取得しない対象、コミュニティNG情報等を根拠に当社が今後出品しないと確定した対象をBLOCK候補とする。REVIEWはBLOCKと別管理し、具体的な追加確認・対応で販売する可能性が残る対象だけに限定する。根拠のない漠然とした危険性では追加せず、通過またはBLOCKを決める確認事項を明記する。その情報を現時点で保有しない場合は無理にREVIEW辞書を作らない。ELIGIBLEは現在のBLOCK／REVIEW条件に該当しなかったことだけを意味し、Shopeeの販売承認、法令適合、知財安全性を保証しない。
- 理由: 当社の出品禁止を共通ルールと市場固有の追加禁止へ分けることで、同じ禁止事項の重複と市場別例外を避けられる。BLOCKとREVIEWの境界を具体的な業務行動で定義し、根拠のないREVIEW増加や確定禁止の降格を防ぐため。
- 影響: DEC-0024の一発アウト遮断優先は維持するが、REVIEWを「完全にアウトとは言えない候補」一般として扱う部分は、本決定の具体的な追加確認・対応を要する定義へ置き換える。DEC-0025のKeepa分析とHOLD結論は過去の分析結果として保持するが、次の単一作業はオーナー提供3資料の実物照合と`COMMON_BLOCK`／`PH_BLOCK`／REVIEW候補の設計・データ監査へ置き換える。今回、辞書CSV、商品コード、Gate判定ロジック、BLOCK／REVIEW具体項目は変更しない。SG／MY／TH等の具体的辞書内容も作成しない。
- 再検討条件: オーナー提供資料の実物照合で共通化できない禁止条件、必要な市場別例外、または明確なREVIEW確認手順が確認されたとき。実装設計で現行CSV契約やGate結果契約の変更範囲が確定したとき。実運用で重大な見逃しまたは過剰BLOCKが確認されたとき。

## DEC-0027 — Guardrail 3資料監査結果とPH採用判断を正本化する

- 日付: 2026-08-14
- 背景: Guardrail 3資料の実物監査は技術受入済みである。727候補は`COMMON_BLOCK_CANDIDATE` 18、`PH_BLOCK_CANDIDATE` 221、`REVIEW_CANDIDATE` 124、`INSUFFICIENT_EVIDENCE` 314、`SOURCE_CONFLICT` 6、`OWNER_DECISION_REQUIRED` 3、`OUT_OF_SCOPE_OTHER_MARKET` 41に分類された。124件のREVIEW候補には全件で具体的なhuman review questionがある。現行PH keyword辞書は89行であり、新BLOCK／REVIEW候補363件のうち337件は現行辞書と直接テキスト一致しない。これは公式資料がCategory ID中心、現行辞書がkeyword中心であることが主因である。
- 決定: 727候補をそのまま正式辞書とは扱わない。理由不足の一般コミュニティNG 311行は正式BLOCK／REVIEWへ移植しない。一方、市場と具体的NG理由が記録されたPHコミュニティ14項目は、Shopee公式禁止と同一根拠にはせず、当社内部リスク回避のcommunity evidenceとしてPH_BLOCKへ採用する。当社は販売のための現地ライセンスまたは政府許可を取得しないため、当社が取得しない許可が必須の商品は該当市場のBLOCKとする。市場固有の条件を理由にCOMMON_BLOCKへ昇格しない。一般用医薬品および医療用針は、この原則の適用例としてPH_BLOCKとする。SLS資料はファイル名の「2025年3月17日適用」とsheet内の2024年更新日を区別して保持し、後継資料が確認されるまで2026年もGuardrail根拠資料として継続使用する。これはオーナー運用判断であり、Shopeeが2026年現在も有効と公式確認済みという意味ではない。アルコール、医薬品／サプリメント、マスク、電池等は、単体電池・電池内蔵機器、オンライン販売禁止・SLS禁止・輸入禁止・現地ライセンス必須・事前承認可能などの条件差を大きなkeyword一つへ平坦化しない。
- 理由: 根拠不足の候補を自動的にBLOCKへ昇格させず、PHに限定された事業上のリスク回避とShopee公式根拠を区別するため。公式資料のCategory ID中心の判定単位を扱える設計がなければ、候補と現行keyword辞書の不一致を安全に解消できないため。
- 影響: DEC-0026のCOMMON_BLOCKと市場別BLOCKの原則を維持する。今回、Guardrail辞書CSV、商品コード、Gate判定ロジック、正式COMMON_BLOCK／PH_BLOCK項目、REVIEW辞書、台湾・タイ・マレーシア等の具体辞書は変更しない。次の単一作業は、Category ID等を扱う候補データ構造、判定単位、根拠種別の設計ゲートとする。データ構造そのものは今回確定しない。
- 再検討条件: 後継SLS資料、PHの一次根拠、またはPHコミュニティ14項目の理由に変更・不足が確認されたとき。設計ゲートでCategory ID等を扱う候補構造、根拠種別、既存keyword辞書との移行境界が明確になったとき。PH以外の市場を正式監査するとき。

## DEC-0028 — 出品支援ツールV2の責務・データ契約・実装原則を承認する

- 日付: 2026-08-15
- 背景: 現行正本はV1の候補生成、Gate、Category / Brand準備を中心としており、structured REVIEW、Fact取得の分離、発送条件、Category Batch化を含む承認済みV2方針を一意に読めなかった。
- 決定: 出品支援ツールの目的を、安全に出品準備できるASIN数を少ない人手で増やすこととし、評価軸を安全に出品準備完了できたASIN数を人間作業時間で割ったものとする。ASIN Expansionは既知Amazon ASINから関連候補を広げ、ASIN ResolverはShopee出品商品の英字タイトルから対応するAmazon ASINへ到達する。両者は候補生成の並列入口であり、出品可否、Guardrail、Shopee Category判定を担当しない。V2はCandidate、FactSnapshot、SafetyDecision、ReviewCase、OperationalFilter、CategoryBatchを論理的に分離する。APIはFact、RuleはDecision、AIはPrediction、HumanはExceptionとし、Gate／GuardrailはFact取得層と決定層を分離する。REVIEWは不足Factを解決する構造化ReviewCaseとし、APIで解決できるものを人間へ出さず、ruleの正式化にはevidence reviewとowner approvalを必要とする。発送条件はSafetyとは別のOperational Filterとし、初期条件はPrimeまたは翌日発送とする。Category Mapperは唯一のleaf Categoryの完全自動確定ではなく、Categoryと必須属性単位のBatch Preparationを主目的とする。接続は手動CSVを維持し、V1 / V2を区別して破壊的migrationを行わない。まずPHでdeterministic BLOCK、structured REVIEW + API auto-resolution、発送条件、Category Batch Builder、mandatory attribute Batch化、exception-only human confirmationの順に進める。
- 理由: 安全な出品準備を速く増やすために、候補生成、確認済みFact、安全判断、運用条件、カテゴリ準備、人間例外を混同せず、未承認の技術詳細を固定しないため。
- 影響: V2は実装前であり、コード、辞書、既存V1 schemaは今回変更しない。三つの独立ツール構成を維持し、自動Workflow／自動投入の保留を維持する。オーナーの実物受入前に完成扱いしない。
- 再検討条件: PHの実画面・実データ受入で、Fact取得可否、発送条件の技術マッピング、既存出品ツールのBatch共通入力、またはV1 / V2移行境界の追加判断が必要になったとき。

## DEC-0029 — V2 Phase 1 deterministic BLOCKの最小実装設計を承認する

- 日付: 2026-08-15
- 背景: DEC-0028でV2全体責務とPH-firstの実装順は承認済みだが、Phase 1 deterministic BLOCKのV1 / V2接続位置、Rule V2の最小表現能力、SafetyDecision V2の先行範囲、V1 schemaとの互換境界、Fact欠損時の扱い、実装を小さく保つ停止条件は未確定だった。現行コードではPrelisting Gateが内部で`apply_guardrails()`を実行しており、外部計算済みGuardrail結果を受け取る入力interfaceを持たない。
- 決定: Phase 1はV2 Safety全体ではなく、確認済みFactに対する`COMMON_BLOCK ∪ PH_BLOCK`のdeterministic BLOCKだけを追加するBLOCK veto layerとする。V2 deterministic BLOCKをGateへ別入力として渡さず、Guardrail層内の独立したpure Rule V2 evaluatorとして追加する。現行`apply_guardrails()`はV1 GuardrailとV2 deterministic BLOCKを内部合成する互換Facadeとして維持し、Gate側へV1 / V2合成責務を持たせない。`PRELISTING_CANDIDATE_V1`、`PRELISTING_GATE_RESULT_V1`、`evaluate_prelisting_gate()`のpublic interface、既出品・入力重複・self ASIN・metadata不足の判定、およびfinal eligibilityロジックは変更しない。V2 BLOCKが成立しない行は、`guardrail_status`、`guardrail_risk_category`、`guardrail_matched_terms`、`guardrail_source`、`guardrail_note`を含めV1単独時と完全互換にする。
- 決定: V2はBLOCK vetoだけを担当する。V1 SAFE / REVIEW / BLOCKにV2 no BLOCKなら各V1結果をそのまま返し、V1 SAFEまたはREVIEWにV2 BLOCKならBLOCKへ上げ、V1 BLOCKはV2の有無にかかわらずBLOCKのままとする。V2からV1 BLOCKをREVIEWまたはSAFEへ降格する能力は持たせない。PHでの実効V2 BLOCKは`COMMON_BLOCK ∪ PH_BLOCK`とし、PH_BLOCKはCOMMON_BLOCKを解除できない。Phase 1の有効化対象はPHのみで、SG / MY / TH等を同時展開しない。
- 決定: Rule V2は巨大なrules engineにせず、ASINのexact、Brandのexact、Product Titleのexact / contains、Shopee Category IDのexact、structured attributeのexactを上限とする。同一`rule_id`の複合条件は最大3条件のANDだけとし、ORは別ruleで表現する。NOT、regex、fuzzy、range、nested AND / OR、priority override、script、expression DSLはPhase 1で実装しない。4条件以上またはこれらの能力が必要になった場合は、Phase 1を拡張せず設計へ戻す。
- 決定: API = Fact、Rule = Decision、AI = Prediction、Human = Exceptionを維持する。Candidate V1のAmazon category文字列をShopee Category IDとして扱わず、AI予測CategoryをSafety Factとして扱わない。確認済みShopee Category IDまたはstructured attribute Factの供給経路がない場合、そのFactを必要とするRule V2は有効化しない。Fact欠損だけではBLOCKせず、GateまたはGuardrailが不足Factを埋めるためShopee、Keepa、AI等の外部APIを直接呼ばない。Phase 1は完全なPASS / REVIEW / BLOCK engineではなく、SafetyDecision V2のdeterministic BLOCK subsetだけを先行し、V2 BLOCK非該当をV2 Safety PASS保証とは扱わず既存V1フローを維持する。
- 決定: V2 rulesetのschema破損、未知operator、重複rule IDその他の信頼できない契約異常は「V2 BLOCKなし」と扱わずfail-closedで停止し、V1だけへ黙ってfallbackしない。現行PH 89ルールはV2の正解として自動移植せず、既存V1運用との比較・移行対象として維持する。
- 決定: DEC-0027のPHコミュニティ14項目をcommunity evidenceとしてPH_BLOCKへ採用するオーナー判断（`OWNER_APPROVED_PH_BLOCK_DISPOSITION`）は維持する。ただし、それは各項目のcanonical Rule V2が作成・有効化済み（`CANONICAL_RULE_V2_ACTIVE`）であることを意味しない。14項目を含む候補をRule V2へ具体化する前に、元Evidence実物、対象項目の一意な識別、Rule条件、必要Fact、false-positive境界、`rule_id`、evidence reference、machine-readable表現を確認するEvidence Gateを必要とする。この確認は採用可否の再判断ではなく、承認済みPH_BLOCK方針を安全なcanonical Rule V2へ具体化できるかの確認である。DEC-0027の候補分類だけを理由に、その他のCOMMON_BLOCK_CANDIDATE、PH_BLOCK_CANDIDATE、REVIEW_CANDIDATE、INSUFFICIENT_EVIDENCE、SOURCE_CONFLICT、OWNER_DECISION_REQUIREDを自動採用しない。
- 決定: structured REVIEW、ReviewCase、API auto-resolution、発送条件、Operational Filter、Category Batch Builder、mandatory attribute Batch、AI Category、自動Workflow、自動出品、SG / MY / TH等のV2有効化、727候補または最新community NGの一括移植はPhase 1対象外とする。
- 理由: 既存Gate interfaceとV1 schemaを壊さず、確定BLOCKだけを小さく追加できる構造にするため。Safety判断の責務をGuardrail層に維持し、GateをV1 / V2 Safety engineの合成層にしないため。未確認FactやAI Predictionによる過剰BLOCKを防ぐため。
- 影響: 今回変更するのは正本文書だけであり、コード、Guardrail辞書、V1 schema、Gate interface、API連携、UIは変更しない。DEC-0027のPHコミュニティ14項目の採用方針は維持する一方、canonical Rule V2は未具体化・未有効化のままとする。
- 再検討条件: Rule V2で4条件以上または複雑なoperatorが必要になったとき。Candidate / Gate Result V1の変更、Gate / GuardrailからのAPI呼出し、COMMON_BLOCKを市場側で解除する必要が生じたとき。PH実データで重大な過剰BLOCKまたは見逃しが確認されたとき。Category IDまたはstructured attribute Factの供給方式に追加設計が必要になったとき。

## DEC-0030 — Phase 1初期canonical Rule V2設計候補を13 Brand-exact PH_BLOCKに限定する

- 日付: 2026-08-15
- 背景: DEC-0029でPhase 1 deterministic BLOCKの最小実装設計を正本化した。その後、Git外Evidence 7点を実物・完全SHA-256で照合し、PHコミュニティ14項目と追加承認済みPH_BLOCK方針について、元Evidence、必要Fact、Rule条件、false-positive境界、V1重複を監査した。RULE_V2_EVIDENCE_GATEおよびEVIDENCE_PACKAGEはPASSである。
- 決定: Phase 1初期canonical Rule V2設計候補を、PHの`PH_BLOCK`、Fact `Brand`、operator `exact`、action `BLOCK`という共通条件を満たす次の13件だけに限定する: グルマンディーズ、Gourmandise、OXO、ZOJIRUSHI、Schleich、L'OREAL、nivea、LEGO、Shu Uemura、ロート製薬、Endgame Gear、エーザイ、ゼンハイザー。Candidateのbrandがexact一致した場合だけ対象とし、titleにブランド名が含まれるだけ、別ブランド、brand欠損、fuzzy / containsによるブランド判定ではBLOCKしない。13件が実装・有効化済みであることは意味しない。
- 決定: Boseイヤホン／ヘッドホンはRule境界が曖昧なため保留する。一般用医薬品および医療用針は必要Factが未供給のため保留する。その他711候補は新規canonical BLOCK採用判断なしでは進めず、今回対象外とする。
- 理由: 13件はDEC-0027によるowner-approved PH_BLOCK disposition、元Evidenceとの一意対応、Brand exactでの表現可能性、Candidate brand Factの利用可能性、明確なfalse-positive境界、およびDEC-0029のPhase 1最小能力を満たすため。
- 影響: 次の実装対象を13件だけに限定する。Rule V2コード、Guardrail辞書、V1 schema、Gate interface、Bose、一般用医薬品、医療用針、その他711候補は今回変更しない。
- 再検討条件: 13ブランドのbrand Fact品質に問題が確認されたとき。V1完全互換を維持できないとき。Boseの製品種別Factが確立したとき。Shopee Category IDまたはstructured attribute Factの供給経路が確立したとき。オーナーが追加canonical BLOCK候補を承認したとき。

## DEC-0031 — Phase 2前にPH End-to-End業務ボトルネック測定ゲート v0.1を挿入する

- 日付: 2026-08-16
- 背景: 出品支援ツールの最上位目的は、安全に出品準備できるASIN数を人間作業時間で割った値を高めることである。Phase 1 deterministic BLOCKはmain技術受入済みだが、DEC-0028の現行順序では次にstructured REVIEW + API auto-resolutionへ直進する。Safety REVIEW、Category、Brand、候補生成、またはPreparationのどこが実際の業務ボトルネックかは測定されていない。第三者独立レビューを受け、オーナーはPhase 2実装前にE2E測定を先行することを承認した。
- 決定: PH End-to-End業務ボトルネック測定ゲート v0.1をPhase 1後、Phase 2前に置く。対象はCandidate、Safety、Category、Brand、Preparationの5 Stageとし、Shopeeへの出品自体は対象外とする。成果状態は、PH Gateが`ELIGIBLE`である`SAFETY_CLEARED`、Amazon ASIN・確認済みShopee Category ID・確認済みShopee Brand IDまたは確認済みNo Brandが揃う`CORE_INFO_READY`、現行実装上`listing_ready`相当まで到達する`CURRENT_PREPARATION_READY`を論理的に区別する。外部出品ツールの正式入力契約は未確認のため、`CURRENT_PREPARATION_READY`を実際の出品可能とは扱わない。
- 決定: 実務担当者のStage・batch単位の概算`human_minutes`、`human_touch_count`、停止理由、既存出力参照を、既存のcandidate ASIN、Gate final eligibility・reason codes、Category推薦、Brand推薦、manual review、`listing_ready`等と可能な限り再利用して記録する。新しい物理CSV schemaやExcel列は、既存Git外実行記録を読み取り専用で確認するまで確定しない。初回コホートは20〜50程度のdistinct candidate ASINを実行時の目安とし、両入口が通常業務として利用できる場合はExpansionとResolverを含めるが、人工的に件数を均等化しない。中心指標は`CORE_INFO_READY ASIN / human hour`、補助指標はHuman Touch RateとStage Human-Time Shareとする。人間作業時間は操作・判断・情報確認を含め、API・AI・放置の待ち時間を原則含めない。Safety見逃しが観測された場合は時間効率だけで良い結果と評価しない。
- 決定: 測定結果を次の開発優先順位のEvidenceとし、structured REVIEW + API auto-resolution、Category / Brand、ASIN Resolver、ASIN Expansion、mandatory attribute、発送条件を測定前に固定順序へ戻さない。Baseline測定にCategory Mapper AI Shadowは含めず、開始しない。測定実行前に別途明示承認がある場合だけ、業務判断に影響しない観測専用Shadowとして並走できる。測定完了後はAI Shadowについて`START`、`HOLD`、`DROP`のいずれかをオーナー判断事項として提示する。PH v0.1を先に実使用し、Marketplace-neutral measurement schemaの共通化はその後に判断する。
- 理由: 想定した技術工程ではなく、実務担当者が実際に使う時間、介入、停止理由から、最上位目的を最も改善する次の開発対象を選ぶため。Safetyを弱めず、既存出力とGit外実行記録を優先して測定負荷と新規設計を最小に保つため。
- 影響: 今回は管理文書だけを更新する。実データ測定、Shopee・Keepa・AI API、AI Shadow、Phase 2、Category Mapper、Brand resolution、Resolver、Expansion、Guardrail辞書、Shipping、他市場、physical measurement schema、新しいExcelまたはCSVを開始・変更しない。既存Git外Excel実行記録は次の単一作業で読み取り専用に確認する。
- 再検討条件: 既存実行記録に流用可能な測定項目がない、Stage定義が現行出力と整合しない、Safety見逃しまたは重大な過剰な人間負荷が観測された、または測定結果が次の優先順位変更を示すとき。

## DEC-0032 — PH Beta Minimum Definition B1〜B7の成立可能性をBeta前に先行確認する

- 日付: 2026-08-16
- 背景: DEC-0031では、Phase 1 deterministic BLOCKの技術受入後、Candidate、Safety、Category、Brand、PreparationのEnd-to-End人間作業時間を測り、`CORE_INFO_READY ASIN / human hour`等を次の優先順位のEvidenceにする方針を定めた。既存Git外Excel実行記録の読み取り専用監査までは実施したが、実データの測定やmeasurement logの設計・作成は開始していない。その後のオーナー検討により、Beta成立前は省力化の程度より、出品支援ツールとして最低限必要な能力自体が現実に成立するかを先に確認することを優先する。
- 決定: PH出品支援ツールのBeta Minimum Coreを次のB1〜B7とする。(B1) ASIN ExpansionとASIN Resolverの両入口から実利用可能なAmazon ASIN候補を得る経路、(B2) PHを明示したSafety GateによりBLOCK / EXCLUDEを準備へ進めず、未解決REVIEWを準備完了に混ぜず、ELIGIBLEだけをCategory / Brand確認へ進める能力、(B3) 確認済みShopee Category IDへ到達する反復可能な経路、(B4) 確認済みShopee Brand IDまたは確認済みNo Brandへ到達する反復可能な経路、(B5) Category / Brandその他の未確定情報を推測で準備完了にせず停止する能力、(B6) Amazon ASIN・確認済みShopee Category ID・確認済みShopee Brand IDまたはNo Brandの揃い具合を候補ごとに一意に判別する能力、(B7) それらの確認済み情報を画面またはファイルで人間が取得・確認し、既存出品ツールへの手入力準備に利用できる能力。
- 決定: Beta前の詳細なE2E時間測定、`CORE_INFO_READY ASIN / human hour`、Human Touch Rate、固定工数削減目標は必須Gateから外す。DEC-0031は削除・編集せず、Beta後に必要なら実利用の継続改善手法として再利用できる判断履歴として保持する。
- 決定: 次工程は、B1〜B7をGitHub mainの実装・テスト・既存Evidenceに読み取り専用で照合するBeta Minimum Feasibility Auditとする。各MUSTをREADY / PARTIAL / BLOCKEDに分類し、現状・根拠・不足・最小対応を対応表で明示するが、このDecision自体はその監査または判定を行わない。Beta前の開発優先順位は、同監査で判明するBLOCKEDおよびBeta成立を妨げるPARTIALから決める。
- 決定: mandatory attribute全面対応は現時点でBeta MUSTではなくconditionalとする。監査で既存出品ツールへの実務的な手入力準備に不可欠と確認された場合だけ、Beta MUSTへの昇格をオーナー判断事項として戻す。structured ReviewCase完成形、API auto-resolution完成形、Shipping / Operational Filter、Category Batch Builder完成形、AIによるCategory自動確定またはAI Shadow、自動Workflow、GateからCategoryへの自動接続、外部出品ツールへの自動投入・自動出品、SG / MY / TH、exception-only human confirmationはBeta MUSTに含めない。
- 決定: Betaは完全自動化や固定工数削減KPIを要求しない。Beta受入ではB1〜B7にBeta成立を妨げるBLOCKEDがないこと、残るPARTIALの通常利用可能性をオーナーが実物で確認すること、少量の実商品で一連の導線を実画面・実業務として確認すること、EXCLUDE / 未解決REVIEWや未確認Category / Brandを準備完了に混ぜないこと、確認済みASIN / Category ID / Brand IDを人間が取得できることを条件とする。実画面、実データ、実業務の受入はオーナー確認前に完了扱いにしない。
- 決定: Beta後は、実利用、オーナーによる実務ボトルネック報告、次versionでの改善、再利用の反復へ移行する。必要になった場合も、既存の件数、status、未解決理由等の自動出力を優先し、人間へ詳細な時間記録を常時要求しない。
- 理由: 測定システムを先に整えるより、実際に使えるBetaの根本能力を最短で成立させることを優先する。不成立の能力があれば、作業時間を測るより先にその不足を解消する必要があり、実利用後の方が継続的な実務ボトルネックを発見しやすい。
- 影響: DEC-0031のBeta前E2E測定必須GateをこのDecisionでsupersedeする。measurement log設計・実測は停止し、Phase 2等へは自動直進しない。今回の変更は正本文書のみであり、コード、Guardrail、tests、README、外部API、実データ、Git外成果物、外部サービスへの書込みを変更しない。
- 再検討条件: Feasibility Auditで追加のBeta MUSTが判明したとき、mandatory attributeがBeta利用に不可欠と判明したとき、外部出品ツールの正式入力契約が判明してBetaのhandoff条件が変わるとき、またはBeta実利用で新しい重大な不足が確認されたとき。

## DEC-0033 — B1 Amazon Data Provider Test BridgeにCanopy試験専用providerを採用する

- 日付: 2026-08-16
- 背景: B1 Feasibility Auditで、既存のResolver / ExpansionとKeepa client起動経路は存在する一方、Keepa API契約が現在利用可能とは確認できず、Beta前のlive確認はPARTIALのままである。Keepaを本番標準として維持しつつ、Beta完成までの開発・試験を低コストで進める明示的なprovider境界が必要になった。
- 決定: 本番標準providerは `AMAZON_DATA_PROVIDER=keepa` のKeepaとする。Canopyは `AMAZON_DATA_PROVIDER=canopy_test` が明示された場合だけ用いるBeta開発・試験専用providerとし、通常UIでproviderを選択させない。credentialはKeepaを `KEEPA_API_KEY`、Canopyを `CANOPY_API_KEY` として分離し、秘密情報をGitへ入れない。自動provider fallbackは実装しない。Rainforestは今回対象外とする。
- 決定: Amazon ASINの存在確認はprovider境界を経由させ、Keepaの確認結果を `KEEPA_VERIFIED`、Canopyの確認結果を `CANOPY_VERIFIED` とする。Canopy確認結果を `KEEPA_VERIFIED` として扱わない。`PRELISTING_CANDIDATE_V1` の既存15列schemaとKeepa既存値（`KEEPA_VERIFIED`、`asin_resolver_keepa_verified`）を維持し、Canopy Resolverでは既存列に `source_verification=CANOPY_VERIFIED`、`source=asin_resolver_canopy_verified` を記録する。新schema versionは作らない。
- 決定: Canopy SearchはKeepa Product Finderと同等の性能・意味を保証する代替ではない。v0.1のExpansionは、起点ASINの商品・brand取得、brandをsearch termにしたJP Search、上位候補から最大5 ASIN、Product詳細によるbrand exact match、自ASIN・重複・不正ASINの除外に限定する。Canopy category構造をKeepa leaf categoryへ対応付けず、category利用はlive実データ確認後に再検討する。
- 決定: Canopy test modeの利用上限は、Resolverを1回最大10 ASIN・自動retryなし、Expansionを1回最大7 requests・最大5候補・pagination自動継続なし・自動fallbackなしとする。Canopy v0.1の結果は既存Keepa SQLite cacheへ書き込まない（no-write）。Canopy test mode時だけUIに `Amazon data provider: Canopy TEST` を明示し、provider-neutralにできる文言は「Amazon商品を確認」とする。
- 決定: Guardrail / Prelisting Gate / Category Mapper / Brand処理がCanopyまたはKeepa APIを直接呼ばない責務境界を維持する。provider差異は候補生成とASIN確認層で閉じる。
- 理由: Keepa本番標準と既存のSafety、Category、Brand責務を壊さず、無料枠の不用意な消費、確認出所の混同、cache混在を防ぎながら、B1の開発・mock試験を進めるため。
- 影響: 次作業はCanopy Test Provider v0.1の最小実装となる。live Canopy API試験は実装・mock test後に別途オーナー承認を必要とする。Keepa本番廃止、Rainforest実装、自動fallback、Canopy本番標準化、provider性能比較、Safety / Category / Brandロジック変更、SG / MY / TH、外部出品ツール接続、deployは今回対象外である。
- 再検討条件: live Canopy実データでAPI契約、request数、brand exact確認、category利用可能性、またはcache分離に追加設計が必要と判明したとき。Keepa本番契約が再開し、B1の本番経路を再確認するとき。Canopy以外のprovider追加が必要になったとき。

## DEC-0034 — PH Minimum Beta完成定義・受入条件を正本化する

- 日付: 2026-08-20
- 背景: PH Beta Minimum Feasibility AuditとCanopy Test Provider v0.1のmain統合後、次の完成定義と現行実装の差分監査に先立ち、何をBeta成立条件として比較するかを一意にする必要がある。
- 決定: Minimum Betaの目的は、provider最適化や完成度最大化ではなく、`候補生成 → PH Safety → Category / Brand確認 → 人間へのhandoff`までを実務上使い始められる状態にすることとする。Beta成立後は、実利用、ボトルネック発見、次Version改善を反復する。
- 決定: Beta Minimum Coreは既存B1〜B7を維持し、B8等を追加しない。候補生成はmarketplace-neutralなASIN Expansion / ASIN Resolverが担当し、PH Safety、Category / Brand確認、人間へのhandoffと責務を混同しない。BLOCK / EXCLUDEと未解決REVIEWを準備完了に混ぜず、推測したCategory / Brand値を確認済みFactとして扱わない。
- 決定: Feasibility Audit上BLOCKEDは0で、新規実装blockerは現時点で確認されていない。ただし、これは不足実装なし、Beta実装完成、または最終Beta MUST残課題の確定を意味しない。不足実装の有無、Beta blocker、最終Beta MUST残課題は次の完成定義と現行実装の差分監査で確定する。Keepa確認とPH実物受入だけが残課題だとは限定しない。
- 決定: structured REVIEW完成形、API auto-resolution完成形、Shipping / Operational Filter、Category Batch完成形、mandatory attribute全面対応、AI Shadow、自動Workflow、自動投入、自動出品、SG / MY / TH、固定工数削減KPI、Beta前の詳細E2E人間作業時間測定はBeta MUSTへ自動追加しない。mandatory attributeはconditionalのままとする。
- 決定: Canopy Test Provider v0.1はmain上の正式技術成果であり、Canopy Resolver / Expansionのlive正常系は技術確認済みである。B2〜B7のFeasibility Audit上READY、Gate / Category Mapper等の実装・testsの存在は、PH Minimum Beta全体、実商品、実画面、実業務、Keepa本番標準経路の最終実務確認のオーナー受入完了を意味しない。
- 決定: Keepaを本番標準Amazon Data Provider / Expansion provider、Canopyを`AMAZON_DATA_PROVIDER=canopy_test`明示時だけ用いる開発・試験専用providerとして維持し、自動fallbackを追加しない。SP-APIによるKeepa Expansion全面代替調査はHOLDとする。SP-APIは将来のKeepa依存削減候補であり、Beta MUSTを追加せず、Minimum Beta完成前にExpansion providerとして新規開発しない。Beta実利用後にKeepaコスト、契約、障害、利用制限、運用負荷が実際のボトルネックになった場合だけ再検討する。
- 理由: 技術成果とオーナー受入を混同せず、未検証の探索詳細を正式Factへ昇格させずに、次の差分監査が一意の基準で不足を確認できるようにするため。
- 影響: 今回は既存正本文書と完成定義草案だけを最小更新する。コード、tests仕様、Guardrail辞書、Rule V2、Candidate / Gate schema、Category Mapper、Amazon provider、SP-API、外部出品ツール、外部API、実商品、実画面、実業務、Phase 2、AI Shadow、SG / MY / THは変更・開始しない。個別HTTPレスポンス、individual ASIN試験結果、similarItems件数、Catalog Search件数、variation偏り、Git外cacheのpath・件数・SHA-256は正式Factとして記録しない。
- 再検討条件: 差分監査で追加のBeta MUSTまたは不足実装が確認されたとき、mandatory attributeが実務的handoffに不可欠と確認されたとき、Keepaのコスト・契約・障害・利用制限・運用負荷がBeta実利用で実際のボトルネックになったとき、またはオーナーがPHの実商品・実画面・実業務受入を行うとき。

## DEC-0035 — Minimum Beta差分監査結果と残る受入Gateを正本化する

- 日付: 2026-08-20
- 背景: DEC-0034のB1〜B7完成定義に対する読み取り専用の現行実装差分監査が完了し、次に新規実装を探索する段階か、Keepa本番経路とPH実物受入を確認する段階かを一意にする必要がある。
- 決定: B1〜B7に対する確認済み`MISSING_IMPLEMENTATION`は0件とする。これはBeta完成、Beta受入完了、実商品確認完了、実画面確認完了、実業務確認完了を意味せず、実物受入で新たなblockerが判明する可能性は残る。
- 決定: 残るBeta MUSTは、(1) ASIN ExpansionおよびASIN ResolverのKeepa本番標準経路のlive技術確認、(2) Candidate生成、PH Gate、EXCLUDE / REVIEW / ELIGIBLE、Category、Brand ID / 明示No Brand、`listing_ready`、人間向けhandoff、既存出品ツールへの手入力準備としての実用性を対象とするPH Minimum Betaのオーナー実物受入とする。Keepaを本番標準として維持し、Canopy結果で代替しない。
- 決定: 外部出品ツールの正式入力契約はBeta MUSTへ追加しない。B7は、現行の人間による手入力準備として実際に利用できるかをオーナーが確認して受け入れる。自動投入または正式E2E接続を検討する場合のHOLD事項は維持する。
- 決定: mandatory attribute全面対応はconditionalのままとし、実物受入で不足により実務的な手入力準備が成立しないと確認された場合だけ、Beta blocker候補としてオーナーへ戻す。structured REVIEW完成形、API auto-resolution完成形、Shipping / Operational Filter、Category Batch完成形、AI Shadow、自動Workflow、自動投入、自動出品、SG / MY / TH、SP-API Expansion代替、固定工数削減KPI、Beta前の詳細E2E時間測定はBeta MUSTへ追加しない。
- 理由: 実装差分の確認済み事実と、外部・実物によるオーナー受入を混同せず、未確認の外部契約や将来機能を先回りでBeta MUST化しないため。
- 影響: 次工程は、Keepa本番標準経路のlive技術確認を先行Gateに含むPH Minimum Beta実物受入プロトコルの定義とする。今回の差分は正本文書のみであり、コード、tests仕様、provider、Guardrail、外部API、実商品、実画面、実業務、外部出品ツール、Phase 2、AI Shadowを変更・開始しない。
- 再検討条件: Keepa本番標準経路のlive確認またはPH実物受入でBeta成立を妨げる事実が確認されたとき、mandatory attribute不足が実務的handoffを妨げると確認されたとき、または自動投入・正式E2E接続を別途検討するとき。

## DEC-0036 — PH Minimum Beta実物受入プロトコルを採用する

- 日付: 2026-08-20
- 背景: DEC-0035で確認済み`MISSING_IMPLEMENTATION`が0件と正本化された後、Keepa本番経路の技術確認とPH実物受入を、API障害、サンプル不適合、実装blocker、オーナー受入NGと混同せずに実行・判定する必要がある。
- 決定: `docs/PH_MINIMUM_BETA_ACCEPTANCE_PROTOCOL.md`を実物受入の正本とし、Gate K（Keepa本番標準経路live技術確認）をGate P（PH Minimum Beta実商品・実画面・実業務受入）より先行する二段Gateとして採用する。Gate KはKeepa利用・有料API利用について別のオーナー明示承認を得た後だけ実行する。CanopyでKeepa本番確認を代替しない。
- 決定: Gate PはB1〜B7の実物受入基準に従う。PASS、INCONCLUSIVE、STOP、BETA_BLOCKER_CONFIRMEDを区別し、INCONCLUSIVEを実装FAILと確定しない。mandatory attribute全面対応はconditionalのままとし、既存出品ツールの正式入力契約はBeta MUSTへ追加しない。
- 影響: Gate失敗またはblocker発見時も自動修正へ進まない。次工程はGate Kの実行条件確認とオーナー承認であり、今回、Keepa / Shopee API、実商品、実画面、実業務、外部書込みを開始しない。
- 再検討条件: Gate KまたはGate PでB1〜B7の成立を妨げる具体的事実、承認範囲外の外部API、またはmandatory attribute不足による実務的handoff不能が確認されたとき。

## DEC-0037 — Post-Beta開発管理基盤整備をPH実運用と並行するRoadmap工程として追加する

- 日付: 2026-08-24
- 背景: GPT / Codexプロジェクトの増加とworktree単位の`.env`分散により、複数開発時の進行管理およびcredential管理が複雑化する可能性がある。一方、PH Minimum BetaのGate K / Gate Pと実物受入は未完了であり、開発管理基盤整備を理由にPH実運用の開始を遅らせない必要がある。
- 決定: PH Minimum Betaのオーナー最終確認後、PH実運用を速やかに開始する。PH実運用と並行して、(1) GPTプロジェクトの棚卸し・統合・整理、(2) Codexプロジェクト / task / branch / worktreeの棚卸し・整理、(3) Secrets / API Credential管理基盤の設計・一元化、(4) 複数開発を俯瞰するマスター工程表 / ガントチャート整備を行う。
- 決定: Secrets / API Credentialは、保管を集中し利用権限を分離する方向で、別の設計ゲートで検討する。credential保管場所、最小権限、development / production分離、injection、rotation / revoke、秘密情報混入防止、worktreeごとの`.env`整理、移行・rollbackを検討対象とする。今回、Secret Manager製品、Secret方式、保存方式、credential実値、migration方式は決定しない。credential実値をGitまたは正本文書へ記録しない。
- 理由: PH Beta完成を遅らせず、実利用から得る事実を使いながら、将来の複数開発を安全かつ俯瞰的に並走できる状態を整えるため。
- 影響: 現在のGate K / Gate P、B1〜B7、次の単一作業を変更しない。この工程をPH Minimum Betaの新しいBeta MUSTまたはPH実運用の開始条件にはしない。今回の変更はRoadmapとDecision Logのみであり、コード、README、`CURRENT_WORK.md`、tests仕様、Secret実装、credential操作、外部API、実商品、実画面、実業務を変更・開始しない。
- 再検討条件: PH Beta完成時、複数プロジェクト並走開始前、またはPH実運用でcredential管理・進行管理の具体的なボトルネックが確認されたとき。

## DEC-0038 — PH Minimum Beta完成候補にClaudeによる第三者独立レビューを置く

- 日付: 2026-08-24
- 背景: PH Minimum BetaのGate K / Gate Pとオーナー最終確認の間で、完成定義、安全境界、B1〜B7、Keepa / Guardrail / Category / Brand / handoff、tests / Evidence、重大リスク、Beta前の過剰実装要求を独立に確認する工程を、オーナーが採用した。DEC-0037のPost-Beta開発管理基盤整備には影響しない。
- 決定: Gate P PASS後のPH Minimum Beta受入候補に対して、Claudeによる第三者独立レビューを行い、その後にオーナー最終確認を置く。Claudeは完成を決裁しない。レビューは、Minimum Beta完成定義との整合、安全境界の見落とし、B1〜B7との不整合、Keepa / Guardrail / Category / Brand / handoffの重大な抜け、tests / Evidenceの重大不足、Beta開始前に止めるべき重大リスク、Beta前に不要な過剰実装要求の混入を最低限確認対象とする。
- 決定: 重大指摘はChatGPT / オーナーがBeta blocker候補として再確認する。軽微な改善はBeta後改善候補とし、理想論・追加完成度要求は自動的にBeta MUSTへ追加しない。Claudeの指摘だけで自動修正または自動不合格にしない。PH Minimum Beta完成の最終判断はオーナーが行う。
- 理由: Gate実行結果と最終判断の間に独立した視点を置き、重大な見落としを確認しつつ、未検証の追加完成度要求でBeta開始を不必要に遅らせないため。
- 影響: Gate K / Gate Pの定義と順序、B1〜B7、Keepa本番標準、Canopy試験専用、既存Beta MUSTを変更しない。Claudeレビューは完成判断の品質確認工程であり、PH Minimum Betaの機能MUSTを追加・置換しない。今回の変更はRoadmapとDecision Logのみであり、コード、tests仕様、`CURRENT_WORK.md`、README、credential、API、実商品、実画面、実業務を変更・開始しない。Claudeレビューのためにcredential、`.env`、API key、顧客情報、秘密情報を正本文書へ記録しない。
- 再検討条件: ClaudeレビューでBeta blocker候補となる具体的事実、B1〜B7または安全境界の不整合、tests / Evidenceの重大不足、またはオーナー最終確認に追加判断が必要な事実が確認されたとき。

## DEC-0039 — Prelisting Gateのshop_labelを内部証跡識別子へ限定する

- 日付: 2026-08-25
- 背景: Gate P B2の実物受入で、shop_labelが出品可否のFactではないにもかかわらず、利用者に実ショップ名の入力を求めるUIが不要な停止要因になった。
- 決定: SG / PH共通のPrelisting Gate UIはshop_label入力を表示せず、既出品CSVのupload順に`{marketplace}_SHOP_n`を内部証跡識別子として決定的に生成する。同一marketplaceの全ショップ横断既出品ASIN照合を維持し、どこか1ショップに存在する候補は`EXISTING` / `EXISTING_ASIN` / `EXCLUDE`とする。全ショップ数と同数のinventory CSV提出義務、空inventory契約、重複ファイル保護を維持する。
- 決定: `parse_listing_inventory_csv()`、ListingEvidence / ListingInventoryFileResult、`evaluate_prelisting_gate()`、Candidate / Gate CSV schema、既出品ASIN unionの公開契約と判定意味は変更しない。実ショップ名はB2判定Factではない。
- 理由: 既存の全ショップ横断重複防止を弱めず、不要な人間入力だけを取り除くため。
- 影響: 次工程は、shop label入力のない修正版UIでPH B2 preflightをオーナーが実画面確認することである。今回、Keepa、Canopy、Shopee、SP-API、AI API、外部書込み、Category Mapper、実データ判定、Roadmap工程は変更・開始しない。
- 再検討条件: 実ショップ名が判定Factまたは外部出品ツール正式契約上の必須入力と確認されたとき、全ショップ数とCSV数の一致または横断重複照合を維持できないと判明したとき。

## DEC-0040 — Category Mapperの認証情報を一時利用に限定する

- 日付: 2026-08-25
- 背景: Gate P B4のShopee Brand取得で、既存ローカル認証情報が無効となり、管理シート側の更新済み認証情報を設定ファイル変更なしで安全に利用する必要が生じた。
- 決定: Category Mapperはオーナーが画面へ入力するShopee ACCESS_TOKENをブラウザsession内だけで利用し、空欄時は既存ローカル設定を維持する。入力値を設定ファイル、SQLite、その他ファイル、Git、ログへ保存しない。REFRESH_TOKENの入力・読込・保存・更新、OAuth、token refresh、管理シート連携をCategory Mapperへ追加しない。
- 決定: Category / Brand / Attributeの既存read-only取得経路とCatalog FactのローカルDB保存は維持し、認証情報の更新責務は既存のCategory Mapper外の仕組みに残す。
- 理由: Catalog Factの取得責務と認証管理責務を分離し、既存のtoken更新経路を重複実装せず、無効な固定認証情報によるB4停止を安全に解消できるようにするため。
- 影響: B4 Brand取得は再実行せず、Brand未確定停止を維持する。今回、外部API、外部書込み、認証情報更新、Roadmap、Resolver、Expansion、Prelisting Gateは変更・実行しない。
- 再検討条件: 外部の認証情報更新経路が変更されたとき、session内一時利用で安全なCatalog参照を維持できないとき、または別途承認されたSecrets管理基盤へ移行するとき。

## DEC-0041 — PH Ingredient Safety blockerにより第三者独立レビューを保留する

- 日付: 2026-08-26
- 背景: Gate P旧仕様のB1〜B7受入PASS後、オーナーはPHでGABA成分に関連するとされたアカウント凍結報告を確認した。現行Guardrailは成分Factを確認しておらず、この報告をBeta正式完成判定前に扱う必要がある。
- 決定: この報告はShopee公式の禁止物質または規約違反の断定ではなく、owner/community operational evidenceとして扱う。アカウント保護を優先し、DEC-0038で予定した第三者独立レビューを一旦保留し、次の単一作業をIngredient Safety Factと市場別BLOCK成分辞書の設計正本化へ切り替える。
- 決定: 旧B1〜B7 PASSは当時の仕様に対する受入履歴として保持する。ただし、PH Minimum Betaを正式完成とは扱わず、Ingredient Safety設計ゲートの結論を待つ。
- 決定: 今回の現在地切替だけでは、GABA rule、Keepaによる成分取得、Candidate schema、Guardrail辞書、Guardrail / Prelisting Gate実装方式、外部API利用を確定または変更しない。
- 理由: 新たに提示されたSafetyリスクを、未確認の公式根拠や実装方式へ早期に飛躍させず、Beta完成判断より先に設計上の扱いを明確化するため。
- 影響: `CURRENT_WORK.md` の現在地、次の単一作業、停止条件だけを更新する。`PH_MINIMUM_BETA_ACCEPTANCE_PROTOCOL.md`、`PROJECT_ROADMAP.md`、README、source、tests、Guardrail辞書、Candidate schema、API、UI、外部サービスは変更・実行しない。
- 再検討条件: Ingredient Safety設計ゲートで必要Fact、Evidenceの扱い、市場別BLOCK辞書の管理境界、実装要否が確認されたとき、またはオーナーが追加の運用Safety evidenceもしくは公式根拠を提示したとき。

## DEC-0042 — Ingredient Safety Factと市場別BLOCK成分辞書の設計を承認する

- 日付: 2026-08-26
- 背景: DEC-0041で、PHのGABA成分に関連するとされたアカウント凍結報告をowner/community operational evidenceとして扱い、第三者独立レビューを保留した。titleに現れない危険成分を既存Safetyだけでは検知できないため、API = Fact、Rule = Decision、Human = Exceptionの責務分離を維持したIngredient Safetyの設計原則を先に確定する。
- 決定: Amazon Data Providerは取得済みproduct Factから`ingredients`、`activeIngredients`、`specialIngredients`をSafety Factとして保持・供給する。Candidate / Fact transportはこれらの意味を変えずGuardrailまで搬送し、既存`PRELISTING_CANDIDATE_V1`の後方互換を必須とする。Candidate V2、sidecar、内部Fact objectその他の物理搬送方式は今回確定しない。
- 決定: Guardrail / Prelisting GateはIngredient SafetyのためにKeepaその他の外部APIを呼ばない。Guardrailは取得済みproduct titleまたはIngredient Safety Factと、選択市場の正式BLOCK ruleだけを照合する。正式BLOCK成分が確認された場合はdeterministicにBLOCKし、後工程でREVIEWまたはSAFEへ降格しない。Prelisting Gateは既存どおりGuardrail BLOCKを出品候補から除外し、成分取得・推測を担当しない。
- 決定: 対象成分が取得済みFactのいずれにも確認されない場合、その成分を理由にはBLOCKしない。成分3 Factがすべて欠損しても、欠損だけではREVIEWまたはBLOCKへ昇格しない。いずれも成分不存在または安全の保証を意味せず、残余リスクとして受容する。
- 決定: 初期Ingredient SafetyのBLOCK根拠はproduct title、`ingredients`、`activeIngredients`、`specialIngredients`に限定する。description、features、shortDescription、safetyWarning、itemHighlights、画像、OCR、Amazonページscraping、AIによる成分推測をSafety BLOCK Factへ入れない。
- 決定: 市場別BLOCK成分はowner-maintained deterministic ruleとして管理し、少なくともmarketplace、canonical ingredient / term、aliases、action = BLOCK、evidence reference / evidence typeを表現できるものとする。物理CSV列、exact / contains表現、正規化、alias格納方式、辞書編集UIは次のrepo-grounded技術設計で確定する。新成分は原則としてsource code変更ではなく辞書追加で扱える構造を目指し、GABA専用コードは追加しない。
- 決定: PHのGABAは、オーナーが確認したアカウント凍結報告に基づく`OWNER / COMMUNITY OPERATIONAL EVIDENCE`として当社運用上のBLOCK対象にする設計方針を採用する。これはShopeeがGABAを全面禁止物質として明示しているという公式ポリシー上の断定ではない。取得済みproduct title、`ingredients`、`activeIngredients`、`specialIngredients`でGABAが確認された場合はPH BLOCK対象とし、aliasesの完全セットと誤検知境界は次の技術設計で確定する。
- 理由: 未確認のFactをAIやGuardrailの逆方向API接続で補完せず、成分に現れた明確な運用上のSafetyリスクだけを市場別の決定論的BLOCKとして扱い、Candidate契約を壊さず拡張可能にするため。
- 影響: B2は正式BLOCK ruleが取得済みSafety Factに一致した候補をreadyへ進めず、Fact未取得だけではREVIEW / BLOCKへ昇格しない受入条件を持つ。今回、source、tests、Guardrail辞書、Candidate schema実装、Keepa / Canopy / Shopee / AI API、UI、README、`PROJECT_ROADMAP.md`、外部書込み、push、PR、merge、deployを変更・実行しない。GABA ruleはこの設計だけでは有効化しない。
- 再検討条件: repo-grounded技術設計でKeepa戻り値の型・実際のFact搬送経路・後方互換方式・辞書表現・正規化・誤検知境界を確認するとき、追加の市場別Evidenceまたは公式根拠が提示されたとき、または成分Factの欠損率や実務上の見逃しが確認されたとき。

## DEC-0043 — PH Guardrail BaselineをBeta MUSTとしてGate Pより先行させる

- 日付: 2026-08-27
- 背景: Ingredient Safetyの技術検証は完了した一方、PH向け禁止根拠の全件カバレッジ、各根拠のdisposition、`COMMON_BLOCK` / `PH_BLOCK`への登録境界、およびその受入は未完了である。Gate Pを再開する前に、PH Guardrail Baselineを明確なBeta MUSTとして完成させる必要がある。
- 決定: P0でPH Guardrail BaselineをBeta MUSTとして正本化し、Gate PをHOLDする。P0はmain統合後にP1へ進む。P1aでPH向け禁止根拠を全件棚卸しし、P1bで各Evidenceを`BLOCK`、`REVIEW`、`非対象・根拠不足`へdispositionして未判断を残さない。P1cで確定BLOCKだけを`COMMON_BLOCK` / `PH_BLOCK`に区別してGuardrailへ登録し、関連testを行う。P1dで`PH_GUARDRAIL_BASELINE_COMPLETE`を受入する。
- 決定: P2で通常フローを`Expansion / Resolver → Candidate CSV → 市場別Gate → ELIGIBLE / REVIEW / EXCLUDE`へ簡素化する。Ingredient Safety sidecar、Rule CSV、SHA binding等の内部安全機構は必要に応じて維持するが、通常利用者に不要な操作は極力隠す。DB化はこのBeta MUSTへ自動追加せず、具体方式は別設計で決定する。
- 決定: P3で最新PH Guardrailを含むGate P B2 — PH Safetyをオーナー再受入し、P4でGate P B1〜B7全体を実商品・実画面・実業務で受入する。P5でIngredient Safetyと最新Guardrailを含むEvidence Packageを再生成して第三者独立レビューを行い、P6でその結果を確認したオーナーだけがPH Minimum Beta最終受入とPH実運用開始を判断する。
- 理由: 実装済みの個別Safety機構と、PH向け禁止根拠の全体的なカバレッジ・正式運用ルールを混同せず、最新のGuardrailを前提にGate Pと最終受入を行うため。
- 影響: `PROJECT_ROADMAP.md`の「現在から先の工程」と`CURRENT_WORK.md`の現在地・次の単一作業・停止条件を更新する。旧Gate P受入履歴は保持するが、P0〜P2の新しい前提を満たすまで再受入またはPH Minimum Beta PASSの根拠にしない。今回、source、Guardrail辞書、tests、UI、Candidate schema、DB、外部API、外部書込み、push、PR、merge、deployは変更・実行しない。
- 再検討条件: P1aで利用可能・確認可能なEvidenceの範囲が確定できないとき、P1bでdisposition不能な根拠が残るとき、P1cで既存Guardrail契約を保てないとき、P2で内部安全機構の維持と通常導線の簡素化を両立できないとき、またはP3〜P5でBeta blocker候補が確認されたとき。

## DEC-0044 — PH Guardrail P1bの判断基準と依存工程前の正本化順序を明確化する

- 日付: 2026-08-27
- 背景: DEC-0043によりP1aのEvidence棚卸しは完了し、P1bで各Evidenceをdispositionする前段階にある。DEC-0024、DEC-0026、DEC-0027、DEC-0030はそれぞれ一発アウト遮断、BLOCK / REVIEW境界、市場別Evidence、13 Brand-exact PH_BLOCKを定めているが、SLSの市場別表、owner提供のNG・制限資料、community operational evidence、許認可、既存確定事項の正本化順序を、P1b開始前に一意に参照できるようにする必要がある。
- 決定: SLS出品可否確認表は市場別資料として扱う。PHのdispositionではPH欄とPH条件だけを用い、SG / MY / TH / TW等のNGまたは条件をPHへ推測適用しない。他市場NGまたは複数市場NGだけを理由に、PH_BLOCKまたはCOMMON_BLOCKへ自動昇格しない。
- 決定: SLS出品可否確認表、`ＮＧリスト.xlsx`、PH制限参考画像は、中立なカタログではなくNG・禁止・制限のEvidence sourceとして扱う。ただし全行を無条件にBLOCKせず、P1bで市場、適用条件、NG理由を確認し、BLOCK、REVIEW、非対象・根拠不足へ整理する。
- 決定: community operational evidenceは公式Evidenceと区別する。ただし、第三者販売で実際に生じた警告、削除、違反、ペナルティ、制限または凍結を示し、市場、ブランドまたは商品、具体的理由を確認できる場合は、当社内部のリスク回避BLOCK根拠になり得る。DEC-0027のPHコミュニティ14項目に関する採用方針を維持する。
- 決定: 正規品であることだけではブランドまたはIPリスクを否定しない。第三者販売への警告、削除申請、ペナルティ等の具体的EvidenceがあるブランドはBLOCK候補になり得るが、有名ブランドであることだけではBLOCKしない。DEC-0030で確定し実装済みの13 Brand-exact PH_BLOCKを降格しない。
- 決定: 現地ライセンス、政府許可その他の許認可が販売に必須で、当社が取得しない対象は、該当市場のBLOCKとする。「必要だからREVIEW」にはしない。市場固有の要件を理由にCOMMON_BLOCKへ自動昇格しない。DEC-0026およびDEC-0027の原則を維持する。
- 決定: REVIEWは、具体的な追加確認または対応により販売可能性が残る対象だけに用いる。通過またはBLOCK決定に必要な確認事項を示し、当社が取得しない許認可を確認待ちREVIEWに置かない。
- 決定: 後続の開発、実装、disposition、受入または優先順位判断の前提となるオーナー確定事項は、依存する次工程の開始前に適切な正本へ最小限反映する。順序は、会話・検討、オーナー判断確定、正本への最小反映、main統合確認、依存する次工程とする。既存に同一判断がある場合は重複Decisionを作らず参照し、仮説または却下案は正本化しない。
- 理由: 市場固有のEvidenceを他市場や共通禁止へ推測拡張せず、公式根拠と内部リスク回避根拠を区別しながら、確定禁止と現実に解決可能なREVIEWを一貫して扱うため。また、依存工程が未統合または仮説の判断を前提に開始されることを防ぐため。
- 影響: DEC-0024の一発アウト遮断優先を維持し、DEC-0026のBLOCK / REVIEW境界、DEC-0027の市場別Evidenceと許認可の扱い、DEC-0030の13 Brand-exact PH_BLOCK、DEC-0043のP1a〜P1d順序を再決定しない。今回、P1bの個別disposition、Guardrail辞書、Rule V2、source、tests、UI、DB、Gate P、外部API、外部書込み、push、PR、merge、deployは変更・実行しない。
- 再検討条件: 既存Decisionと矛盾し、優先関係を一意に決められないとき、SLSの市場別扱いと正本が両立しないとき、または個別dispositionにPROJECT_ROADMAP、辞書、P1b範囲を越える責務変更が必要と判明したとき。
