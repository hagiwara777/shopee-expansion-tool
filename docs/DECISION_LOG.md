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
- 背景: DEC-0043でP1a〜P1d工程を定義し、その後P1aのEvidence棚卸しはPR #38のmain統合により完了した。P1bで各Evidenceをdispositionする前段階において、DEC-0024、DEC-0026、DEC-0027、DEC-0030はそれぞれ一発アウト遮断、BLOCK / REVIEW境界、市場別Evidence、13 Brand-exact PH_BLOCKを定めているが、SLSの市場別表、owner提供のNG・制限資料、community operational evidence、許認可、既存確定事項の正本化順序を、P1b開始前に一意に参照できるようにする必要がある。
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

## DEC-0045 — PH Guardrail P1b Evidence dispositionをオーナー受入する

- 日付: 2026-08-28
- 背景: DEC-0044に従ってP1bの727件をdispositionし、ChatGPT検収差戻しを反映したv1-r1 candidateを作成した。後続P1cが確定済みP1b dispositionだけを入力にするため、オーナー受入、artifact identity、件数、P1c候補範囲を依存工程の前に正本化する必要がある。
- 決定: Git外artifact `ART-PH-GUARDRAIL-P1B-DISPOSITION-CANDIDATE-V1-R1`（`PH_GUARDRAIL_P1B_DISPOSITION_CANDIDATE_v1_r1.csv`、SHA-256 `27641fc0cde3bc3d585f939f9db3aeeb54545283716350554e4c74b1de382deb`、producer `Codex`、storage alias `LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/`）を`OWNER_ACCEPTED`とする。P1b dispositionは727件、`BLOCK` 243、`REVIEW` 125、`非対象・根拠不足` 359、未分類0でP1bを完了とする。非対象・根拠不足はSAFEを意味しない。
- 決定: P1c candidateは`YES` 229、`NO` 498である。REVIEW 125件をBLOCKへ変更せず、P1c対象にしない。P1cでは受入済みの229 candidateを入力として、各対象を`COMMON_BLOCK`または`PH_BLOCK`へ具体化・登録するかを判断する。このDecisionだけで229 Ruleを実装・有効化したものとはしない。
- 決定: GSA-0659（Boseイヤホン、ヘッドホン全般）はP1b `BLOCK`を維持するが、`p1c_candidate=NO`および`p1c_scope_hint=N/A`とする。DEC-0030のBose Rule境界HOLDを維持し、P1c対象へ戻さない。
- 決定: P1cは本Decisionの正本化差分がmainへ統合されたことを確認した後にだけ開始する。P1d `PH_GUARDRAIL_BASELINE_COMPLETE`受入前にGate Pを再開しない。
- 理由: 受入済みのEvidence dispositionと未実装のGuardrail登録を区別し、未統合または未確定の判断をP1cの入力にしないため。
- 影響: `DECISION_LOG.md`、`PH_GUARDRAIL_EVIDENCE_COVERAGE_AUDIT.md`、`CURRENT_WORK.md`のP1b受入状態と次工程を更新する。今回、P1c実装、Guardrail辞書、Rule V2、source code、tests、UI、DB、PROJECT_ROADMAP、Gate P、外部API、外部書込み、push、PR、merge、deployは変更・実行しない。
- 再検討条件: v1-r1 artifactのSHA-256または受入件数が一致しないとき、DEC-0030のBose HOLDと矛盾するP1c登録が必要になったとき、またはP1cで既存Guardrail契約を保てないと判明したとき。

## DEC-0046 — PH Safetyを商品チェックとCategory決定後チェックの二段階に分離する

- 日付: 2026-08-29
- 背景: P1c Expressibility Auditでは、受入済み229候補を現行の単純なGuardrail契約で安全に実装可能な対象は0件で、新しいFactまたはconnection changeが必要な対象189件、安全なRule boundaryが未解決の対象40件となった。Category判定をSafetyの前提にしすぎず、ExpansionとResolverの両入口、Guardrail、Category Mapperの責務を分離した設計原則をP1c技術設計より先に確定する必要がある。CodexとClaudeの独立レビューはいずれも`ACCEPT_WITH_REQUIRED_CHANGES`であり、元案の新しい`PASS`状態および非BLOCK候補の全件人間確認は採用しない。
- 決定: ExpansionとResolverはともに候補生成入口とし、候補生成自身にSafety責務を持たせない。両入口の候補は共通の出品前Safety判定へ渡し、Shopee上の既出品商品またはResolver由来であることだけを安全の根拠にしない。ResolverでAmazon ASINとの商品同一性が未確定の候補は、確定済みAmazon FactとしてSafetyへ渡さない。具体的なconfidence score、閾値、UIは後続設計で決める。
- 決定: PH Safetyは二段階とする。第一段階ではShopee Category確定前に、ASIN、Brand、Ingredient、商品属性、商品種別、許認可等の商品自体から判断可能なFactに基づき、明確な禁止は自動除外し、具体的な判断材料が不足する場合は解決に必要な確認項目を示して人の確認へ止め、禁止条件または確認要件が成立していない候補だけをCategory決定へ進める。Category決定へ進むことは絶対的な安全保証を意味しない。第二段階ではShopee Category確定後かつ`listing_ready`前に、Categoryおよび市場条件に依存する禁止・確認要件を再判定し、禁止は除外し、追加確認が必要な対象は人の確認へ止める。
- 決定: Category Mapperは出品可否の最終判断者ではなく、Safety判定を通過した候補を対象市場のどのCategoryへ準備するかを担当する。Category predictionとSafety判定を混同しない。AIを最終的な禁止または通過の決定者にせず、利用する場合はFact候補、商品種別候補、確認項目、Category候補の抽出・整理に限定し、AI出力だけを無検証で正式BLOCK Ruleまたは安全Factへ昇格させない。人の確認はFact不足、Resolverの商品同一性未確定、Category自動確定不能、Category決定後条件の機械判定不能等の未解決例外に限定し、既存出品ツールへの手入力をSafety再審査の代替にしない。
- 決定: このDecisionでは`PASS`、`NO_KNOWN_BLOCK`、`SAFE_CORRIDOR`等の新しい公開status / enumを導入しない。既存の`BLOCK / REVIEW / SAFE`および`EXCLUDE / REVIEW / ELIGIBLE`との具体的対応は後続技術設計で整理し、既存の`SAFE`を安全保証の意味へ拡張しない。Safe Corridor、positive whitelist、Amazon Browse Node等による全面的な入口制限、リスクスコアだけの通過判定、AIによる最終Safety決定、Expansionだけの独自Safety Firewall、非BLOCK候補の全件人間確認は今回採用しない。
- 決定: 2026-08-29のread-only auditでは、Seller Centre category datasetとOpen Platform `get_category` snapshotのCategory ID比較において、Seller Centreだけに存在する79 IDとSeller Centre `is_prohibit=true`の79 IDがexact一致した。これは今回取得したdataset間の観測事実であり、Shopee APIの恒久仕様とは断定しない。`is_prohibit`はCategory決定後のSafety Evidence候補とするが、このDecisionではRuleを実装しない。今回のdatasetでは`is_prohibit=true`の上位Category配下に`is_prohibit=false`の子Categoryは確認されなかったが、「親が禁止なら子は必ず禁止」という一般則を追加せず、各Category自身のversioned Evidenceを優先する。将来、親禁止・子非禁止の不整合を検出した場合は推測で通過させず設計確認へ戻す。
- 決定: 後続技術設計では、使用Fact、Rule / Evidence、marketplace、Category taxonomyの版または取得時点、人が確認した場合の確認結果を追跡可能にする。具体的なDB列、CSV列、schemaは今回確定しない。確認済みBLOCKを後工程でREVIEWまたは通過扱いへ降格せず、`COMMON_BLOCK`と市場別BLOCKの境界を維持する。今回の対象はPH Minimum Betaであり、他marketplaceへ実装しない。
- 理由: 商品自体から確定できるSafetyをCategory未確定のために遅延させず、同時にCategory依存の禁止条件も`listing_ready`前に確実に再確認するため。候補生成、Safety、Category決定の責務を分け、通常商品の全件目視やAIの無検証決定を避けながら、未解決ケースだけを具体的な確認へ回すため。
- 影響: 後続のP1c技術設計は、受入済み229候補をCategory確定前に判定できるもの、Category確定後に判定するもの、追加Factが必要なもの、Rule境界が未解決なものへ整理する。この正本化差分がmainへ統合されるまでP1c implementationを開始せず、P1d受入までGate PをHOLDする。今回、Guardrail、Category Mapper、Resolver、Expansion、Rule V2、BLOCK辞書、source、tests、UI、DB、schema、外部API、外部書込み、push、PR、merge、deployは変更・実行しない。
- 再検討条件: 二段階のどちらかで必要FactまたはRule境界を一意に定義できないとき、Resolverの商品同一性をSafety Factへ接続する契約を確定できないとき、Category taxonomy Evidenceに親子不整合または取得版の不明確さがあるとき、既存statusとの対応が安全保証を誤認させるとき、またはBeta実利用後に今回不採用とした案を再評価する具体的Evidenceが得られたとき。

## DEC-0047 — PH Guardrail P1c技術分類 v1-r1をオーナー受入する

- 日付: 2026-08-30
- 背景: DEC-0046のmain統合（formal main `49a383da7fd895973e66f08c8a0f065cf0f08c5d`）後、P1bで受入済みの229候補を二段階Safetyに沿って技術分類した。v1のOwner Decision Queue 15件についてオーナーが境界を確定し、hemp、GABA、武器を持つキャラクター玩具等の扱いを反映したv1-r1を作成した。後続工程が未受入candidateを前提に進まないよう、成果物identityと受入範囲を正本化する必要がある。
- 決定: 次のGit外artifact 3件を`OWNER_ACCEPTED`とする。`ART-PH-GUARDRAIL-P1C-TECHNICAL-CLASSIFICATION-CANDIDATE-V1-R1`（`PH_GUARDRAIL_P1C_TECHNICAL_CLASSIFICATION_CANDIDATE_v1_r1.csv`、SHA-256 `fadb8d18aec2dd8ac0453d608fd643b421d5fc7ec7f24b09f33562a3b121e68f`）、`ART-PH-GUARDRAIL-P1C-OWNER-DECISION-QUEUE-V1-R1`（`PH_GUARDRAIL_P1C_OWNER_DECISION_QUEUE_v1_r1.csv`、SHA-256 `16d17bad452ead487769f5a51c104c96b6e9c24d7d256a1538f8e302e897e707`、残件0）、`ART-PH-GUARDRAIL-P1C-TECHNICAL-CLASSIFICATION-SUMMARY-V1-R1`（`PH_GUARDRAIL_P1C_TECHNICAL_CLASSIFICATION_SUMMARY_v1_r1.md`、SHA-256 `5cf4f313e94f3e1cbddc599a92e6a22419c345d44ee91633779b7209baa0e434`）。producerはいずれも`Codex / PH Guardrail P1c Owner Decisions Applied`、storage aliasは`LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/`とする。
- 決定: 229件の確定分類は、`PRE_CATEGORY` 0件、`POST_CATEGORY` 170件、`ADDITIONAL_FACT_REQUIRED` 59件、`RULE_BOUNDARY_UNRESOLVED` 0件、オーナー判断残0件とする。P1bのoriginal dispositionを再判定せず、分類の受入だけでRuleを実装・有効化したものとはしない。
- 決定: Exhaust/CNGは親Categoryから子Categoryへ推測継承せず、個別に確認済みの子Category EvidenceだけをCategory決定後に判定する。hempはtitleに`hemp`を含む場合（`hemp-free`を含む）を対象とし、titleに現れない大麻・マリファナ・CBD・ヘンプ由来品は追加Factを必要とする。実武器、武器形状商品、武器を持つキャラクター玩具・模型、ガンプラ等は追加Factが必要な境界として扱う。
- 決定: GABA含有またはGABA商品のPH除外方針と既存GABA Evidence / Rule V2の関係は維持する。ただし既存matcherが`GABA-free`までBLOCKする差分を確認した。この差分は別修正事項として残し、今回の正本化ではRule、辞書、code、testsを変更しない。
- 決定: 次の単一作業は、本正本化差分のmain統合確認後に、`POST_CATEGORY` 170件をcurrent Shopee Categoryへ安全に接続する技術設計とする。`ADDITIONAL_FACT_REQUIRED` 59件のFact取得・搬送実装は開始しない。
- 理由: オーナーが確定した境界、Git外artifactの実物SHA、後続工程の入力を一意にしつつ、分類受入とGuardrail実装・業務受入を混同しないため。
- 影響: `CURRENT_WORK.md`の現在地、Git外成果物索引、残作業、次の単一作業、停止条件を更新する。P1d `PH_GUARDRAIL_BASELINE_COMPLETE`受入までGate P HOLDを維持する。今回、PROJECT_ROADMAP、Guardrail、Category Mapper、Resolver、Expansion、Rule、辞書、source、tests、UI、DB、schema、外部API、外部書込み、push、PR、merge、deployは変更・実行しない。
- 再検討条件: 3成果物のSHA-256または229件・分類件数が一致しないとき、P1c分類がRule実装済みまたはFact取得済みと誤認されるとき、GABA-free差分の解消に別のRule／code変更が必要になったとき、または170件のCategory接続でversioned Evidenceとcurrent Categoryを安全に対応付けられないとき。

## DEC-0048 — P1c POST_CATEGORY Connection Design v1をオーナー受入する

- 日付: 2026-08-30
- 背景: DEC-0047のmain統合（formal main `0d1d58a59c7f3e729e0c305fb367cbde9f693889`）後、受入済み`POST_CATEGORY` 170件を、SLS source EvidenceのCategory ID / full pathと2026-08-29のcurrent Shopee PH Category snapshotへstrict criteriaで照合した。後続工程が62件の確定mappingと108件の未解決範囲を混同せず、未解決Categoryを名前類似や意味推測で接続しないよう、設計、成果物identity、件数、次工程を正本化する必要がある。
- 決定: 次のGit外artifact 3件を`OWNER_ACCEPTED`とする。`ART-PH-GUARDRAIL-P1C-POST-CATEGORY-MAPPING-CANDIDATE-V1`（`PH_GUARDRAIL_P1C_POST_CATEGORY_MAPPING_CANDIDATE_v1.csv`、SHA-256 `f12b96dbe8a073c67a5d6bc75b0c542431b956cc50023321c617d130566c2ecd`）、`ART-PH-GUARDRAIL-P1C-POST-CATEGORY-UNRESOLVED-V1`（`PH_GUARDRAIL_P1C_POST_CATEGORY_UNRESOLVED_v1.csv`、SHA-256 `b61d2d78149ad2b8bd50193d660ae63486b7dc825c2b0d694fc51bfc1f4218c9`）、`ART-PH-GUARDRAIL-P1C-POST-CATEGORY-CONNECTION-DESIGN-V1`（`PH_GUARDRAIL_P1C_POST_CATEGORY_CONNECTION_DESIGN_v1.md`、SHA-256 `7f46486883f1b96f1631d0fc5a6f4ac398f066ad7ba691cbbf243ce104e461ee`）。producerはいずれも`Codex / PH Guardrail P1c POST_CATEGORY Connection Design`、storage aliasは`LOCAL_ARTIFACT_ROOT/PH_Guardrail_Evidence/Derived/`とする。
- 決定: `POST_CATEGORY` 170件のstrict照合結果は、current Categoryへ接続可能62件、未解決108件とする。接続可能の内訳は`CURRENT_ID_EXACT` 62件、`CURRENT_FULL_PATH_EXACT_UNIQUE` 0件である。未解決の内訳は`LEGACY_UNRESOLVED` 106件、`PARENT_SCOPE_UNRESOLVED` 2件である。fuzzy、AI、leaf名だけの一致、親Categoryから子Categoryへの推測継承は使用しない。108件のartifact受入は、108件が解決したことを意味しない。
- 決定: Category依存Safetyは、Category確定後にGuardrail所有のCategory依存Safety判定を行い、問題がない場合だけ`listing_ready`へ進める二段階Safety原則を維持する。Category Mapper自身を禁止判定者にしない。`PRELISTING_CANDIDATE_V1`、`PRELISTING_GATE_RESULT_V1`、既存Category Mapper CSVの破壊的変更は不要とし、具体的な内部interface、version binding、Category変更時のDecision invalidation、audit persistence、fail-closed表示は後続実装設計で確定する。
- 決定: 62件のstrict mappingを後続Rule設計の正式入力として受け入れるが、この受入をRule登録、Guardrail実装、Category Mapper実装または有効化の許可としない。未解決108件はそのまま保持し、LEGACY 106件の現在の後継CategoryとExhaust / CNG 2件の個別子Categoryについて、確認可能なSeller Centre Category Evidenceを追加取得・照合する。`ADDITIONAL_FACT_REQUIRED` 59件のFact取得・搬送実装は開始しない。
- 決定: 次の単一作業は、本正本化差分のmain統合確認後に、108件を解決するためのSeller Centre Category Evidenceのidentity確定とstrict再照合をread-onlyで実施することとする。以前取得済みのローカルdatasetを使う場合も、ファイル名、完全SHA-256、producer、取得元、取得時点、storage aliasを確認して正式Evidence identityを固定し、未索引ファイルを推測で正式根拠にしない。
- 理由: versioned Evidenceに基づく62件だけを確定入力として固定し、Evidence不足の108件を推測接続せず、Category決定とGuardrail所有のSafety判定の責務を分離したまま後続調査へ渡すため。
- 影響: `CURRENT_WORK.md`の現在地、Git外成果物索引、未完了事項、次の単一作業、停止条件を更新する。P1c implementationとGate PはHOLDを維持する。今回、`PROJECT_ROADMAP.md`、Guardrail、Category Mapper、Prelisting Gate、Resolver、Expansion、Rule、辞書、source、tests、UI、DB、public schema、外部API、外部書込み、push、PR、merge、deployは変更・実行しない。
- 再検討条件: 3成果物のidentityまたはSHA-256が一致しないとき、`170 != 62 + 108`となるとき、108件を解決済みとして扱う必要が生じるとき、strict criteriaでないmappingが必要になるとき、または次工程にRule／code変更が必要と判明したとき。

## DEC-0049 — PH Minimum Beta完成線を重大実務リスク中心へ再設定する

- 日付: 2026-08-31
- 背景: GPTがオーナー提供のSLS一次資料を直接確認した結果、同資料は単純な禁止Category一覧ではなく、SLS物流、危険物、発送可否の性格が強いと判断した。受入済みP1c成果では`POST_CATEGORY` 170件をstrict接続可能62件と未解決108件に分けたが、この完全追跡をBeta前に継続する限界効用は低い。既存実装と過去成果を壊さず、アカウント・知財・Safety上の重大な実務リスクを防ぎながら早く実務投入できる完成線へ優先順位を変更する必要がある。なお、Work Briefの「61件」表記は、既存正本で確認済みの62件を変更する根拠とせず、`170 = 62 + 108`を維持する。
- 決定: PH Minimum Beta前のMUSTを次の10項目に限定する。(1) Expansion / Resolverの既存候補生成機能を継続利用できること、(2) 既出品ASINおよび同一入力内ASINの重複を検出して準備対象から外せること、(3) 確定済みNG ASIN、Brand、知財Evidenceに基づく除外を行えること、(4) GABA、hemp等の確定禁止条件を取得済み商品情報から検出できること、(5) 商品titleだけでなく、description、featuresその他の取得可能な商品文章も禁止判定対象にできること、(6) 武器等、文章から明確に禁止対象と判断できる商品を除外できること、(7) 画像でしか判別できない武器等はAIを疑わしい商品の発見に利用し、AI推定だけで自動BLOCKせず人間確認へ回せること、(8) 判断不能な重大Safety案件を準備完了にせず人間確認へ止められること、(9) Category Mapper、Brand、handoffの既存機能を継続利用できること、(10) 少量の実商品でこの一連の流れを確認し、オーナーがBeta受入を判断すること。具体的な実装充足状況は未確認であり、本Decisionだけで各項目を実装済みまたはPASSとは扱わない。
- 決定: Beta前MUSTから、SLS旧Category 170件・未解決108件・strict接続可能62件の完全追跡、Category依存Safetyの網羅的Rule化、古いCategoryの後継Category完全特定、確定済みNGリスト外の知財をAI等で広範囲に推測してBLOCKすること、ASIN exact一致を越える高度な重複商品判定、他marketplace対応、自動出品を外す。これらは削除せず、必要に応じて再評価する`BETA_AFTER_CANDIDATE`として保持する。
- 決定: DEC-0043のP0〜P6をBeta前の必須順序とする部分、およびDEC-0048の未解決108件調査を次の単一作業とする部分を、本Decisionでsupersedeする。DEC-0034／DEC-0035のB1〜B7、DEC-0043のPH Guardrail Baseline、DEC-0046〜DEC-0048の二段階Safety・P1c分類・Category接続成果は履歴および将来Evidenceとして保持するが、本Decisionの10項目を越えてBeta blockerを自動追加する根拠にはしない。確定済みBLOCKを後工程で降格しない原則、候補生成・Safety・Category Mapperの責務分離、AIだけで正式BLOCKまたは安全Factを確定しない原則は維持する。
- 決定: Gate PはPASSにしない。新しい10項目に対する現行実装のread-only差分監査と、その結果に基づく必要最小限の別途承認済み対応を経て、少量の実商品による一連の流れをオーナーが確認するまでHOLDとする。過去のGate P PASSは旧仕様に対する受入履歴としてのみ保持する。
- 決定: 次の単一作業を「現行実装が新Beta MUSTのどこまで既に満たしているかのread-only差分監査」とする。監査では各MUSTを、確認済み実装、部分充足、未充足、未確認に区別し、未確認事項または理想的な追加機能を新しいBeta blockerへ自動昇格させない。監査中はコード、Rule、辞書、testsを変更せず、外部API、実データ、外部書込みを使用しない。
- 理由: 網羅的なCategory追跡より、確認済みの重大禁止、重複、知財、文章・画像から発見できる重大Safety、人間へのsafe stopを優先し、既存の有効な候補生成・Category・Brand・handoffを再利用してPH実務投入までの距離を短くするため。
- 影響: `CURRENT_WORK.md`を旧Category調査から新Beta方針とread-only差分監査へ切り替え、`PROJECT_ROADMAP.md`のBeta前／Beta後境界を同期する。過去のP1c成果物、identity、SHA-256、170件・62件・108件の確認済み事実は削除、無効化、再分類しない。今回、コード、Rule、辞書、tests、README、schema、UI、DB、外部API、実データ、外部書込み、push、PR、merge、deployは変更・実行しない。
- 再検討条件: read-only差分監査で10項目のいずれかに重大な未充足が確認されたとき、少量実商品受入で重大な見逃しまたは実務不能が確認されたとき、新しいBeta blockerを追加するオーナー判断が行われたとき、またはBeta後の実利用EvidenceによりCategory完全追跡その他の`BETA_AFTER_CANDIDATE`を優先する必要が生じたとき。

## DEC-0050 — PH Product Text Safety最小搬送契約とhemp境界を確定する

- 日付: 2026-09-01
- 背景: DEC-0049に基づくB0 read-only差分監査で、現行保安ゲートへtitleとIngredient Safetyの3成分fieldは届くが、description / features等の商品文章は届かず、PHのhemp確定BLOCK Ruleも未実装であることを確認した。Candidate固定15列、Expansion / Resolver共通経路、既存Ingredient Safety責務を壊さず、この不足だけをB1で解消する必要がある。
- 決定: `PRELISTING_CANDIDATE_V1`の15列は変更しない。Candidate最終bytesのSHA-256、`PRELISTING_CANDIDATE_V1` schema、Candidateとの完全一致ASIN集合に結び付く別CSV `PRODUCT_TEXT_SAFETY_FACT_V1`を新設する。schema、SHA、ASIN集合、重複ASIN、JSON cellまたはFact構造が不正なsidecarは使用せず停止する。Ingredient Safety sidecarのschema、責務、matcherは変更せず、汎用Sidecar Registryへ先行抽象化しない。
- 決定: ExpansionとResolverは、既存provider response / cacheから同一の内部Fact payloadを作り、同一serializerでProduct Text sidecarを生成する。追加Keepa requestは行わない。必須抽出対象は同名field `description`と`features`とし、`shortDescription`、`safetyWarning`、`itemHighlights`は既存応答に同名fieldが存在する場合だけ抽出対象とする。類似名探索、Web取得、AI補完、意味推測は行わない。
- 決定: capture statusは`CAPTURED`、`NOT_CAPTURED`、`NOT_AVAILABLE`、`PROVIDER_UNSUPPORTED`とする。markerのない旧Keepa cacheは`NOT_CAPTURED`、新規Keepa応答の承認済みfieldに非空文章がなければ`NOT_AVAILABLE`、Canopy Testは`PROVIDER_UNSUPPORTED`とする。これら3つの未取得statusは文章不存在またはSafety PASSを意味せず、そのstatusだけではBLOCKまたはREVIEWにしない。PH通常app flowでは対応sidecar未指定をpreflightで停止し、「sidecar渡し忘れ」と「sidecar内Fact未取得」を区別する。SGはlegacy互換としてsidecarなしでも実行できる。
- 決定: PHでは`product_title`およびProduct Text Factの承認済み5 fieldを対象に、NFKC・case正規化後のliteral substring `hemp`をdeterministic BLOCKとする。`hemp-free`と`hempseed`はsubstring一致によりBLOCKする。CBD、marijuana、大麻その他のaliasを推測追加せず、このRuleをSGへ適用しない。GABAの既存6 aliasと`contains_term` matcherは変更せず、`GABA-free`差分は別のオーナー判断まで未着手とする。
- 理由: Candidate互換性、両入口の責務統一、Fact未取得商品の過剰除外を維持しながら、取得済み文章に明示された確定禁止条件の見逃しだけを最小変更で減らすため。
- 影響: `modules/product_text_safety.py`、既存Keepa / Resolver内部搬送、Prelisting Gate、PH Guardrail Rule V2、通常app/UI、関連synthetic / mock tests、READMEを最小範囲で変更する。外部API、実商品、live書込み、画像AI、Bose、Category Safety、他marketplace対応、自動出品は実行・実装しない。Gate PはHOLDを維持し、独立reviewと少量実商品受入を別工程とする。
- 再検討条件: 追加Keepa requestなしで承認済みfieldを保持できないと判明したとき、固定15列CandidateまたはExpansion / Resolver共通契約を維持できないとき、Product Text sidecarとIngredient Safetyの責務が重複するとき、hemp以外のaliasまたはGABA-free境界に新しい事業判断が必要になったとき、または少量実商品受入で通常PH flowが成立しないとき。

## DEC-0051 — PH画像Safety・人間REVIEWの事業ルールを確定する

- 日付: 2026-09-02
- 背景: DEC-0049で、画像でしか判別しにくい武器等の疑義発見と、判断不能な重大Safety案件の人間確認をPH Minimum Beta前のMUSTに残した。B2 E2E全体フローの技術確認完了後、AIの権限、対象範囲、結果status、人間判断、商品単位REVIEWとGate全体STOPの境界を、使用技術の選定より先に事業ルールとして固定する必要がある。
- 決定: AIは、商品画像から重大Safety上の疑わしい対象を発見する補助に限定する。AI単独ではBLOCKせず、SAFEを保証せず、既存BLOCKを解除しない。Beta対象は画像上で見える武器・武器形状物の疑義発見だけとし、知財、Category、個別玩具ジャンルその他の対象を推測で追加しない。
- 決定: AI結果は`NO_SIGNAL`、`REVIEW`、`UNAVAILABLE`、`ERROR`、`INDETERMINATE`の5 statusとする。`NO_SIGNAL`は今回確認した画像で対象疑義を検出しなかったことだけを表し、SAFE保証ではない。`REVIEW`は疑わしい対象の検出、`UNAVAILABLE`は自動取得可能な画像なし、`ERROR`はAIまたは画像処理失敗、`INDETERMINATE`は一部画像失敗または十分判断できない状態を表す。`NO_SIGNAL`以外は原則商品単位REVIEWとする。
- 決定: 画像なしは商品単位REVIEWとし、それだけでGate全体を停止しない。人間が別経路で十分な画像を確認できた場合は`ALLOW_PREPARATION`を選択でき、人間も十分に確認できない場合はREVIEWを継続する。transient timeout、429、5xx等は最大1 retryとし、その後も失敗した場合は商品単位REVIEWとする。認証、契約、未対応設定等のシステム不整合は処理開始前にGate全体をSTOPする。
- 決定: Betaでは1商品最大3画像を確認する。一部画像が失敗した場合は`NO_SIGNAL`にせず、`INDETERMINATE`として商品単位REVIEWへ止める。人間最終判断は`ALLOW_PREPARATION`と`EXCLUDE`の2つとする。`ALLOW_PREPARATION`は画像由来REVIEWだけを解除し、他のBLOCKまたはREVIEWを解除しない。`EXCLUDE`はその商品だけを準備対象から外し、AIによるBLOCKとして扱わず、自動で一般Ruleまたは学習データへ昇格させない。
- 決定: sidecar schema不正、Candidate SHA不一致、ASIN集合不一致、重複ASIN、不正status、人間判断binding破損、AI認証・契約・未対応設定はGate全体STOPとする。`PRELISTING_CANDIDATE_V1`の固定15列を維持し、画像Safetyは独立sidecar方式を基本方針とする。汎用Sidecar frameworkは作らない。
- 決定: 今回はAI provider、API、model、prompt、正式sidecar schema、cache方式、具体的料金を決定しない。次の単一作業は「PH 画像Safety 使用技術・最小実装方式の選定」とする。Gate PとPH Minimum BetaはHOLDを維持する。
- 理由: AIの誤検出または未検出を正式な禁止判定や安全保証へ昇格させず、商品単位の人間判断で重大Safetyを保留できる最小境界を、Candidate互換性と既存BLOCK優先を維持したまま定めるため。
- 影響: `CURRENT_WORK.md`と`PROJECT_ROADMAP.md`を事業ルール確定・技術選定前へ更新する。今回、コード、Rule、辞書、tests、README、正式sidecar schema、外部API、実商品、外部書込み、push、PR、merge、deployは変更・実行しない。
- 再検討条件: 最大3画像では重大Safety疑義の発見に不足すると確認されたとき、statusまたは人間判断だけではfail-closedを維持できないとき、独立sidecarでCandidate bindingを安全に表現できないとき、またはBeta実利用で対象範囲の変更が必要なEvidenceが得られたとき。

## DEC-0052 — 市場横断のGuardrail一次EvidenceをGit外で固定管理する

- 日付: 2026-09-02
- 背景: DEC-0051の画像Safety技術選定に先立ち、Shopee Japan販売規制ガイドの実物とPH包丁記載を再現可能な根拠として固定し、将来の複数市場Guardrailが同じ資料identityを参照できるようにする必要がある。
- 決定: 資料IDを `SHOPEE_JAPAN_SALES_RESTRICTION_GUIDE` とし、`LOCAL_ARTIFACT_ROOT/Guardrail_Evidence/Sources/SHOPEE_JAPAN_SALES_RESTRICTION_GUIDE/original/` にPDF、同資料ID直下の `derived/` にTXTをコピーして保持する。元ファイルは移動・削除しない。既存 `PH_Guardrail_Evidence` は変更しない。
- 決定: `docs/evidence/GUARDRAIL_SOURCE_MANIFEST.csv` を資料索引の正本とし、PDFを `PRIMARY`、TXTを解析用 `DERIVED` とする。資料ID、artifact ID、完全SHA-256、bytes、storage alias、市場範囲、親artifact ID・親SHA、source_date・版、検証日時・方法を記録する。PDF/TXT本体、QA画像・詳細ローカルログはGitへ入れない。実パスは環境変数 `LOCAL_ARTIFACT_ROOT` で解決し、Gitにはstorage aliasだけを記録する。
- 確認事実: ローカルの番号なしPDFと `(1).pdf` はSHA-256および全bytesが一致した。異版候補はなく、指定名と完全一致する番号なしファイルをコピー元とした。PDF全9ページを抽出確認し、9ページ目の「フィリピン → 輸入禁制品 → 包丁」を描画して目視確認した。PDF/TXTともコピー前後の完全SHA-256が一致した。
- 確認事実: pypdf 6.10.0で全9ページを順に抽出し、PDF/TXTの空白・箇条書き記号（●・▪）・独立したページ番号2〜9を除去し、TXTの追加Reference行・独立URL行を除いた本文6811文字が完全一致した。正規化本文のUTF-8 SHA-256は `03bd80f8db7ae880d6d0a17cb153a4666dc5c657bd34a57e842e25f395958007`。TXTは同資料の解析用派生物として登録するが、生成者・変換ツール・変換履歴は未確認であり推測しない。追加Reference行はPDF一次本文の根拠として扱わず、列の配置・区分はPDFを優先する。
- 決定: source_dateとsource_versionは本文・PDF metadataで確認できないため `UNKNOWN_NOT_SHOWN` とする。取得日、取得元URL、TXTの変換方法は `UNKNOWN_NOT_RECORDED` とし、検証日時、ファイル作成・更新時刻、参照URL中の数字を資料日付へ代用しない。資料に記載された市場はSG / TW / TH / MY / ID / PHであり、この範囲は収録内容を示すだけである。
- 決定: `PRIMARY` は保存した資料に対する一次Evidenceの役割であり、最新版、法令・規約の現行性、個別Rule採用またはCOMMON_BLOCKへの昇格を認定しない。PDFが参考資料である旨を保持し、各市場の適用判断では資料identity・対象ページ・市場・項目を明示する。派生TXTだけで禁止区分または適用範囲を確定しない。
- 決定: 再利用時は完全SHA-256を再照合する。改訂・差替え時は既存bytesとidentityを上書きせず、新しいartifact ID・SHA-256・親子関係を索引に追加して旧版を保持する。候補を区別できない、hash不一致、同一資料性未確認、未確認日付の推測が必要、対象にユーザーdirty変更がある、またはPDF/TXTのGit登録が必要になる場合は停止する。
- 決定: 次の単一作業を「PH包丁規制の正式整理と画像Safety selectorへの反映判断」とし、DEC-0051の使用技術・最小実装方式の選定より先に行う。今回、PH包丁のRule境界、selectorへの採否、AI provider・model・promptは決めない。Guardrail Rule、辞書、判定コード、画像AI実装は変更しない。Gate PとPH Minimum BetaはHOLDを維持する。
- 理由: 同じ資料を市場別フォルダで重複管理せず、一次資料と解析用派生物を区別し、資料identityの保存と市場別の事業・実装判断を分離して再現性を保つため。
- 影響: 新設Manifest、CURRENT_WORK、B3の次工程記載だけを更新し、snapshotを既存スクリプトで再生成・検証する。ユーザー許可により検証済みローカルcommitまで実施できる。push、Draft PR、mergeは行わず、Rule実装や他市場展開へ自動的に進まない。
- 再検討条件: 日付・版・取得履歴を示す一次資料が得られたとき、新版または異なる内容の同名資料が見つかったとき、PDF/TXTの対応に不一致が判明したとき、またはPH包丁規制の正式整理で画像Safety事業ルールの変更が必要になったとき。

## DEC-0053 — PH画像Safety selectorのMinimum Beta範囲を確定する

- 日付: 2026-09-03
- 背景: DEC-0051の画像Safety・人間REVIEW事業ルールと、DEC-0052で登録した販売規制ガイド一次Evidenceを前提に、使用技術・最小実装方式の選定へ進むため、画像AIを実行するBeta範囲をオーナー承認により固定する。
- 決定: PH Minimum Betaで画像AIを原則実行するKeepa JP root categoryは次の4つに限定する。これは画像確認対象の選択であり、root自体のBLOCK判定ではない。

  | Keepa JP root category | root_category_id |
  | --- | --- |
  | おもちゃ | `13299531` |
  | ホビー | `2277721051` |
  | スポーツ＆アウトドア | `14304371` |
  | DIY・工具・ガーデン | `2016929051` |

- 決定: 上記以外の正常に識別できたroot categoryは、Betaでは原則画像AIを実行しない。`root_category_id`が欠損・不正・判定不能の場合はSKIPせず画像AI対象とする。既存title / description / ingredients SafetyでBLOCKが確定した商品には、rootの対象内外・不明を問わず画像AIを実行せず、既存BLOCKを維持する。
- 決定: 画像AIを実行しなかった商品を`NO_SIGNAL`とは扱わない。「未実行」と「画像確認済みで疑義なし」を分離する。DEC-0051の5つのAI結果statusと、疑義・画像なし・処理失敗・一部画像失敗・判断不能等を商品単位REVIEWにする原則は画像AI対象の商品に適用する。selectorによる対象外または既存BLOCKによる未実行をAI結果へ読み替えず、未実行をSAFE保証または既存Safety解除の根拠にしない。未実行の具体的な表現・記録方式は後続技術選定で決め、今回新しいstatus / enumまたは正式sidecar schemaを確定しない。
- 決定: ホーム＆キッチンroot全体はBeta画像AI対象にしない。Shopee Japan販売規制ガイドのPDF p.9「フィリピン → 輸入禁制品 → 包丁」が一次確認済みであり、現行PH Guardrailにも`kitchen knife` / `chef knife` / `包丁`のBLOCK Ruleがあるため、既存の明示語BLOCKを維持し、この理由でroot全体へ画像AI対象を広げない。Beautyその他root全体もBetaでは対象外とする。これらは正常にrootを識別できた場合の扱いであり、欠損・不正・判定不能時の対象化を上書きしない。
- 根拠: 一次資料identityは`SHOPEE_JAPAN_SALES_RESTRICTION_GUIDE` / `SJ-SALES-RESTRICTION-PDF-8ef486ce851b`、完全SHA-256は`8ef486ce851bda22ae2442c3c234ab33de29f44ccdf52f3e106c254ebdf7bb6d`。索引は`docs/evidence/GUARDRAIL_SOURCE_MANIFEST.csv`、区分・配置の根拠はPDF p.9とDEC-0052の確認記録とする。今回、登録済みPDF/TXTの完全SHA-256とbytesを再照合し一致した。現行Ruleはfetch済みformal main `2d309adb3dcfbf14bf5a348f25d5bf32f7468dd6`の`guardrails/risk_keywords_ph.csv`にあるPH-D070 / PH-D071 / PH-D072（title / contains / BLOCK / enabled TRUE）を直接確認した。資料の日付・版・現行性は推測せず、今回新たな法令解釈またはRule境界変更は行わない。
- 決定: title trigger、subcategory細分化、全rootの網羅的画像リスク調査は`BETA_AFTER_CANDIDATE`とする。Beta前のselector選定または網羅性確認として別名称で再開しない。既存title SafetyのBLOCKを適用することと、画像AI対象を増やすtitle triggerは分離する。
- 維持: DEC-0051の「画像上で見える武器・武器形状物の疑義発見」という目的、AI単独ではBLOCKしないこと、`NO_SIGNAL`はSAFE保証ではないこと、1商品最大3画像、transient error最大1 retry、疑義・判断不能等の商品単位REVIEWを維持する。人間最終判断は`ALLOW_PREPARATION` / `EXCLUDE`とし、前者は画像由来REVIEWだけを解除し、他のBLOCK / REVIEWを解除しない。sidecar schema・Candidate SHA・ASIN集合・重複ASIN・status・人間判断bindingの不正、およびAI認証・契約・未対応設定のGate全体STOPも維持する。`PRELISTING_CANDIDATE_V1`固定15列と独立sidecar基本方針を維持し、汎用Sidecar frameworkは作らない。
- 決定: selectorのBeta範囲は確定済みとし、次の単一作業を「selectorを前提としたPH画像Safety使用技術・最小実装方式の選定」とする。AI provider、API、model、prompt、正式sidecar schema、cache方式、具体的料金は今回選定しない。Gate P / PH Minimum BetaはHOLDを継続し、selector確定を実装完了またはBeta受入PASSとして扱わない。
- 理由: 既存の文章Safetyで確定できるBLOCKを優先し、承認された4 rootとroot不明の商品に画像確認を絞り、未実行と確認結果を混同せずに最小実装の選定へ進むため。
- 影響: DECISION_LOGへの追記、CURRENT_WORKのselector確定・次作業・停止条件、PROJECT_ROADMAPの必要な工程差分だけを更新する。snapshotは既存手順で再生成・検証し、Git管理対象外を維持する。本作業の検証済み差分のcommit、push、PR作成、mainへのmergeはオーナー明示承認済みである。Guardrail Rule、辞書、判定コード、画像AI実装、Candidate 15列は変更せず、外部API実行、実商品処理、deploy、Shopee live書込みは行わない。
- 再検討条件: Beta実利用で対象rootまたは未実行の扱いを変更すべき具体的Evidenceが得られたとき、資料identityまたはPH包丁記載に不一致が判明したとき、あるいは最小実装方式の選定でDEC-0051と本selectorの両立に未解決の事業判断が必要になったとき。変更は別判断として記録し、対象範囲を自動拡張しない。

## DEC-0054 — PH画像Safetyの使用技術・Minimum Beta最小実装方式を確定する

- 日付: 2026-09-03
- 背景: DEC-0051の画像Safety・人間REVIEW事業ルールとDEC-0053のselectorを前提に、オーナー指定の技術と最小実装境界を固定する。fetch済みformal main `3cb2d04d4a2c6e059a4e17e98c35101a223d3c8d`とCURRENT_WORKを確認して開始した。今回は設計・正本化のみであり、画像AI機能は実装しない。
- 決定: AI providerはOpenAI、APIはResponses API、Minimum Beta modelは`gpt-5.6-terra`とし、画像入力を使用する。reasoningは最小限に抑えるため、対応値の`reasoning.effort=low`を基本とする。1商品最大3画像を原則1 requestで判定し、商品をまたいで結果を混在させない。モデルの画像入力、Responses API、Structured Outputsおよびreasoning対応値は[OpenAIモデル仕様](https://developers.openai.com/api/docs/models/gpt-5.6-terra)で確認した。モデルを暗黙に代替しない。
- 決定: Responses APIのStructured Outputs（`text.format`の`json_schema`、`strict=true`）で、機械的に検証可能な出力を得る。対応するJSON Schemaで必須field・許容値・余分なfieldの禁止を定め、応答完了状態、refusal、schemaと値の検証を通過した結果だけを採用する。refusal、不完全な応答、解釈不能な結果を`NO_SIGNAL`へ変換しない。正式field名・prompt・schemaの具体化とsynthetic / mock検証は次の実装作業で行う。[Structured Outputs仕様](https://developers.openai.com/api/docs/guides/structured-outputs)
- 決定: API側の応答保存・後日取得を必要とせず、`store=false`を基本とする。複数画像を同一requestへ渡し、画像入力は処理時のURLまたは一時的な画像dataを用い、恒久保存やFilesへの継続保管を前提としない。`store=false`はZero Data Retentionの保証とは区別する。[画像入力仕様](https://developers.openai.com/api/docs/guides/images-vision)、[データ取扱い仕様](https://developers.openai.com/api/docs/guides/your-data)
- 維持: AIの権限は画像上で見える武器・武器形状物の疑義発見だけとする。AI単独BLOCK、SAFE保証、既存BLOCK解除は禁止する。`NO_SIGNAL`は今回確認した画像で疑義を検出しなかったことだけを表す。疑義・判断不能等は商品単位REVIEWへ送り、人間最終判断はDEC-0051の`ALLOW_PREPARATION` / `EXCLUDE`を維持する。前者は画像由来REVIEWだけを解除し、他のBLOCK / REVIEWを解除しない。後者はその商品だけを準備対象から外し、AI BLOCKや一般Ruleへ昇格させない。
- 維持: selectorはDEC-0053をそのまま使用する。原則対象はKeepa JP rootのおもちゃ`13299531`、ホビー`2277721051`、スポーツ＆アウトドア`14304371`、DIY・工具・ガーデン`2016929051`と、root欠損・不正・判定不能の商品とする。正常に識別できたその他rootは原則未実行とし、ホーム＆キッチン・Beauty等のroot全体を追加しない。既存title / description / ingredients SafetyでBLOCK確定済みの商品はrootに関係なくAI未実行とする。
- 決定: selector結果・理由、画像処理の実行状態、AIの意味上の結果をsidecar内で分けて記録する。selector対象外または既存BLOCKによる未実行ではAI結果を持たせず、`NO_SIGNAL`、画像なし、処理失敗へ読み替えない。未実行をSAFE保証や既存Safety解除の根拠にしない。DEC-0051の5 statusの意味は維持し、AIが返す意味上の結果（`NO_SIGNAL` / `REVIEW` / `INDETERMINATE`）と、システム側が判定する取得・実行状態から、商品単位の扱いを導く。画像なし・処理失敗等をAIに自己申告させてシステム状態の代わりにしない。
- 決定: 画像AI対象の商品で、画像なし・画像取得不能は`UNAVAILABLE`または原因に応じた`ERROR`、処理失敗は`ERROR`、一部画像失敗・十分判断できない場合は`INDETERMINATE`として商品単位REVIEWへ送る。残りの画像が`NO_SIGNAL`でも一部失敗を打ち消さない。人間が別経路で十分な画像を確認できた場合の`ALLOW_PREPARATION`と、十分確認できない場合のREVIEW継続はDEC-0051どおりとする。
- 決定: transient timeout、429、5xx等は最大1 retryとし、それでも失敗した商品はREVIEWへ送る。SDK等の自動retryを含めてこの上限を守り、原則1 requestに無制限の再試行を付け加えない。AI認証・契約・未対応設定等、結果を信頼できない全体障害はGate全体STOPとし、開始前に検出した場合は開始せず、実行中に判明した場合も続行しない。商品単位の失敗と全体障害を分離する。
- 決定: Keepaとの接続は、既存の商品取得応答から`root_category_id`と画像情報を取得・保持し、Expansion / Resolverから画像Safetyへ搬送する方向とする。現行Keepa正規化でroot保持は確認したが、画像情報の搬送・画像Safety接続が完成済みとは扱わない。画像Safetyだけを目的とした追加Keepa API requestはMinimum Betaでは原則行わず、既存応答・保持情報に画像がない場合は未取得を隠さず前述のREVIEW境界に従う。Amazon画像そのものは恒久保存せず、選択した最大3画像を処理時だけ利用する。
- 決定: `PRELISTING_CANDIDATE_V1`固定15列を維持し、PH画像Safety専用sidecarを作る。Candidate最終bytesのSHA-256、Candidateとの完全一致ASIN集合、商品ごとのrootとselector結果・理由、選択画像の参照identity・順序・使用結果、AI結果とシステム状態、provider / model、評価を識別する情報、人間判断を結び付ける。画像bytesそのものの恒久保存をbindingの前提にせず、処理時の内容hash等で実際に使用した画像を識別できる設計とする。人間判断は同じCandidate・ASIN・画像評価に結び付け、いずれかが変われば古い判断を流用しない。schema・Candidate SHA・ASIN集合・重複ASIN・status・人間判断binding不正はDEC-0051どおりGate全体STOPとする。汎用sidecar frameworkは作らず、正式sidecar schemaと検証処理はこの境界内で次の実装作業により具体化する。
- 決定: 現行Canopyはtest providerのままとし、Minimum Beta画像Safety対象へ拡張しない。Canopyで不足する情報を補う暗黙Keepa fallbackを追加しない。
- 決定: `gpt-5.6-luna`へのコスト最適化比較、provider複数対応、AI結果cache、title trigger、subcategory細分化、その他root拡張は`BETA_AFTER_CANDIDATE`とする。DEC-0053の全rootの網羅的画像リスク調査も同区分を維持する。sidecarへの評価記録を、別の商品取得・画像評価でのAI結果cache再利用に拡張しない。
- 未確認事項: 利用アカウントでのmodel利用可否・契約・データ保持設定、実際の画像形式・取得可否、検出品質、遅延、商品単位の実費は未確認である。公式仕様の確認を実API疎通・実商品受入の代わりにしない。画像選択順序、取得制限・timeout、prompt、正式schemaとbindingの検証ケースは次の実装で具体化する。これらは本決定を前提とする実装詳細・検証事項であり、provider選定を再開する別工程にはしない。外部API・実商品検証は別途オーナー承認を得る。
- 決定: 技術選定は完了とし、次の単一作業を「DEC-0054に基づくPH画像Safety Minimum Beta実装」とする。Gate P / PH Minimum BetaはHOLDを継続し、本決定を実装完了・Beta受入PASSとは扱わない。
- 理由: 既存の事業ルールとselectorを変更せず、1 provider・1 API・専用sidecarに絞り、AIの意味上の出力、未実行、商品単位の失敗、全体停止、人間判断の境界を保った最小実装へ進むため。
- 影響: DECISION_LOGへの追記、CURRENT_WORKの技術選定済み・次作業・停止条件、PROJECT_ROADMAPの必要な工程差分だけを更新する。snapshotは既存手順で再生成・検証し、Git管理対象外を維持する。関連文書検証後のローカルcommitまでを今回の承認範囲とし、push / PR / mergeは別途オーナー承認を得る。Guardrail Rule・辞書、既存判定ロジック、Candidate 15列、画像AI実装コードは変更せず、外部API実行、実商品処理、deploy、Shopee live書込みは行わない。
- 再検討条件: 指定model・API・設定を利用できないと判明したとき、最大3画像・追加Keepa requestなしでは承認済み境界を満たせないとき、安全なbindingまたは商品REVIEW / Gate STOPの分離を維持できないとき、あるいは検証Evidenceから事業範囲の変更が必要になったとき。モデル代替、対象拡張、既存Safety解除を暗黙に行わず、別判断として記録する。

## DEC-0055 — PH Minimum Betaを最終受入し少量実務投入へ移行する

- 日付: 2026-09-08
- 背景: DEC-0049はPH Minimum Beta前のMUSTを重大実務リスク中心の10項目へ限定し、少量実商品で一連の流れを確認した後にオーナーがBeta受入を判断する完成線を定めた。Product Text Safetyの必要最小対応、Resolver / Expansion両入口の少量実商品E2E、PH画像Safetyと人間REVIEWの実務確認が完了したため、formal main `8bfc46a2fe35b4492fe4365dbcb30353b3b9404f`上で最終事業決裁を行う。
- 確認事実: Product Text Safetyは固定15列Candidateを維持したsidecarとPH限定hemp Ruleの必要最小対応を完了し、独立read-only reviewとKeepa JP production read-onlyの少量live技術確認をPASSした。Resolver / Expansion両入口では、少量実商品でCandidate生成からSafety、exact重複、Category、Brand / No Brand、`listing_ready`、CSV / TXT handoffまでのE2E成立を確認した。
- 確認事実: PH画像Safetyは正式計画の5商品live検証を終了し、技術blockerは確認されなかった。疑義ありW1 / W2は2/2で`REVIEW`、非該当N1 / N2は2/2で`NO_SIGNAL`、境界A1は`REVIEW`となった。人間REVIEWではW1を`EXCLUDE`、A1を`ALLOW_PREPARATION`として元の`ELIGIBLE`へ戻す操作を実物確認した。Candidate SHA、ASIN集合、評価、人間判断のbinding、sidecar再読込、rerun保持、判断取消時の`REVIEW`復帰、既存`BLOCK` / `REVIEW`非解除をPASSした。
- 決定: オーナーはDEC-0049の現行Beta MUST 10項目を基準としてPH Minimum Betaを最終受入する。Gate Pを`PASS`、PH Minimum Betaを`PASS / OWNER_ACCEPTED`とし、PHに限定した少量実務投入を承認する。画像Safety追加サンプル検証は終了し、6商品目またはBeta前の追加ガンプラ試験を開始しない。
- 境界: この受入は、完全なSafety保証、Shopeeその他の規約適合保証、自動出品の完成または承認、外部出品ツールの正式契約確認、PH以外のmarketplace受入を意味しない。ASIN到達性能およびResolver成功基準は別の未確認事項として保持し、本受入から成功判定を推測しない。GABA-free matcher差分、Bose、Category 170 / 108 / 62件、`ADDITIONAL_FACT_REQUIRED` 59件、その他の既知課題を完了扱いにしない。
- 決定: DEC-0049、DEC-0053、DEC-0054で`BETA_AFTER_CANDIDATE`とした項目はその区分を維持し、今回の最終受入を理由にBeta前blockerへ戻さない。Beta後の改善は、実利用で観測した発生頻度、被害、実務ボトルネック、修正コストに基づいて優先順位を判断する。
- 理由: 承認済みの重大リスク中心の完成線に対して、必要最小実装、少量実商品E2E、画像Safety品質sanity、人間safe stopと最終判断が成立し、少量実務投入を妨げる技術blockerが確認されなかったため。
- 影響: `CURRENT_WORK.md`を最終受入完了・Beta実務投入へ切り替え、`PROJECT_ROADMAP.md`のB4を完了としてPH Minimum BetaをBeta実利用フェーズへ移す。今回の正本化ではOpenAI / Keepa / Shopee API、実商品処理、Shopee書込み、deploy、Beta実運用を実行せず、コード、Rule、辞書、selector、model、prompt、schemaを変更しない。snapshotを既存手順で再生成・検証し、検証済み文書差分をローカルcommitまで行う。push / PR / mergeは別途オーナー承認を得る。
- 再検討条件: 初回または継続するBeta実利用で重大事故、重大な見逃し、許容できない過剰REVIEW、実務不能なボトルネック、費用・遅延・外部契約上の障害が確認されたとき、またはPH以外へ範囲を広げる判断が必要になったとき。発生時はGate停止または改善要否を個別に判断し、本受入を完全保証として扱わない。

## DEC-0056 — Category AI Benchmark Ver1の比較契約とmock / 実AI評価境界を確定する

- 日付: 2026-09-11
- 背景: 現行Mapperの誤判断を伝播させず、商品EvidenceからShopee Category Treeを独立探索する汎用Coreで複数OpenAI modelの精度と商品単価を比較する。オーナーはPlanを3条件付きで承認し、反映後の新branch/worktree、local実装、mock test開始を明示承認した。
- 決定: `benchmark_request_profile`をversion管理し、exact model ID、reasoning effort、text verbosity、max output tokens、service tier、timeout、Responses endpoint、store / stream / truncation / tool条件、Prompt version / SHA-256、schema / traversal versionを固定する。各Predictionへ完全profile、profile hash、model以外の比較条件hashを保存する。モデル比較中にmodel ID以外の条件を変更せず、条件差のある結果を同一比較へ混在させない。
- 決定: Fake Providerは台本型とし、Prompt入力、許可field、strict schema、candidate allowlist、ABSTAIN、fail closed、step trace、token / cost / hash / Gold分離等のプログラム契約だけを検証する。product titleの意味的優先、resolver title非上書き、Tablet / Powder誤分類防止、main product / accessory / replacement / set識別等のAI精度はmock成功条件にしない。これらは実API smoke、35件、100件Benchmarkで初めて評価する。
- 決定: Hierarchical Traversalの各stepにparent ID / path、候補数、decision、selected category ID / name / path / leaf、confidence、reason、summary、usage、calls、latency、応答service tierを保存する。最終`prediction_confidence`はSELECTした全stepの最小confidenceとする。選択stepのないroot ABSTAINではnullとし、ABSTAIN応答confidenceはstepへ残す。confidenceは100件Benchmarkで信頼性を検証し、それまではCategory確定、自動承認、Safety判断へ使用しない。
- 決定: 固定Promptは`CATEGORY_AI_BENCHMARK_PROMPT_V1`を変更せず一元管理する。Goldは全Predictionのhash固定後に評価層だけで読む。AI入力はmarketplace、product title、Keepa category / brand、resolver title、現在path、現在child候補だけとし、Mapper判断、過去選択、Gold、評価結果を含めない。候補外ID、schema / API / catalog / traversal異常はfail closedとし、Mapper fallbackを作らない。
- 境界: 本CoreはPH / SG / MY / THのcatalog差替えに対応する独立Benchmarkで、正式Category Mapper、既存AI Shadow、Safety、Brand、Resolver、Expansion、Listing Tool、Shopee書込API、production SQLiteを変更しない。local実装・mock testまでを承認済みとし、実OpenAI API、費用、実商品、commit、push、PR、merge、deployは別承認とする。
- 理由: モデル以外の条件を固定して比較可能性を保ち、ソフトウェア契約の正しさとモデルの意味理解精度を混同せず、confidenceを未校正のまま業務確定へ使わないため。
- 影響: 固定base `03a35772a0f513cffec72ef8a4b2ea814aae6fdb`から`feature/category-ai-benchmark-v1`を作成し、独立Core / provider / config / UI / tests /文書を追加する。実API smoke直前で停止し、1モデル×3〜5商品、exact profile hash、catalog hash、最大request数、概算上限額を提示してオーナー承認を得る。smoke成功後も35件・100件へ自動進行しない。
- 再検討条件: 指定model・request field・Structured Outputsが利用できない、catalog snapshotが契約を満たさない、実APIで意味精度・confidence・費用・latencyに問題が出る、または正式Category Mapper統合の責務・interfaceを決める段階。

## DEC-0057 — 新規Benchmark 100商品のlocal auditとKeepa補充承認境界を確定する

- 日付: 2026-09-11
- 背景: Luna / Terra / Sol等を未知商品で公平に比較するため、既存35件と独立した10 genre x 10商品のBenchmark Set作成をオーナーが指示した。今回はCategory AI Core変更とmodel評価を行わず、Amazon候補からKeepa確認済みEvidenceを作る前段だけを対象とする。
- 確認事実: ASIN Resolver / Expansion、Keepa確認済みCSV、Prelisting候補、関連JSON / SQLite / Excel artifactをread-only監査した。既存35件、smoke 5件、synthetic fixture、blank template、同一ASIN、同一商品の近接variantを除外すると、必要Evidence 5 fieldを持つ候補は6商品だった。凍結PH catalogの指定10 root名はすべてexact一致した。genre内訳はBeauty 1、Hobbies & Collections 5、その他8 genre 0で、94商品が不足する。
- 決定: 100商品未達のため正式Source CSV、Gold Review Packet、Gold Truth Review、manifestを作成しない。Difficulty、Codex Category候補、ABSTAIN候補、Gold reviewer fieldもDataset完成前に確定しない。local mock / live smoke Predictionを商品選定へ使用しない。
- 決定: 補充は、AIを使わずAmazon候補ASINと実際のresolver input titleを先に固定した後、Keepa JP Product endpointでASIN、固有title、category、brand、必要ならroot category / product groupをbatch取得する。94商品が全採用なら94 tokens、25% buffer想定118 tokens、1不足枠につき最大2候補のhard cap 188 tokensとする。Product Finder単独発見はresolver_titleのprovenanceを満たさないため現契約の正式Sourceには使わない。
- 境界: Keepa、OpenAI、Shopee APIは今回0 request。Keepa補充は別途オーナー明示承認を得る。Category AI Core、Prompt V1、Traversal、model profile、正式Category Mapper、Brand、Guardrail、Resolver、Expansion、Listing、production SQLite、AI Shadow、precision branchを変更しない。commit、push、PR、mergeを行わない。
- 理由: 100件の件数を優先してEvidence provenanceや未知評価データ性を崩さず、API費用発生前に不足と最大消費を明示して承認を得るため。
- 再検討条件: Amazon候補ASIN + resolver_titleを94採用分とbuffer分まで用意できない、Keepa Product responseで必要Evidenceが揃わない、実質variant除外後に10 genre x 10を満たせない、またはProduct Finder等の別取得方式を採用する判断が必要になったとき。

## DEC-0058 — Product FinderをBenchmark候補発見だけに限定し専用runnerを採用する

- 日付: 2026-09-12
- 背景: DEC-0057のlocal auditでは新規100商品に94件不足し、既知ASINを確認するProduct APIの前にAmazon.co.jp候補ASINを発見する工程が必要になった。汎用Keepa clientはProduct Finder失敗時の診断・fallbackと候補詳細の一括取得を持ち、今回承認されたno-fallback、hard cap、選抜候補だけProduct確認する契約とは一致しない。
- 決定: Product FinderはCategory AI Benchmark V1の評価Source候補ASIN発見だけに使用する。Finder結果は正式Sourceではなく、ASIN dedupe、既存35件、smoke 5件、seed、family / variant除外後に選抜し、Keepa JP Product APIでASIN、title、category等の商品データを確認できた候補だけをSource採用候補へ進める。既存の「Product Finderを正式ソースとしない」方針は維持する。
- 決定: Product API確認結果は「Keepa JPでASIN・title・category等の商品データが確認できた」と表現する。Amazon.co.jpの現在のlive page、販売中、在庫、購入可能性を確認済みとは表現しない。
- 決定: `resolver_title`列は維持し、実在するResolver入力値がある場合はその値を保存する。実在するResolver入力値がない新規Keepa商品では、Category AI Benchmark V1 Sourceに限り空文字`""`を正式に許容する。Keepa titleのコピー、推測補完、NULLとの意味混在を禁止する。この限定判断はResolver正式仕様または他工程のprovenance要件を変更しない。
- 決定: EASY / MEDIUM / HARDの4 / 4 / 2、同一brand最大2、同一leaf最大4、複数Product Typeは多様性確保の目標とする。目標未達を黙って大幅緩和せず報告する一方、100件作成を不必要に長期化させる反復取得は行わない。商品選定にLuna / Terra / Sol、過去Prediction、Category AI Benchmark結果を使用しない。
- 決定: 既存の汎用Keepa clientは変更せず、固定10 genre / 32 leafのBenchmark専用runnerを追加する。retry 0、concurrency 1、自動fallbackなし、page 0を全leafで先行、不足leafだけpage 1を1回、選抜候補だけProduct確認、responseごとの実測`tokensConsumed`、request前token予約、hard cap 1,140 tokens / 77 requests、partial artifact保存を必須とする。page 1を使用した場合はASINリスト、取得時刻、leaf ID、page、selection条件とhashを固定する。
- 境界: 専用runnerはproduction SQLiteを使用・変更せず、API key、token残高値、raw responseを保存・表示しない。残高は実行前にmemory上でhard cap充足可否だけを判定し、artifactにはbooleanだけを残す。OpenAI API、正式Category Mapper、Resolver、Expansion、Guardrail、Brand、Listing、Prompt V1、Traversal、model profileを変更しない。今回の承認はlocal実装とFake / Mock検証までで、実Keepa API、Benchmark CSV、100商品Source確定、commit、push、PR、mergeは含まない。
- 確認事実: 専用runnerとFake transport testsをlocal実装し、seed確認、Category Lookup batch、Finder page 0 / 不足leafだけpage 1、ASIN・既存35・smoke 5・seed除外、Product batch、family / identifier重複除外、有効pool不足停止、token台帳、hard cap、no-fallback、partial保存、`resolver_title=""`、secret非保存の11 testsをPASSした。通常mock経路は617 tokens / 42 requestsである。実Keepa API、OpenAI API、production SQLite writeは0であり、mock成功をKeepa契約または実商品確認と扱わない。
- 理由: Product Finderの責務を候補発見に限定し、正式Source採用をProduct確認後へ分離しながら、API費用、無限追加取得、fallbackによる条件変化、secret漏洩を機械的に防ぐため。
- 再検討条件: 固定seed / category / Finder条件が現Keepa契約で成立しない、実測tokenが予約値を超える、page 1後も必要poolを確保できない、多様性目標を大幅に外れる、またはhard cap内で実行できない場合。その時点のpartial結果と代替案を報告して停止し、別endpointや条件緩和を自動実行しない。

## DEC-0059 — 電気ケトルseedのAmazon root計画だけを最小修正する

- 日付: 2026-09-12
- 背景: オーナー承認済みの実Keepa候補取得は、32 seed一括Product確認後に`B0CHHYQHGP`の`SEED_CATEGORY_MISMATCH`で正常停止した。Finder、Category Lookup、候補Product確認には進まず、runnerはraw responseを保存しない契約のため、実応答のroot / leaf / path値そのものはpartial artifactから再現できない。
- 確認事実: 事前計画はAmazon root `124048011`、leaf `16245081`、path `生活家電 > 小型家電 > 電気ケトル`だった。公開Amazonカテゴリの補助確認では、同ASINは電気ケトル商品であり、leaf `16245081`はroot `3828871`のHome & Kitchen配下に表示される。商品種別が当初目的の電気ケトルから外れたEvidenceはない。これは保存済みKeepa実応答の完全復元ではなく、次回seed確認で再検証する計画値である。
- 決定: A対応とし、`B0CHHYQHGP`は維持する。当該planだけAmazon rootを`3828871`、表示pathを`ホーム＆キッチン > 家電 > キッチン家電 > 電気ケトル`へ修正し、leaf `16245081`は維持する。他31 seed / plan、Finder条件、Product確認条件、除外、選抜、runner logicは変更しない。
- 境界: resume機能、fallback、追加endpoint、他seed再調査、別seed選定を行わない。通常617 tokens、hard cap 1,140 tokens / 77 requests、retry 0、concurrency 1を維持する。今回の修正工程ではKeepa / OpenAI / Shopee APIを追加実行せず、production SQLiteを使用・変更しない。実Keepa再実行は別途オーナー承認を得る。
- 理由: 商品種別とleafを維持したまま、rootとして扱っていた中間node `124048011`を実際の上位rootに合わせる最小変更でStop Conditionの原因を解消し、runner作り込みや条件変更を避けるため。
- 再検討条件: 次回実Keepa seed確認で`B0CHHYQHGP`がroot `3828871`かつleaf `16245081`として確認できない、または別のseed / category mismatchが発生した場合。その時点で再びpartial artifactを保持して停止し、自動修正しない。

## DEC-0060 — Seed Product 1 responseから32 planを一括診断する

- 日付: 2026-09-12
- 背景: Seed Product APIは32 seedを1 batchで返すが、従来runnerはplan順の最初のmismatchで検査を終了していた。このためplan 13、plan 14のroot mismatchを1件ずつ発見し、同じ32-token requestを反復した。費用・requestを増やさず、全seedの不一致を一度に確認する必要がある。
- 決定: Seed Product response取得後は全32 planについて、plan番号、genre、ASIN存在、title存在、expected / actual root、expected / actual最深leaf、root / leaf一致、status、安全に取得できたcategory pathを派生診断として保持する。全件検査後、1件でも欠損、title欠損、root / leaf mismatchがあれば診断全体を`seed_diagnostic.json`へ保存し、Category Lookup / Finder / 候補Product確認前に停止する。
- 決定: mismatchを根拠とする自動plan修正、別seedへの差替え、fallback、resume、追加requestを実装しない。plan 14 `B099242274`のroot `3828871`は修正候補として保持し、32 seedの実一括診断後に他のmismatchとまとめて別判断する。今回の変更でleaf plan値は変更しない。
- 確認事実: Mockで全32件一致時はSeed ValidationがPASSして既存次工程へ進むこと、plan 5 / 20が不一致の場合は両方を診断へ保存し、最初の不一致後もplan 32まで検査したうえでseed Product 1 request / 32 tokensだけで停止することを確認した。Seed runner 13 tests、Category AI関連55 testsは既存Python 3.13環境でPASSした。
- 境界: Finder条件、Product API条件、retry 0、concurrency 1、自動fallbackなし、通常617 tokens、hard cap 1,140 tokens / 77 requests、Category AI Core、Prompt、OpenAI関連、正式Keepa client、production SQLiteを変更しない。今回の工程では実Keepa / OpenAI / Shopee API、commit、push、PRを実行しない。
- 理由: 既に支払った1 batchの応答を全件検査し、安全なFinder前停止を維持したまま、同じseed requestの反復だけを除去するため。
- 再検討条件: 実一括診断でProduct response自体が不完全、categoryTreeから最深leafを安全に導出できない、または診断artifact契約を満たせない場合。その時点でpartial artifactを保持して停止し、自動修正しない。

## DEC-0061 — Category AI Benchmark V1のHard StopとDiagnostic運用を分離する

- 日付: 2026-09-12
- 背景: Category AI Benchmark V1は正式Category Mapper、main、production SQLite、Shopee書込APIから隔離した実験branchである。taxonomy mismatch等を1件ずつ停止・承認・再実行すると、同じAPI requestと管理更新を反復し、Minimum Beta投入までを不必要に長期化させる。秘密情報、費用上限、外部API異常、正式系への影響は即時停止を維持しながら、通常のデータ品質問題は一括診断する運用が必要になった。
- 決定: Hard Stopは、API key・秘密情報の漏洩懸念、production SQLite / main / 正式Category MapperまたはGit変更禁止範囲への変更、Keepa / OpenAI token・cost hard cap超過見込み、HTTP / API異常・429・認証異常、未承認endpoint・fallbackの必要、データ・schema破損とする。該当時は安全なpartial artifactだけを保持して即時停止し、後続requestへ進まない。
- 決定: seed root / leaf mismatch、古いAmazon taxonomy、variant / family重複、candidate不足、genre内の商品構成偏り、difficulty / brand / leaf比率未達はDiagnosticとする。単独では即時停止せず、当該工程の対象全件について可能な限り収集する。承認済み条件内で安全かつ決定的に処理できるものだけを処理し、安全に自動修正できない事項を一覧化する。
- 決定: DiagnosticによりFinder等の次工程の前提条件を満たさない場合は、診断完了後に一度停止してまとめて報告する。個々のtaxonomy mismatchごとに「停止、文書更新、承認、再実行」を繰り返さない。DEC-0060の32 seed一括診断はこの運用に適合し、全seedを検査した後、mismatchがあればFinder前で一度停止する。
- 決定: `CURRENT_WORK.md`、`DECISION_LOG.md`、`CONTEXT_SNAPSHOT.md`の通常更新は、Benchmark runner完成、100商品Source完成、Gold Truth完成、100商品model比較完成、Category Mapper統合判断のマイルストーン単位を原則とする。Hard Stop、安全・integrity上の重大変更、承認境界そのものの変更は例外とする。
- 境界: 本決定は外部APIの新規実行承認、token / request / cost capの変更、endpoint・fallbackの追加、production系への統合、commit / push / PRを意味しない。現在の32 seed実Keepa一括診断は引き続き別途オーナー承認待ちとし、今回runner logic、leaf plan、Prompt、Category AI Coreを変更しない。
- 理由: 本当に即時停止すべき安全・費用・integrity事象と、Benchmark作成中に通常発生するデータ診断を分離し、保護境界を弱めずに反復作業と管理負荷を減らしてAI Category判定のMinimum Beta投入を早めるため。
- 再検討条件: Diagnosticとして続行した事象が秘密情報、費用上限、API健全性、schema・データintegrity、正式系への影響へ波及することが判明した場合、または一括診断では次工程の前提を安全に判定できない場合。その事象はHard Stopへ昇格して扱う。

## DEC-0062 — Keepa実値へtaxonomyを修正しBenchmark 100商品Sourceを固定する

- 日付: 2026-09-12
- 背景: DEC-0060の実Seed一括診断で32件中29件が一致し、plan 14、15、23の3件に古いAmazon taxonomy由来のrootまたはleaf不一致が確認された。オーナーは3 seedの商品Genre上の役割を維持し、Keepa実返却値へまとめて最小修正した後、承認済みrunnerで100商品Source完成まで進めることを承認した。
- 決定: plan 14 `B099242274`はrootを`3828871`へ、plan 15 `B0CKWQQXLB`はrootを`3828871`、leafを`15691411`へ、plan 23 `B0F2NZL4FK`はleafを`10395289051`へ変更し、実Category pathも診断値へ合わせる。seed差替え、resume、validation skip、fallbackは追加しない。修正後planが保存済み32件診断のactual root / leafと全件一致することをlocal確認した。
- 確認事実: 固定runnerをretry 0、concurrency 1、fallbackなし、hard cap 1,140 tokens / 77 requestsで実行した。seed Product 32 tokens / 1 request、Category Lookup 4 tokens / 4 requests、Finder page 0 352 tokens / 32 requests、候補Product 229 tokens / 5 requestsで合計617 tokens / 42 runner requestsだった。page 1は0、Hard Stopは0。Finderは32 leafから1,600 ASIN entryを取得し、選抜229件をProduct確認した。Keepa JPでASIN、title、category等の商品データを確認できた候補は224件、rejectはleaf mismatch 2、substantial duplicate 1、duplicate family 2だった。これはAmazon.co.jpの現在のlive page、在庫または購入可能性の確認ではない。
- 決定: 既存local 6件と新規Keepa 94件を、AI Prediction・Goldを使わず10 genre x 10へ選定し、100 unique ASINの`BENCHMARK_100_SOURCE_V1.csv`を固定する。Source SHA-256は`743b32eb2c8e7835b4ad2ada8cdbf0ca7cbbdb453320c024322af6c1b766ee48`。新規94件は`resolver_title=""`とし、Keepa titleをコピーしない。既存local 6件は実在する保存済み入力値を保持する。
- 確認事実: 同一brand最大2と、IDを確認できるleaf最大4は全genreで達成し、制約緩和または追加取得は不要だった。既存local 5件は保存Evidenceにleaf IDがないためleaf比率の完全検証対象外と明示する。difficulty 4 / 4 / 2は商品選定時に推測せず、100件を`UNASSESSED`としてGold Truth工程へ引き継ぐ。Category AI source parserで100件、100 unique case ID、100 unique ASIN、genre各10、新規94件のblank resolver titleを再検証し、関連56 testsをPASSした。
- 境界: Product Finderは本Benchmarkの候補発見専用であり、正式Source採用はProduct確認後に限定する。OpenAI / Shopee API、Gold Truth作成、Category Mapper統合、production SQLite、commit、push、PRは実行しない。追加Keepa request、Source差替え、model Benchmarkは別工程・別承認とする。
- 理由: 実データで確認したtaxonomyだけを修正し、diversity目標を過剰な追加取得なしで満たしながら、モデル比較の固定入力を早く完成させるため。
- 再検討条件: Source hash不一致、重複またはprovenance不整合が判明した場合、Gold Truth作成で商品Evidenceが不足した場合、または既存localの未確認leaf IDを比較設計上必須とする判断が生じた場合。Source変更は既存hashを上書きせず別versionとして扱う。

## DEC-0063 — family / variant候補5組を解消してBenchmark Source V1.1を固定する

- 日付: 2026-09-12
- 背景: Source V1のGold Review Packet作成時、異なるASINながら同一product familyまたはvariantとしてBenchmark上の重みが重複する可能性がある5組を検出した。オーナーはGold Truth確定前に各組を1件へ削減し、追加APIなしで保存済みverified unused candidate poolから同Genreの商品へ差し替えることを指示した。
- 決定: V1は監査証跡として上書きせず保持する。B100-022、B100-065、B100-073、B100-074、B100-091を残し、B100-025、B100-068、B100-079、B100-077、B100-095のcase枠を、それぞれ`B0FR8LBTTF`、`B0GVY7TCCM`、`B0FKGNS9F9`、`B0BTD6RCJV`、`B083W2XW3V`へ差し替える。差替えは同Genre、V1未採用、既存35件・smoke 5件と非重複、verified family key非衝突を必須とし、brandと確認可能なAmazon leafの多様性目標を維持する。
- 確認事実: `BENCHMARK_100_SOURCE_V1_1.csv`は100 rows、100 unique case ID / ASIN、10 genre x 10、既存35件・smoke 5件とのASIN重複0。新規94件の`resolver_title=""`と既存local 6件の保存値を維持し、verified family key衝突0、exact title重複0、再監査で新規近似family候補0、同一brand最大2、確認可能なAmazon leaf最大4を確認した。Source V1.1 SHA-256は`a128aa7b5cad87e08397bdc09e0b2cdd656270c00be025b58d4f2e2419cccae0`。
- 決定: Source V1基準のGold Review Packetは正式採用せず、V1.1基準でReview PacketとTruth Reviewを再生成する。正式Gold欄`expected_category_id`、`expected_category_path`、`truth_status`、`truth_note`は全件空欄とし、Codex候補をGold Truthへ昇格しない。review confidenceはHIGH 74 / MEDIUM 21 / LOW 5、candidate statusはCONFIRMED 84 / ABSTAIN 5 / NEEDS_REVIEW 11で、人間レビュー待ちとする。
- 境界: 既存verified pool以外を使用せず、Keepa / OpenAI / Shopee API、production SQLite、正式Category Mapper、Gold Truth確定、model Benchmark、commit、push、PRを実行しない。AI Prediction、過去Benchmark結果、Mapper推薦を商品選定またはGold候補の根拠へ使用しない。
- 理由: 同系統商品の反復で特定Product Typeを過大評価することを避けながら、追加取得やDataset全体の作り直しをせず、比較可能な100商品Sourceを早く確定するため。
- 再検討条件: V1.1 hash不一致、追加の実質family / variant重複、Source / Gold Review間のASIN・case不整合、正式Gold欄への事前混入、または人間レビューで商品Evidence不足が判明した場合。Source変更が必要ならV1.1を上書きせず新versionとして扱う。

## DEC-0064 — 人間レビュー済みGold Truth V1.1を92 CONFIRMED / 8 ABSTAINで固定する

- 日付: 2026-09-12
- 背景: Source V1.1とGold Review Packet V1.1についてオーナー確認が完了し、全100件の正式Goldをmodel比較前に固定する条件が整った。Gold確定中はPredictionを参照せず、Review Packetで採用したCategoryを再推測しないことが条件である。
- 決定: B100-001、B100-004、B100-005、B100-032、B100-035、B100-038、B100-054、B100-079の8件を`ABSTAIN_REQUIRED`とし、expected Category ID / pathを空欄にする。各truth noteにはReview Packetの候補・代替Categoryと人間判断に基づく、一つのleafへ安全に確定できない理由を記録する。
- 決定: 残り92件を`CONFIRMED`とし、Review Packet V1.1のcandidate expected Category ID / pathをそのまま正式expected Categoryへ固定する。B100-012、B100-018、B100-036、B100-039、B100-067、B100-075、B100-078、B100-087も`NEEDS_REVIEW`または`ABSTAIN_CANDIDATE`を正式statusへ持ち越さず、人間確定どおり`CONFIRMED`とする。
- 確認事実: 正式Goldは100 rows、100 unique case ID / ASIN、Source対応100/100、CONFIRMED 92、ABSTAIN_REQUIRED 8、UNCONFIRMED 0。CONFIRMED全件は固定PH Catalog上の実在leafでID / pathが一致し、ABSTAIN全件はexpected ID / pathが空欄である。Source V1.1のbytesと全Source field差分は0で、Source SHA-256は`a128aa7b5cad87e08397bdc09e0b2cdd656270c00be025b58d4f2e2419cccae0`。Gold Truth SHA-256は`1faf1365ac0bb83566ea0347c12b9505895fcb9fed2cf4e5ba3964e62e28e93b`、Catalog normalized hashは`d694271a244bf743547d8cf9b1711f14618032954bae2cc81645f35ea65d72e6`。
- 境界: Source V1 / V1.1、旧Review Packet、旧Truth Reviewは上書き・削除しない。OpenAI / Keepa / Shopee API、Luna / Terra / Sol、過去Prediction、smoke Prediction、model Benchmark、production SQLite、正式Category Mapper、commit、push、PRを実行しない。現行`parse_gold_csv`はpositive expected Category IDのGoldだけを扱い、ABSTAIN_REQUIRED行をまだ受理しないため、model比較前に採点契約とloader対応を別工程で確認する。
- 理由: model出力をGold作成へ混入させず、人間が確定した正解と必要なABSTAINを不変hashで先に固定し、公平なmodel比較の基準を成立させるため。
- 再検討条件: Source / Gold hash不一致、case対応不整合、CONFIRMED leafのCatalog不一致、ABSTAIN expected欄への値混入、またはmodel比較の採点契約でABSTAIN_REQUIREDの扱いが未定義の場合。SourceまたはGoldを変更する必要があれば既存versionを上書きせず新versionとして扱う。

## DEC-0065 — ABSTAIN_REQUIRED採点とLuna / Terra比較契約を固定する

- 日付: 2026-09-12
- 背景: Gold V1.1は92件の`CONFIRMED`と8件の`ABSTAIN_REQUIRED`を含むが、既存loaderと評価はpositive expected Category IDだけを扱い、正式100件比較を採点できなかった。GoldをPrediction生成へ漏らさず、Category exactnessと必要なABSTAINを同時評価する契約が必要になった。
- 決定: 正式Gold loaderは`CONFIRMED`でexpected leaf ID / pathを必須かつ固定Catalog一致、`ABSTAIN_REQUIRED`で両欄を空必須とし、`UNCONFIRMED`と未定義statusを拒否する。Source / Goldは全case ID・ASINの一致と重複なしを必須とする。
- 決定: `CONFIRMED`はexact SELECTを`CORRECT_SELECT`、別leafを`WRONG_CATEGORY`、ABSTAINを`FALSE_ABSTAIN`とする。`ABSTAIN_REQUIRED`はABSTAINだけを`CORRECT_ABSTAIN`、いずれのleaf SELECTも部分点なしの`OVERCONFIDENT_SELECT`とする。Provider / API / Traversal異常は`FAILED`とし、ABSTAINへ合算しない。
- 決定: 主要指標は100件全体を分母とする`overall_success_rate`とし、`confirmed_exact_accuracy`、`abstain_accuracy`、`select_precision`、各outcome件数、token、cost、API call、latencyをmodel別に集計する。FAILED除外のcompleted-decision success rateは参考値として区別する。
- 決定: 処理順をSource、全Prediction個別hash、Prediction batch hash、Gold load、Evaluatorとする。Gold object、expected Category、truth statusをCategory AI Core、Provider、Prompt serializer、Traversal requestへ渡さない。比較対象は`gpt-5.6-luna`と`gpt-5.6-terra`の2つだけとし、model ID以外のrequest profile、Source、Gold、Catalog、Prompt、Traversalを比較完了まで変更しない。実行順はLuna 100件、結果hash固定、Terra 100件、結果hash固定、Gold評価とする。
- 確認事実: 正式100件fixtureをCONFIRMED 92 / ABSTAIN_REQUIRED 8として読み込み、全outcome、loader矛盾、Source / Gold identity、重複、Gold非混入、batch hash、model別KPIをFake Provider / offline testsで確認した。Category AI関連72 testsをPASSした。Source SHA-256は`a128aa7b5cad87e08397bdc09e0b2cdd656270c00be025b58d4f2e2419cccae0`、Gold SHA-256は`1faf1365ac0bb83566ea0347c12b9505895fcb9fed2cf4e5ba3964e62e28e93b`、Catalog hashは`d694271a244bf743547d8cf9b1711f14618032954bae2cc81645f35ea65d72e6`、Prompt hashは`7fb5dfb95f3c9293b96acd1c50fbb382e12e4f715d0e77d0d7e93da3f587983d`。
- 確認事実: 2026-09-12のOpenAI公式model docsでLuna $0.20 / $0.02 / $1.20、Terra $2.00 / $0.20 / $12.00（input / cached input / output、各1M tokens）とcache write 1.25倍を確認し、既存price configと一致した。最大5 traversal stepsから各model 500 requests、2-model 1,000 requests。最大serialized requestを全requestへ適用する保守上限はLuna US$1.585075、Terra US$15.852、合計US$17.437075。
- 境界: 今回はOpenAI / Keepa / Shopee API、Source / Gold / Prompt / Traversal、production SQLite、正式Category Mapper、commit、push、PRを変更・実行しない。実API比較は別途オーナー明示承認までHOLDする。
- 理由: Goldを事前に固定した公平なblind predictionを維持しながら、無理にleafを選ぶ挙動を明示的に罰し、Category正解率、適切なABSTAIN、失敗、費用を同じ100商品E2Eで比較するため。
- 再検討条件: 固定hashまたはprofile共通条件の不一致、公式料金とprice configの不一致、API key・秘密情報漏洩懸念、最大cost / request cap超過見込み、HTTP / API / schema / response model / service tier異常、または全100件のPrediction batchを安全に固定できない場合。該当時は後続modelまたはGold評価へ進まず停止する。

## DEC-0066 — Category AI Benchmark V1を完了しLunaを候補提示モデルに採用する

- 日付: 2026-09-13
- 背景: 固定Source V1.1、Gold V1.1、PH Catalog、Prompt V1、Traversal V1、共通request条件を変更せず、Luna / Terra各100商品の実API比較を完了した。Minimum Betaへ進むため、精度、費用、安全境界を合わせてモデル選定を確定する必要がある。
- 確認事実: Lunaはoverall 81%、CONFIRMED exact 79/92（85.87%）、Hobbies & Collections 0/10、100商品の実コストUS$0.12669125。Terraはoverall 82%、CONFIRMED exact 79/92（85.87%）、Hobbies & Collections 0/10、実コストUS$1.202226で、Lunaの約9.5倍だった。両モデルともFAILED / Hard Stopは0だった。
- 決定: Category Mapper Minimum BetaのCategory候補提示モデルとして`gpt-5.6-luna`を採用する。Terraは精度差が小さい一方で約10倍の費用を要したため今回は不採用とし、Solは検証しない。
- 決定: AIの責務はCategory候補提示に限定し、自動Category確定を許可しない。`manual_review_required`、`listing_ready`、既存Safety、Category Confirmationその他の安全機構を維持し、AI predictionやconfidenceだけで解除・通過・準備完了にしない。
- 決定: Hobbies & Collectionsは両モデルとも0/10だった既知弱点として、Minimum Betaで特に手動確認する。Prompt V1、Traversal V1、Hobbies固有改善は今回行わず、実運用後に頻度・被害・運用負荷上の真のボトルネックと確認できた場合だけ別Version・別判断で改善する。
- 境界: 本決定はCategory Mapper統合の実装、追加OpenAI API実行、Prompt / Traversal変更、Safety / Brand / Resolver変更、自動Category確定、自動出品、push、PR、mergeを許可しない。Mapperへの最小統合は新規Codexタスクで開始する。
- 理由: LunaとTerraの全体精度差は1ポイント、CONFIRMED exactは同率であり、Hobbies弱点も共通だった一方、Lunaは実コストが大幅に低い。人間確認を残すMinimum Betaの候補提示用途では、Lunaが費用対効果に優れるため。
- 再検討条件: Minimum Beta実運用でCategory候補品質、Hobbies、手動確認負荷、失敗率または費用が真のボトルネックになった場合。その時点で実運用Evidenceに基づき、Prompt / Traversal改善、モデル再比較その他の対応を別タスクで判断する。

## DEC-0067 — Category Mapperへ独立AI候補としてMinimum Beta最小統合する

- 日付: 2026-09-13
- 背景: DEC-0066で`gpt-5.6-luna`を候補提示モデルに採用した。最新mainとBenchmark V1 commitが共通親から分岐したsiblingだったため、dirtyなBenchmark worktreeを避け、最新mainを基点にCategory AI Coreを安全に取り込んだ上で、既存Category Mapperの人間確認と出力安全条件を維持する最小統合が必要だった。
- 決定: 最新`origin/main` `73b81a1032f24652eed29cd1d2f85872d0496727`からclean branch `codex/ph-category-mapper-ai-minimum-beta`を作り、Benchmark V1 `7fe9712b914c473c3ab81c7b99e3f5bc9442a7ae`をcherry-pickした統合commit `c2031ad239a54bd9dc605915e66ce9c1a8eab22b`を実装baseとする。正本文書競合は発生せず、最新mainとCategory AI Coreの双方を保持する。
- 決定: AI Predictionは既存Recommendationを書き換えず、session内の独立候補として保持する。Category未確定行だけを対象とし、確認済みCategoryはProviderへ渡さない。model選択UIを作らず`gpt-5.6-luna`に固定し、明示ボタン押下までProvider生成・API呼出しを行わない。
- 決定: Category Mapperのlocal PH Category Tree全体を目的限定interfaceで読み、既存Category AI CoreのCategoryCatalogを構築する。Predictionは現在catalogの実在ID、path一致、有効leafを満たす場合だけ候補表示し、ABSTAIN、FAILED、catalog不整合は採用不可とする。商品単位失敗でbatch全体を止めず、該当行の既存Recommendationと手動経路を維持する。
- 決定: group採用は全memberが同じ有効leafへ一致した場合だけ表示し、人間が採用した時点で既存`apply_manual_category()`へ渡す。Predictionやconfidenceだけでは`category_is_confirmed`、`manual_review_required`、`listing_ready`を変更しない。採用後は既存どおりBrand未確定へ戻してBrand確認へ進む。Hobbies & Collections候補にはBenchmark弱点警告を表示する。
- 確認事実: 外部APIなしでCategory AI関連78 tests、Category Mapper関連60 tests、全pytest 1148 testsがPASSした。変更Python構文と`git diff --check`もPASSした。初回全pytestの1 failureは新worktreeに`.venv`がない環境要因で、Git除外済みjunction接続後に当該testと全回帰を再実行してPASSした。
- 境界: Prompt V1、Traversal V1、Category AI Core、`category_mapper.py`本体、Brand、Safety、Guardrail、Resolver、Expansion、Listing Tool、自動出品は変更しない。実OpenAI / Keepa / Shopee API、実商品処理、push、PR、merge、deployは行わない。local実装・mock検証完了を実データ有用性、ユーザー受入、Minimum Beta正式完成とは扱わない。
- 理由: AIなしの従来経路を残し、API費用と障害を明示操作へ隔離しながら、候補の有用性だけを早く実務評価できる形にするため。Category確定・Brand確認・出力準備の既存安全条件を変更しないことで、AI誤分類が自動出品準備へ進む経路を作らない。
- 再検討条件: mock検収後に実APIスモークを行う明示承認が得られた場合、実利用で候補品質・Hobbies・失敗率・費用・group不一致が真のボトルネックと確認された場合、または正式PH catalogからCategoryCatalogを安全に構築できない具体例が確認された場合。改善は既存Prompt / Traversalを黙って変更せず別Version・別判断とする。

## DEC-0068 — Category Mapper AI Minimum Betaのlive smokeを技術PASS・実務受入候補PASSとする

- 日付: 2026-09-13
- 背景: DEC-0067のlocal実装・mock回帰検証後、オーナー承認済みの実商品最大3件、`gpt-5.6-luna`限定、総コストUS$0.05以下、retry禁止という条件で、実際のPH Category Mapperにおける候補取得、人間確認、Category採用、Brand確認までのMinimum Beta経路を確認した。
- 確認事実: PH Gate ELIGIBLEかつCategory未確定の実商品3件を1件ずつ実行し、3件とも`COMPLETED`、retry 0、実API総コストUS$0.00332790だった。既存RecommendationとAI候補は並列に保持され、AI Predictionだけでは`category_is_confirmed=False`、`manual_review_required=True`、`listing_ready=False`を維持した。人間採用後だけ既存Category確定経路へ入り、Brand未確認中は`listing_ready=False`を維持した。Hobbies & Collectionsはlive該当なしで、弱点警告はmock確認済みだった。
- 決定: Category Mapper AI Minimum Betaの技術的live smokeを`PASS`、実務受入候補を`PASS`、blockerなしとする。3商品の結果を新しいCategory精度指標にはせず、Benchmark V1の評価と既知のHobbies弱点を置き換えない。実装commitは`64fdce3c2b8745fbdf908db0d7be641a65380372`とする。
- 維持: AIは候補提示だけを担当し、AI単独のCategory確定、manual review解除、`listing_ready`化を許可しない。Category採用は人間操作時だけ既存経路へ渡し、Brand確認、Safety、Guardrail、Resolver、Expansion、Listing Tool、自動出品の境界を変更しない。
- 境界: 本決定はMinimum Betaの正式main受入、push、PR、merge、追加OpenAI API実行、自動出品を許可しない。最終受入は新規Codexタスクで本記録と実装commitを確認した上で、オーナーとChatGPTが判断する。
- 理由: 実APIと実画面でも、AI候補の有用性を人間確認へ限定し、既存のCategory・Brand・出力安全条件を壊さない最小経路が、承認済み費用上限内で成立したため。
- 再検討条件: 実務投入後に候補品質、Hobbies、手動確認負荷、ABSTAIN / FAILED、group不一致、API費用または操作性が実際のblockerとなるEvidenceが得られた場合。改善は先行せず、別Version・別判断とする。

## DEC-0069 — Resolver evidenceとPH Gate handoffの重複ASIN境界を固定する

- 日付: 2026-09-14
- 背景: 実Owner Flowで、同一Amazon ASINが複数の`source_id` / `input_title`に対応するResolver evidenceをPH Gate入力へそのまま渡すと、Gateが求める商品ASIN単位と衝突することを確認した。Evidenceのprovenance保持とGate入力の一意性を両立させる恒久境界が必要である。
- 決定: Resolver evidence層では、重複ASIN、元の順序、`source_id` / `input_title`等のprovenanceを保持する。Resolverの証拠を商品単位へ破壊的に集約しない。
- 決定: PH Gate handoff境界でのみstable ASIN normalizationを行い、Resolver evidenceからPH Gate CandidateとSafety sidecarを商品ASIN単位へ統合する。duplicate consolidationは正常な境界変換であり、UNKNOWN / ERROR等による除外件数に含めない。
- 決定: 同一ASINのSafety Evidenceが競合する場合は一方を推測採用せずfail-closedで停止する。信頼できるSafety Factが一方にだけある場合の保持は許容するが、Safety条件、Gate判定、sidecar bindingを緩和しない。
- 確認事実: bugfix commitは`a0fd8593cd8606845f0c68af66f2006bb8a6e7e6`。実画面でResolver evidence 37行から26 unique ASIN、duplicate consolidation 11行、未確認等による除外0、PH Gate ELIGIBLE 18 / REVIEW 6 / EXCLUDE 2、Category Mapper 18商品、Category AI追跡18件の成立を確認した。Luna送信15件はCOMPLETED 15、確認済みCategoryのため送信前skip 3、ABSTAIN 0、FAILED 0で、欠落・重複・ASIN差替えはない。全18件の`manual_review_required=True`と`listing_ready=False`を維持し、全pytest 1155件がPASSした。
- 境界: 本決定はResolver evidenceの保存契約、Safety / Guardrail仕様、Category AI Core、Category Mapper AI、自動Category確定、`manual_review_required`、`listing_ready`、外部API承認ポリシーを変更しない。bugfixはbranch上の検証済み成果であり、main統合前に正式成果と扱わない。
- 理由: 行単位の証拠を失わずに、Gate以降の商品単位不変条件を満たし、Safetyの競合だけは見逃さず停止できるため。
- 再検討条件: Resolver evidenceのprovenanceを保持できない例、stable normalizationでSafety sidecarのASIN集合または値が不一致となる例、または同一ASINで信頼できるSafety Evidenceが競合する実例が確認された場合。別Version・別判断で扱い、自動緩和しない。

## DEC-0070 — PH Resolverの手動retry運用とShopee URL起点Evidenceの優先順位を固定する

- 日付: 2026-09-15
- 背景: PH Minimum Betaをformal mainで約60件のShopee由来タイトルに少量実務利用し、初回でAIが明示的に`UNKNOWN`を返した28 sourceについて、現行retryの実務上の救済価値と追加開発の費用対効果を確認した。現行コードには、AI明示`UNKNOWN`だけをretry対象とする抽出、検索タイトル、A retry promptが存在する。
- 確認事実: 以下はオーナー提示の実務検証結果であり、今回Git・テストで再実行した精度評価ではない。固定12商品の比較は、A（現行retry）が`EXACT_SUCCESS` 4、`VARIANT_ONLY_SUCCESS` 3、`MISMATCH_ONLY` 2、`UNKNOWN` 3、B（複数検索表現追加）が4/3/0/5、C（Bに日本語検索追加）が4/4/0/4だった。`MATCH`と`VARIANT_MATCH`を分け、後者を完全一致に含めないDEC-0002を維持する。
- 確認事実: 同じ12商品ではA retryの5/5/2分割は有用候補到達7/12、12件一括は少なくとも8/12で、検索結果には入れ替わりがあった。同一28 UNKNOWNのA retryでは、Web Search明示ONはcandidate source 15/28、OFFは20/28だったが、候補数には人間確認済み`MISMATCH`の再出力も含まれ、再検索ごとの非再現性があった。Web Search OFFでのA retryは1回目にcandidate source 20/28、残り`UNKNOWN` 8、同条件の2回目は追加候補2/8、残り6だった。追加2件は人間確認で各1件の`MATCH`と`VARIANT_MATCH`だった。28件の候補全件を同一性監査していないため、候補到達件数をaccuracy、recallまたは正解件数として扱わない。
- 決定: Resolverの成功目的を`UNKNOWN`ゼロではなく、少ない人手で十分な有用種ASINを確保することとする。現行A retryを維持し、標準は原則1回、2回目は商品価値・必要性に応じた手動救済、3回目以降は標準化しない。限界効用が低い`UNKNOWN`は許容し、次の商品候補へ進む。
- 決定: B promptを標準採用せず、CはAで`UNKNOWN`となった日本商品の人間による任意fallbackに限定する。D/E/F等を含む追加prompt探索を継続せず、Cへの全面置換もしない。
- 決定: Web Search明示ONを標準必須条件にしない。Web Search OFFが常に優れるとは一般化しない。5件等への自動小分け、retry自動化、retry回数の自動ループを実装しない。適切な最大batch title数は未確定のまま残し、実務上のblockerが確認された場合だけ再検討する。
- 決定: Shopee検索URLから商品ページ、variation等のEvidenceを経てAmazon商品を特定する方式は、技術的不可能との判定ではなく、開発・保守コスト、売上寄与未確認、1万商品投入の遅延リスクを踏まえたHOLDとする。Resolverの目的はShopee listing完全再現ではなく有用種ASINの確保であり、タイトル型Resolverが実務上不足し、売れ筋商品のvariation展開等が人手負荷または売上機会のblockerと確認された場合だけ再検討する。
- 境界: 本決定はResolver prompt、parser、UI、Guardrail、Category Mapper、Expansion、外部API、検索結果CSV、商品名・ASIN一覧、検索ログを変更・追加・保存しない。Web Searchの有効性、batch size最適値、候補到達率の精度指標化、URL起点方式の技術可否を確定しない。
- 理由: A retryには人間確認済みの追加有用候補という救済価値がある一方、比較結果は追加prompt、Web設定、分割、反復の一律最適解を支持せず、候補数だけでは品質を判断できない。小さい手動コピペ負荷を先行自動化せず、実利用の真のblockerへ開発投資を残すため。
- 再検討条件: 少量実務でA retryの手動負荷、残存`UNKNOWN`、検索結果の揺らぎ、batch size、またはvariation情報不足が、頻度・影響・売上機会を伴う実blockerと確認された場合。再検討は実データの範囲と人間同一性確認を分けた別タスクで行い、外部API実行や機能変更には別途承認を要する。

## DEC-0071 — SG Safety Baseline 40 Ruleをtitle限定REVIEWで固定する

- 日付: 2026-09-15
- 背景: PH Minimum Betaの少量実務を維持しながらSG Minimum Betaへ進む前に、現行SG Guardrailで未検出だった重大な規制疑義を、既存BLOCKや市場分離を緩めず人間確認へ止める必要がある。設計で列挙された候補は43ではなく40語句であり、formal mainのSG辞書との重複は0件、DROPは0件と確認済みだったが、設計結果はGit正本化されていなかった。
- 決定: `guardrails/risk_keywords_sg.csv`と`tests/test_guardrails.py`で固定した40行の8列値をSG Safety Baselineとする。全行を`action=REVIEW`、`match_field=title`、`match_type=contains`、`enabled=TRUE`とし、商品実体・用途・許認可等を語句だけでは確定しない。公式規制を根拠とする行と当社保守運用の`internal_rule`を`source_type`およびnoteで区別する。
- 確認事実: fetch後のformal main `2318f0cb6f94938afb288f83b1e8a18671ce1274`は設計baseと一致した。既存182行を順序・8列値とも変更せず40行だけ追加し、総222行、有効217行、正規化term重複0件となった。40語すべてでSG titleはREVIEW、brand / categoryだけでは不一致、新規Rule由来BLOCKは0、既存BLOCK同時一致ではBLOCK優先、加美乃素Penalty BLOCK維持、SG REVIEWはGateでELIGIBLEにならず、PHへの新Rule漏洩がないことを合成testで確認した。関連pytest 465件、全pytest 1199件、`git diff --check`をPASSした。
- 境界: 新規の広範囲BLOCK、既存BLOCKの緩和・削除・変更、SG brand辞書、matcher、Candidate schema、Gate優先順位、COMMON_BLOCK、PH辞書・PH処理、Resolver、Expansion、Category AI、Category / Brand、sidecar、自動出品、外部APIを変更・実行しない。本決定はbranch上のlocal実装であり、push、PR、merge、formal main受入、SG Minimum Beta全体の完成を許可または確定しない。
- 理由: 重大疑義をSAFEのまま流さず、名称一致だけで禁止商品本体と断定しない最小差分により、既存Penalty保護とPH実務運用を維持できるため。
- 再検討条件: 実務で過剰REVIEWまたは表記漏れが具体的Evidenceとして確認された場合、現行Shopee SG Policyまたはmatcher契約が変わった場合、もしくは商品Factに基づくCategory依存Safetyを別設計で開始する場合。既存BLOCKを自動降格せず、別Version・別判断として扱う。

## DEC-0072 — 管理基盤Ver2の正本・信頼・承認契約を採用する

- 日付: 2026-09-16
- 背景: Ver1のCURRENT_WORK中心契約はactive task等の長寿命状態混入、過去local branch依存、fresh clone再現性、Evidence binding、repository identity bootstrap、複数市場並行作業に未解決点があった。
- 決定: Revision 1と5 blockerを解消したRevision 2を管理基盤Ver2の実装仕様として採用する。競合時はRevision 2を優先する。
- 決定: GitHub owner証跡、repo外Trust Anchor、Owner Acceptance説明契約を採用する。Owner Acceptanceはmandatory technical gate完了後だけ要求し、非エンジニア向け9項目サマリーで事業判断を求める。hash、SHA、schema等の技術的正当性判断をownerへ要求しない。
- Migration: PHはACTIVE / ALLOWED / `ph.beta.operation` ACCEPTED。SGはINACTIVE / PAUSED / `sg.safety.baseline` ACCEPTED、Category / Brand / Handoff未成立、Minimum Beta未完成。MY / THはINACTIVE / NOT_STARTED。既存受入はLEGACY_ACCEPTANCEとして記録し、未実行のVer2 TESTを捏造しない。
- 保護: 未知・混合変更はSHARED_COREへfail-safeし、PH/SG protected capability gateを適用する。Governance mandatory checksはGitHub branch protectionとは独立して評価する。
- 境界: 製品runtime、SG Category / Brand / Handoff、MY / TH、live API、push、PR、merge、GitHub設定、実Trust Anchor設定を本決定だけで許可しない。
- Rollback: pre-Ver2 formal main `136958a1bf2493983b4413f7d231ee5adbd913bf`の対象pathへ通常のrevert PRまたは後続変更を保持した復旧差分で戻す。Ver1既知問題の復帰も明示する。
- 理由: fresh cloneで再現可能な信頼境界、決定的なConfig、独立Verifier、content-addressed Evidence、並行Task Contextを最小構成で成立させ、PH運用を維持しつつ複数市場変更をfail-safeに管理するため。

## DEC-0073 — 通常開発承認とformal main最終受入を二段階へ分離する

- 日付: 2026-09-16
- 背景: pushやDraft PRごとに承認待ちを置くと、mainを変更しない検証候補の公開、CI、reviewで得るべきEvidenceまで不必要に停止し、通常開発の反復を遅らせていた。
- 決定: 目的とscopeをオーナーが承認した通常タスクでは、local編集、local test、local commit、push、Draft PR作成、CI / checks確認、read-only reviewを一括で許可する。pushとDraft PRは検証可能な候補をGitHubへ公開する工程であり、formal mainへの採用承認ではない。
- 決定: formal mainへのmerge直前だけ、mandatory technical gate、現在対象にbindingしたOwner Acceptance Summary、オーナーの明示的な最終承認を必要とする。PR作成後にhead、scope、主要リスク、protected capabilityへの影響、Summary bindingが変われば、merge前に現在対象への受入を取り直す。
- 維持: Governance VerifierのHOLD / HARD_STOP、Protected Capability Gate、mandatory technical gateを通常開発承認で無効化・迂回しない。live API / 実商品、有料API・新規費用、deploy、GitHub設定、branch protection / ruleset、GitHub Actions secret / variable、実環境Trust Anchor、credential / secret、復元困難な削除、force push、大幅なscope変更は別承認のままとする。
- 理由: push / Draft PRはmainを変更せず、CI・reviewはmerge判断に必要なEvidenceを得る工程であるため。細かい承認待ちによる無意味なSTOPとCodex token消費を減らしつつ、formal mainへの最終採用判断と安全gateをオーナーとGovernanceに残すため。
- 再検討条件: Draft PR公開によるreview負荷、無承認scope逸脱、CI Evidenceの欠落、またはformal main受入での手戻りが実務上のblockerとなった場合。安全gateの緩和ではなく、Evidenceと承認境界を別タスクで再検討する。

## DEC-0074 — Community NGを国別共通Safety資産として正本化する

- 日付: 2026-09-17
- 背景: オーナー提供の最新CSVにはSG / PH / MY / TH / TW / VNの国別ASIN・ブランドNGと、国が特定できない列が混在していた。従来はSG辞書とPH V2へcommunity由来情報が重複し、国不明データの一部もSG runtimeへ入っていたため、市場境界、更新元、入力hash、正規化判断を一つの契約として固定する必要があった。
- 決定: guardrails/community_ng/をCommunity NGの正本とし、ASIN 46行、ブランド48 concept / 54 exact match行、source manifest 2行をversioned assetとして保持する。元CSVはGitへ追加せず、元ファイル名、2026-09-16提供日、SHA-256、入力件数、重複・除外・隔離・出力件数をmanifestへ固定し、repo外のオーナー提供Evidenceとして扱う。NG理由列は判定条件やruntime資産へ含めない。
- 決定: 国別ASINはmarketplace + 10文字ASIN完全一致、国別ブランドはmarketplace + NFKC / casefold / trim / 連続空白統一後の完全一致で常にBLOCKとする。G=SHOCKはcanonical key g-shockのG-SHOCK / G=SHOCK alias、グルマンディーズ / Gourmandiseは同一brand key、PHのBose商品群表現はブランドBose、SUNTORYのサプリメントは除外してSUNTORY全体BLOCKへ拡張しない。VNブランド列のB08DHKD9T4はASIN混入として隔離する。
- 決定: 国不明の224 recordはUNSCOPED / DEFERREDとし、どのmarketplace runtimeにも展開しない。SG辞書の旧community_report 85行（brand 47、keyword 38）とPH V2の旧community brand 13行は共通正本への移管に伴い削除する。Shopee brand list、SG Safety Baseline 40 REVIEW、own penalty、PH辞書、GABA / hemp V2は維持する。
- Runtime境界: この変更で共通資産を読むproduct runtimeはSG / PHだけとする。MY / TH / TW / VNは将来利用できるformal data assetに限り、product runtime、Gate、UI、workflowを開始しない。SG / PH間およびdata-only市場からの漏洩を禁止する。Community NG BLOCKは既存REVIEWより優先し、既存BLOCK、Shopee由来、own penalty等の監査証跡を失わない。
- 検証: loaderは列、source identity、hash形式、日付、件数、marketplace、ASIN、brand key / alias、action、enabled、source row範囲、重複、決定的順序、manifest出力件数をfail-closedで検査する。正規化判断、市場分離、完全一致境界、alias、SUNTORY除外、Bose、国不明非runtime、BLOCK優先、既存Evidence保持、Prelisting Gate EXCLUDEを自動testで固定する。
- Governance: modules/community_ng.py、guardrails/community_ng/**、関連Evidenceとtestをownershipのsafety.sharedへ登録し、変更全体をSHARED_COREとしてPH ph.beta.operationとSG sg.safety.baselineのprotected gate対象にする。
- 境界: live Shopee / Keepa / OpenAI API、deploy、GitHub設定、MY / TH / TW / VN runtime、既存Penalty緩和、自動出品を実行・許可しない。Draft PRとCIはDEC-0073の通常開発承認内で行うが、formal mainへのmergeはbound technical gateとOwner Acceptanceを別途必要とする。
- 理由: 入力provenanceと市場scopeを一つの検証可能な資産へ集約し、国不明情報の誤適用と複数辞書のdriftを防ぎながら、既存SG / PH Safety保護を維持するため。
- 再検討条件: 新しいオーナー提供source、source hash不一致、marketplace未特定recordの国確定、alias追加、現行Shopee policyとの競合、またはdata-only市場のruntime開始判断が生じた場合。既存source identityを上書きせず、新source IDと別判断で扱う。

## DEC-0075 — SLS Battery疑義をPH / SG共通REVIEWでfail-safeする

- 日付: 2026-09-17
- 背景: 2026-09-21以降、SLSで発送するバッテリーを含む全商品は事前登録が必要であり、発送可能な分類はUN3481 / PI966 / Section II、UN3481 / PI967 / Section II、UN3091 / PI969 / Section II、UN3091 / PI970 / Section IIに限定される。発送前には分類確認、Battery商品事前登録G-form、有効なSDS、指定ラベルが必要だが、現行Candidate / Keepa / Amazon情報だけではこれらを安全に確定できない。
- 決定: `guardrails/sls_shared/battery_review_rules.csv`をSLS共有Battery signalの単一正本とし、`battery`、`batteries`、`バッテリー`、`電池`、`rechargeable`、`充電式`、`power bank`、`powerbank`、`モバイルバッテリー`、`power case`、`powercase`の11件を`REVIEW / shipping_restricted / all / contains / shopee_policy`として固定する。これは禁止確定ではなく、SLS Battery要件を人間確認するまで自動出品準備へ進めないsignalとする。
- 決定: 共有資産をproduct runtimeへ接続する市場は既存runtimeを持つPH / SGだけとし、ブランド、Category、titleおよび既存Product Text Safetyが搬送するdescription / features / shortDescription / safetyWarning / itemHighlightsを対象にする。Bluetooth、speaker、headphone、mouse、smartwatch等のgeneric語は追加せず、実運用の漏れEvidenceが得られた場合だけ別Versionで検討する。
- 優先順位: 既存の`BLOCK > REVIEW > SAFE`を維持し、市場別matchと共有matchを同じ合成判定へ渡す。PH既存power bank / powerbank / モバイルバッテリーBLOCK、SG既存Battery REVIEW、Community NG BLOCK、own penalty BLOCK、PH V2 BLOCKを削除・移管・降格しない。共有signalがBLOCKと同時一致した場合はBLOCKを維持し、双方の監査Evidenceを残す。
- Fail-closed: 共有CSVは列順、8列契約、非空、enabled、固定metadata、stable rule ID、term / ID重複、UTF-8、CSV構文を厳格検査し、missingまたはmalformedならPH / SG Guardrail全体を停止する。Candidate schemaとPrelisting Gateの公開status / enumは変更せず、Guardrail REVIEWは既存契約どおりGate REVIEWとなりELIGIBLEへ進まない。
- Governance: `guardrails/sls_shared/**`を`safety.shared` ownershipへ登録する。変更全体をSHARED_COREとし、`ph.beta.operation`と`sg.safety.baseline`の両Protected Capability Gate、全offline tests、Governance Verifierを必須とする。PH Beta Test-Operation Compatibilityはprotected.phとPH Guardrail / Gate回帰で検証する。
- 境界: SLS Category Matrix 2162件のruntime統合、SG Category Mapper / Brand / Handoff、MY / TH / TW / VN runtime、Category ID推測、Battery type AI自動確定、G-form自動提出、SDS自動生成、自動出品、live Shopee / Keepa / OpenAI APIを開始しない。Category Matrixは次工程`SLS Market Category Rules`で独立した正本資産として扱う。
- 理由: 市場別Safety資産を複製・緩和せず、現行情報でSLS発送条件を証明できないBattery疑義だけを共通の人間確認へ止め、PH実運用とSG Safety Baselineを同時に保護するため。
- 再検討条件: 明示語以外の具体的な検出漏れ、過剰REVIEW、SLS要件変更、追加marketplaceのruntime開始、またはCategory Matrixとの正式な接続判断がEvidenceとして生じた場合。v0.1を黙って拡張せず、既存BLOCKを降格せず、別Version・別工程で判断する。


## DEC-0076 — SLS Market Category Rules Minimum Beta V0.3の設計契約を採用する

- 日付: 2026-09-18
- authority: Owner/GPT DESIGN_GATE_PASS Technical Design V0.3。実装・tests・local commit・push・Draft PR・CI/reviewを承認範囲とし、formal main mergeは別の最終受入まで行わない。
- 決定: 7市場のsource-specific deterministic assetを保持し、Master Unique Category IDだけでJOINする。PH runtimeはcanonical＋PHだけを読み、他市場runtimeは開始しない。source identity、raw logical records、transform version、output digest、anomalyを保持し、raw CSVはcommitしない。
- 決定: SLS resultをmanual reviewとは独立に保持し、market/confirmed Category/taxonomy/market assetへbindする。ready propertyはpureなlocal ANDとし、UI refreshと直接export入口がcurrent contextで再評価する。Brand操作でREVIEW/EXCLUDEを解除しない。
- 決定: PH NOをqtyより優先してEXCLUDE、YES＋No limitのみALLOW候補とし、数量1/2、要確認、unknown/missingはREVIEWに止める。既存Safety、Candidate15列、Gate enum、DB schemaは変更しない。
- 保持: TH 102009は2 raw recordsを維持し102010を生成しない。SG Pet Food noticeは今回sourceの10 IDへ明示bind。VN複合conditionは分離保持。BR authorityはJPBR/JPBR Qty limitでSAGAWAをPASSへ使用しない。
- 障害・更新: canonical/PH検証不能はMapperのSLS依存出口をfail-closedにし、DBを削除せずready=0、Brand操作とgroups/TXT出力を停止する。非PH破損はPH runtimeへ波及させない。正式更新はapp stop→code＋validated assets→restart→new session。hot swap、download thread/lock、Streamlit pin、専用audit CSVを追加しない。
- Governance: SHARED_CORE、既存mandatory gatesを維持。protected jobへ短いSLS invariant回帰を追加し、Mapper/UI詳細回帰は全offline suiteで確認する。
- rollback: SLS追加のcode/asset/tests/Governanceを通常revertで戻しrestart/new session。既存DBと前工程Safetyを維持し、migrationを追加しない。
- 詳細: asset contract、source更新手順、保持anomalyはguardrails/sls_market_categories/README.mdを参照。本決定は技術検証済みまたはOwner最終受入済みを意味しない。

## DEC-0077 — SLS Market Category Rules Minimum Betaをformal mainで正式受入する

- 日付: 2026-09-19
- 背景: DEC-0076のV0.3設計に基づくPR #78について、Owner Acceptance、source freshness確認、mandatory technical gates、PH / SG protected回帰を完了した。
- 決定: PR #78のaccepted head `177c70e8c28208ef8f0fe04afd32757124a40086`をmerge commit `5079795fd1eb7a4ae1940852b76e2bd2315e0006`でformal mainへ統合し、SLS Market Category Rules Minimum Betaを正式受入する。Master source SHA-256 `35f7bab5da9c5dd3d9b62456035916a9fce62a153d6bcfcaa82c221dc117dbc9`はsource-lockと一致し、asset再生成は不要だった。
- 確認事実: CI run `35325162215`でgovernance.validate、governance.ps51、governance.ps7、tests.offline、protected.ph、protected.sgがPASSした。CI offlineは1369 passed / 1既存fixture skip、protectedは574 passed、local offlineは1370 passedである。Category / Brand確認済みでもSLS REVIEW / EXCLUDE / UNAVAILABLEを完了表示しない回帰を固定した。
- 影響: PH runtimeだけを開始し、canonical taxonomy + PH assetの境界、SLS resultのfreshness binding、CSV / TXT leakage防止、既存Safety非解除を正式成果として維持する。Candidate15列、Prelisting Gate contract、DB schema、非PH runtimeは不変である。governance/state.jsonの既存market / capability lifecycleを変更する必要はない。
- rollback: SLS追加単位を通常revertし、app restart→new sessionで戻す。DB migrationはなく、既存Category / Brand DBと前工程Safetyを維持する。
- 再検討条件: 新しい一次source、source hash不一致、PH実利用での停止理由または漏洩Evidence、REVIEW override要求、non-PH runtime開始、または既存Safetyとの競合が生じた場合。いずれも別タスク・別判断とする。

## DEC-0078 — SG Category Mapper Minimum Betaの開発再開を正本化する

- 日付: 2026-09-19
- 背景: SLS Market Category Rules Minimum Betaのformal main受入後、OwnerはSG Category Mapper以降の開発再開を承認し、SG Category Mapper Minimum Betaの設計報告をDESIGN_GATE PASSとして受入した。governance/state.jsonではSG development_policyがPAUSEDのままであり、stop_condition_idsに`pause-sg-product-development`が残っていたため、製品実装前に正式状態を更新する必要があった。
- 決定: SG operationはINACTIVEのまま維持し、SG development_policyをALLOWEDへ変更する。`pause-sg-product-development`停止条件だけを除去する。今回許可する範囲はSG Category Mapper Minimum Betaの開発再開であり、SG実運用開始、SG Brand、SG SLS runtime、`listing_ready`、handoff、live Shopee / Keepa / OpenAI API、deploy、自動Category確定、自動出品は承認しない。
- 保護: PHはACTIVE / ALLOWED、`ph.beta.operation`はACCEPTEDのまま維持する。`sg.safety.baseline`もACCEPTEDのまま維持し、protected capabilityを削除または変更しない。Governance schema、mandatory gate定義、Trust Anchor、rollback_target、MY / TH状態、既存Safety Rule、SLS asset、製品runtimeは変更しない。
- 理由: Owner承認済みのSG Category Mapper Minimum Beta開発だけを再開可能にしつつ、SG operationと出品系・live系の境界を閉じたまま保つため。PAUSED状態と停止条件を残したままだと、設計PASS後の最小製品実装へ進む正式状態と矛盾するため。
- 影響: 変更分類はGovernance変更として扱い、mandatory technical gatesとPH / SG protected capability gateで回帰保護する。formal mainへ統合された後の次工程は、SG Category Mapper Minimum Betaの最小製品実装であり、Brand / SLS runtime / Handoffは後続独立工程とする。
- rollback: 今回のgovernance/docs/test差分を通常revertし、SGをINACTIVE / PAUSEDへ戻して`pause-sg-product-development`停止条件を復元する。PH operation、既存Category/Brand DB、SLS資産、前工程Safetyは維持する。
- 再検討条件: SG operation ACTIVE化、Brand、SG SLS runtime、`listing_ready`、handoff、live API、deploy、自動Category確定、自動出品、またはMY / TH開発開始を検討する場合。いずれも別タスク・別設計Gate・別Owner承認を必要とする。

## DEC-0079 — SG Category Mapper Minimum Betaを商品単位確認で実装する

- 日付: 2026-09-19
- authority: Ownerが受入済みのSG Category Mapper Minimum Beta DESIGN_GATE PASS、およびformal main `15e3ce242953bfa7592e0d89d790d85db8512f83`後の最小製品実装・offline検証・Draft PR / CI承認。formal main mergeはexact headにbindingしたOwner Acceptanceまで行わない。
- 決定: 全行ELIGIBLEの正式SG Prelisting Gate CSVだけを受理し、PH・市場混在・REVIEW / EXCLUDE・audit・raw Candidate・schema不正・source_type混在をfail closedで拒否する。出所確認済みSG Category catalogはID、parent、name、path、leafを全件validationした後、SG分だけをtransactional replaceする。古いSG catalogとのmerge、SG SLS canonical / Master MatrixのAI catalog利用、PH catalog変更を行わない。
- 決定: 既存Category AI Core、ProductEvidence、CategoryCatalog、Prompt V1 / Traversal V1、固定Luna profileを再利用し、SG固有制御層で商品EvidenceからCategory候補だけを提示する。過去推薦・過去確定Category・Safety・Gold・SLSをAI入力にせず、confidence=1.0、ABSTAIN、FAILED、invalid response、catalog mismatchのいずれでも自動確定しない。
- 決定: 人間確認は商品単位とし、AI候補の採用または現在の検証済みSG catalogにある別leafの選択で確定する。確定時にSG marketplace、Category ID、path一致、leafを再検証し、既存marketplace付きDBへASIN単位で保存する。DB migrationとgroup一括確定は行わない。保存済みCategoryも現在catalogに対してID・path・leafを再検証し、不一致なら未確定へ戻す。catalog hash / Evidence hashの永続保存はBeta後候補とする。
- 停止境界: SG Category確定後も`listing_ready=false`とし、groups CSV、listing TXT、handoffへ出力しない。直接export入口もPH-onlyとしてSGを拒否する。SG Brand、SG SLS runtime、listing_ready、handoff、live Shopee / Keepa / OpenAI API、deploy、自動Category確定、自動出品は本工程に含めない。SG operationはINACTIVEを維持する。
- 保護: PH Category Mapperのdeterministic mapping、initial profile、Brand / No Brand、Attribute、PH SLS、listing_ready出口は維持する。Category確定でSG Safety Baseline、Shared Battery、Community NG、own penalty、その他BLOCK / REVIEWを解除しない。Candidate 15列とPrelisting Gate公開contractは不変とする。
- Governance: 共通AI adapter、store、UI接続、PH-only export guardを含むため変更分類はSHARED_COREとして扱い、`ph.beta.operation`と`sg.safety.baseline`のmandatory protected gatesを実行する。branch上の実装・tests・Draft PR / CI候補であり、Owner Acceptanceとformal main統合前は正式成果と扱わない。
- rollback: SG固有module / UI / tests、共通AI adapterのmarketplace対応、SG catalog replace、PH-only export guard、docsを通常revertする。DB migrationはない。PH operation、PH catalog / mapping、SLS asset、Safety assetを維持する。
- 再検討条件: 実SG production catalogのsource identityを確定する場合、Evidence hashによる自動失効、SG Brand / SLS runtime / listing_ready / Handoff、operation ACTIVE化、live API、deploy、自動Category確定または自動出品へ進む場合。いずれも別工程・別承認とする。

## DEC-0080 — SG UIのlive OpenAI実行経路を別承認まで閉じる

- 日付: 2026-09-19
- 背景: PR #82 head `e7e70d909fc7b58f6b623acd5649acc5d0abc277`のOwner Acceptance前レビューで、SG UIのAI候補作成ボタンが`OpenAIResponsesCategoryProvider.from_environment()`を生成し、通常操作から未承認のlive OpenAI APIへ到達できるscope blockerを確認した。CIでlive requestを実行していない事実だけでは、formal main統合後の通常UI経路を閉じたことにならない。
- 決定: SG UIからlive OpenAI provider import・生成、AI候補実行ボタン、AI候補採用UI、AI session resultを除去する。SG UIには「live実行は未承認、現在は手動Category確認のみ利用可能」と表示する。環境変数だけで有効になるfallbackや隠れた自動実行経路を設けない。
- 維持: Category AI CoreのSG対応、`generate_sg_ai_category_suggestions`、ProductEvidence marketplace=SG、固定Luna profile、Fake Provider / synthetic catalogによるoffline tests、AI候補が自動確定しない契約は維持する。商品単位手動確認、ASIN単位保存、現在catalog再検証、`listing_ready=false`、SG export停止、PH AI導線も変更しない。
- 境界: 実SG catalog確認とlive OpenAI検証・UI有効化は後続の別Owner承認とする。SG operation ACTIVE化、Brand、SLS runtime、listing_ready、handoff、deploy、自動Category確定、自動出品は引き続き未承認である。
- Governance: 変更分類はSHARED_COREを維持し、全mandatory technical gates、PH / SG protected回帰、CI、formal verifierを新headへ再bindingする。旧headのOwner Acceptance Summaryは失効する。
- rollback: 本修正commitを通常revertすると未承認live API UI経路が復帰するため、単独revertは行わない。PR #82全体を戻す場合はPRの全commitを通常revertし、SG operation INACTIVEと既存PH運用を維持する。

## DEC-0081 — SG Category Mapper Minimum Betaのoffline成果をformal mainで正式受入する

- 日付: 2026-09-19
- 背景: Owner Acceptance済みのPR #82は、accepted head `c2f15648d189d2d885fe97bda96c3464fcf2fa48`を含むmerge commit `925e022810b0953df4b51ecfb976ce089e06892c`でformal mainへ統合された。DEC-0079のbranch上候補およびDEC-0080のlive OpenAI UI閉鎖を、現在の正式成果・既知制約・次工程境界として記録する必要がある。
- 正式受入範囲: 全行ELIGIBLEの正式SG Prelisting Gate CSV入力、SG-only catalog replace前の全件validation、Category AI CoreのSG offline契約、`marketplace=SG`のProductEvidence、Fake Providerによるoffline AI検証、商品単位の人間Category確認、ASIN単位保存、保存済みCategoryの現在catalog ID / path / leaf再検証、`listing_ready=false`、SG export / handoff停止を正式成果とする。SG UIにはlive OpenAI providerの生成・実行経路を置かない。PH AI / Brand / SLS / exportは維持する。
- 未受入範囲: 実SG production Category catalogのsource identity、実catalogを使う実商品受入、SG live OpenAI API、SG AI意味精度、SG Brand、SG SLS runtime、listing_ready、handoff、deploy、自動Category確定、自動出品、Evidence hashによる完全自動失効は受入していない。SG Minimum Betaの実運用完成またはSG operation開始を意味しない。
- Governance: SG operationはINACTIVE、development_policyはALLOWEDのままとする。PHはACTIVE / ALLOWED、`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDのprotected capabilityのままとし、capability lifecycle、Safety、SLS、Candidate 15列、Prelisting Gate contract、DB schemaを変更しない。
- rollback: PR #82の製品変更を戻す場合は、対象commit群を通常revertし、DB migrationを伴わずSG operation INACTIVEとPH operationを維持する。今回の文書正本化だけを戻す場合はdocs-only change setを通常revertする。DEC-0080が閉じた未承認live OpenAI UI経路を単独で復帰させない。
- 再検討条件: production catalog source identity、実catalog / 実商品の受入、live OpenAI API、AI精度、SG Brand、SLS runtime、listing_ready、handoff、operation ACTIVE化、deploy、自動Category確定または自動出品を検討する場合。いずれも新規Codexタスク、別scope・設計Gate・Owner承認を必要とする。

## DEC-0082 — Shopee Open Platform認証・Catalog取得を多市場共通基盤として先行整備する

- 日付: 2026-09-19
- 背景: PHには`ShopeeCatalogClient`が存在するが、`PH_MARKETPLACE`、`_require_ph()`、`SHOPEE_PH_SHOP_ID`、`SHOPEE_PH_ACCESS_TOKEN`に固定されている。Access Token refreshはCategory Mapperの責務外であり、SG以降を市場ごとにコピー実装すると認証・Catalog取得が重複する。
- 決定: Shopee共通Token ManagerのMinimum Beta設計Gateを先行し、最小実装とPH先行検証、marketplace-neutralな共通Catalog Client、SG production Category catalog source identity確認の順へ変更する。SG source identity調査を中止せず、共通基盤の後に再開する。
- 認証境界: 認証はmarketplaceごとの代表となる認証済みshop単位、Category / Brand / Attribute catalogはmarketplace単位とする。同一marketplaceの全shopについて同じCatalog masterを重複取得・保存しない。注文・在庫等のshop固有APIのtoken管理は別責務とする。
- Token安全境界: Token ManagerはCategory Mapperに埋め込まず、有効なAccess TokenをCatalog Clientへ提供する。API利用時に有効性を確認し必要時だけrefreshするon-demand方式を第一候補とし、refresh失敗時はfail closedとする。refresh時はAccess Tokenだけを更新してRefresh Tokenを失わず、新旧tokenの整合性を保つ。token、refresh token、partner keyその他のcredentialをGit、docs、log、UI平文、snapshot、Evidenceへ出さない。PH既存の一時Access Token手入力経路は、自動refreshの実運用確認前に削除しない。
- 外部仕様: token TTL、refresh endpoint、request / response contractその他の正確な外部仕様値は、実装前に最新の一次資料または実API contractで確認する。推測の数値を恒久的な内部仕様に固定しない。credential保存のatomic方式は後続設計Gateで確定する。
- 非対象: 今回は実装しない。SG live API、SG Brand、SG SLS runtime、`listing_ready`、handoff、SG operation ACTIVE化、deploy、自動出品、MY / TH runtimeを開始しない。
- 保護: PHは`ACTIVE / ALLOWED`、SGは`INACTIVE / ALLOWED`、`ph.beta.operation`と`sg.safety.baseline`は`ACCEPTED`のまま維持する。Candidate 15列、Prelisting Gate contract、DB schema、Safety / SLS既存資産、governance/state.json、PH operation、SG operationを変更しない。
- rollback: docs-only差分を通常revertできる。製品コード、credential、marketplace runtimeを含むrollbackや変更はない。
- 再検討条件: 共通Token Managerの実装、credential保存、PH live検証、共通Catalog Client、SG production source identity、SG Brand、SLS runtime、listing_ready、handoff、operation ACTIVE化、MY / TH展開を開始する場合は、それぞれ別scope・設計Gate・Owner承認を必要とする。

## DEC-0083 — Shopee共通Token Manager Minimum Betaの設計Gateを正式受入する

- 日付: 2026-09-24
- 背景・決定: OwnerがShopee共通Token Manager Minimum Betaの`DESIGN_GATE_PASS`を正式設計として受け入れた。Token ManagerはCategory Mapperから独立した共通認証責務とし、実装は次の新規Codexタスクで行う。
- 公式Refresh Token contract: Shopee Open Platformの`v2.public.refresh_access_token`は`POST /api/v2/auth/access_token/get`。queryには`partner_id`、`timestamp`、`sign`、bodyには`partner_id`、`shop_id`、`refresh_token`を渡し、成功時は`access_token`、`refresh_token`、`expire_in`、`partner_id`、`shop_id`等を受け取る。公開API署名は`partner_id + path + timestamp`を基底文字列とするHMAC-SHA256。Access Tokenの有効期間は4時間、Refresh Tokenは30日有効かつ一度だけ使用可能で、refreshは新しいAccess / Refresh Tokenを返す。参照: [Shopee Open Platform API Reference: v2.public.refresh_access_token](https://open.shopee.com/documents?module=87&type=2&id=58&version=2)。
- 責務境界: 認証credentialはmarketplaceごとの代表shop単位で保持し、Category / Brand / Attribute catalogはmarketplace単位で扱う。同一marketplaceのshopごとに同じcatalogを重複取得しない。注文・在庫等のshop固有業務APIはこのMinimum Betaの対象外とする。
- 更新方式: Token ManagerはAPI利用時のon-demand refreshとし、常駐タイマー更新は行わない。期限までの120秒marginはShopee公式仕様ではなく、内部運用値として扱う。
- token世代・状態: Access TokenとRefresh Tokenは同一refresh世代の組として保存・返却する。状態は`READY`、`IN_FLIGHT`、`BLOCKED`で管理し、refresh中の並行要求を排他する。応答を安全に確定できない場合はfail closedとし、旧Refresh Tokenを自動再送しない。
- credential保存: Minimum BetaではGit管理外の専用credential fileを採用する。更新は同一ファイルシステム上の一時fileへの書込み・flush後にatomic replaceし、Windows上の最低限の排他制御を置く。permissionと保存先は実装Gateで検証する。
- PH fallback・初期状態: PHの一時Access Token overrideをfallbackとして維持する。Token Managerによる自動管理は初期`OFF`とし、credential fileが存在することとruntimeが`ACTIVE`であることを分離する。明示的な設定と運用承認なしにPH runtimeを切り替えない。
- 市場展開・秘密情報: 同じToken ManagerをSG / MY / THへ再利用する設計とし、市場ごとの複製実装をしない。token、partner key、refresh tokenその他secretをGit、log、UI、Evidence、snapshot、通常のdocsへ出さない。
- 保護範囲: PH既存Category / Brand / Attribute経路、Safety判定、SLS資産・判定を変更・迂回・緩和しない。SG operation状態、Candidate schema、Prelisting Gate contract、DB schemaも本決定では変更しない。
- `PRIMARY_SOURCE_UNVERIFIED`: refresh固有rate limit、timeout / 5xx / 429時のtoken消費と再送冪等性、旧Refresh Tokenが失効する厳密なタイミング、認可解除等の伝播挙動は未確認のまま保持する。これらの未確認事項に依存せず不明結果をfail closedにできるため、設計Gateを`DESIGN_GATE_PASS`とする。未確認を実装時に推測で埋めない。
- 次工程と承認境界: 次の単一作業は「Shopee共通Token Manager Minimum Betaの実装＋PH先行offline検証」。offline technical gates完了後に`WAITING_APPROVAL`とし、別Owner承認前はactual PH Refresh Token登録、actual credential変更、Shopee production refresh API、PH live Category / Brand / Attribute確認を行わない。
- rollback: docs-only正本化は通常revertできる。Token Manager製品実装、credential変更、live API実行、runtime状態変更をこの決定で許可しない。
- 再検討条件: offline gates完了後のcredential登録・変更、production refresh、PH live catalog確認、他marketplaceでのruntime有効化、または未確認事項の再評価には、独立した実装タスク、明示scope、必要なOwner承認を要する。

## DEC-0084 — Google Sheet Access Token Source Minimum Betaを共通認証sourceとして採用する

- 日付: 2026-09-25
- 背景: 既存在庫管理ツールとPR #86のToken Managerは、同じShopee Open Platform App、同じshop、同じRefresh Token系列を共有することが判明した。同一系列を複数ツールが独立にrefreshするとtoken世代の競合を招く。
- 決定: この系列のRefresh Tokenは既存在庫管理ツールだけが管理・更新する。各国Mapper側はrefreshせず、最新Access Tokenをread-onlyで取得する共通Google Sheet Access Token Source Minimum Betaを採用する。DEC-0082 / DEC-0083のToken Manager実装順とMapper側refresh方針は、この共有系列について本決定で置き換える。両DECは履歴として保持し、DEC-0083を書き換えない。
- Bridge境界: Partner Key、Refresh Token、注文データ等を含む元注文管理表をMapperへ直接API共有しない。専用Bridge Spreadsheetを設け、最小contractをmarketplace、shop_id、access_tokenとする。MapperはBridgeからRefresh TokenまたはPartner Keyを読まない。Bridgeへの発行・更新責務と具体的なアクセス設定は後続の独立作業で確認する。
- 共通module: PH / SG / MY / THを同一interfaceで扱う。取得したmarketplaceを要求市場へbindし、Bridgeのshop_idとローカルのexpected shop_idを照合する。不一致、欠落、曖昧な行、取得・認証障害ではfail closedとする。Google APIはread-onlyとし、Access Tokenはメモリ内だけで利用する。Access TokenをGit、DB、log、snapshot、Evidenceへ保存しない。
- 認証優先順位: 一時Access Token override、明示ONのGoogle Sheet Access Token Source、legacy Access Tokenの順とする。Google sourceを明示ONにした後の障害・不一致ではlegacyへsilent fallbackしない。overrideの選択は明示的な一時操作として扱う。
- 市場・保護境界: PHで先行検証するが、MY / TH runtimeは有効化しない。SG operationもINACTIVEを維持する。governance/state.json、ph.beta.operation、sg.safety.baseline、Safety、SLS、Candidate / Prelisting Gate契約は変更しない。
- PR #86: Token Manager実装PRはDraftのままruntime OFFで未merge候補として保持し、今回のdocs-only差分に混ぜない。将来、独立した認証系列が必要になった場合の再利用候補とし、その採用は別判断とする。
- 工程順: Google Sheet Access Token Source最小実装・offline検証 → 別承認によるPH live確認 → marketplace-neutral ShopeeCatalogClient → SG production Category source identity → 後続SG工程。今回の決定だけでcredential作成、Bridge作成、Google live read、Shopee live API、runtime切替、deployを許可しない。
- rollback: 今回のdocs-only差分は通常revertできる。PR #86の削除・merge、製品runtimeまたはGovernance状態の変更を伴わない。

## DEC-0085 — PH Access Token Bridge同期をBridge側Apps Scriptで先行する

- 日付: 2026-09-25
- 背景: DEC-0084のread-only SourceはPH live確認済みだが、Bridgeへ最新Access Tokenを自動反映する経路は未実装で、手動コピーが必要だった。
- 決定: 既存在庫管理ツールのApps Scriptを変更せず、専用Bridge同期の独立Apps Scriptを置く。Spreadsheet IDはScript Propertiesで設定し、コードへ埋め込まない。sourceの設定sheetからB/C/E列だけを読み、行番号ではなくPHを検索する。PHが1行、shop_idが正の整数、Access Tokenが非空の場合だけ、Bridge A:Cの3値を更新する。Refresh Token、Partner Key、Shopee Refresh APIは扱わない。時間主導トリガーは5分周期を第一候補とし、Google側の設置・権限承認・live確認は別Owner承認まで実行しない。
- 失敗境界: 実行開始時にBridgeのPH tokenを空にして確認してからsourceを読む。取得、検証、新値書込み、読戻しの失敗では再度空にする。Bridge書込み自体が不能な場合、3列contractと既存readerだけでは旧tokenの無効化を保証できない。この場合は失敗として報告し、完全な書込み障害に対する厳密な停止保証はreader側freshness契約の別判断を要する。
- 市場・責務: PH先行に限る。既存Mapper、Governance State、製品runtime、SG / MY / TH operationを変更しない。Service AccountはBridge Viewerのままで、source Spreadsheetへ共有しない。
- rollback: Owner管理下でトリガーを無効化し、Bridge PH tokenを空にする。古いtokenをBridgeに残して正常扱いしない。

## DEC-0086 — PH Access Token Bridge自動同期Minimum Betaのlive結果を受入する

- 日付: 2026-09-25
- 決定: OwnerはDEC-0085のPH先行Bridge自動同期をMinimum Betaとしてlive受入した。専用Bridge側Apps Scriptと5分間隔の時間主導トリガーを採用し、既存在庫管理ツール側Apps Script、既存Mapper、Governance State、製品runtimeは変更しない。
- 確認済み: 5分トリガーは1件。PH自動同期2回が完了し、元管理表とBridgeのPH shop_id binding・Access Token一致を本文を出さず確認した。既存GoogleSheetAccessTokenSourceはGit外のService Accountを用いたBridge Viewerのread-only取得をPASSした。
- 秘密情報と権限: Access Token、Refresh Token、Partner Key、Service Account JSONの本文をGit、docs、log、Evidenceへ保存しない。同期Scriptは元表のB/C/Eだけを読み、Service AccountはBridge Viewerのままとし、元表へ共有しない。Shopee Refresh APIは呼ばない。
- 既知制約: Bridge書込みが全面失敗した場合、旧token消去を保証できない。Ownerはこの制約をPH Minimum Betaとして受入し、今回はfreshness判定等の追加機構を作らない。失敗した同期を正常な最新値として報告しない。
- 保護と公開境界: SG operation、MY / TH runtime、ph.beta.operation、sg.safety.baseline、Safety、SLS、Candidate / Prelisting Gate、governance/state.jsonは変更しない。local commit、push、Draft PR、CI/checks確認を行い、formal main mergeとdeployは最終Owner承認なしに行わない。
- rollback: Owner管理下で5分トリガーを無効化し、BridgeのPH tokenを空にする。全面書込み障害中は空への更新も保証できないため、復旧確認まで最新値として扱わない。

## DEC-0087 — AGENTSのmandatory原則とRUNBOOKの詳細手順を分離する

- 日付: 2026-09-26
- 背景: AGENTSの承認境界・正本化・Governance説明がRUNBOOKや同文書内で重複し、毎タスクの再読込負担と更新不整合を生んでいた。Ownerは監査案を承認し、同じタスクで文書整理と検証、local commit、push、Draft PR、CI確認までを承認した。
- 決定: AGENTSには毎タスク必須の短い恒久ルール・mandatory原則、RUNBOOKには詳細手順・実行方法を置く。AGENTSに開始時、変更前、検証・formal merge前、終了・handoff、E2E、共有・復旧時の必須参照を残し、移動した手順を任意化しない。削除は意味が完全に残る重複記述に限る。
- 維持: DEC-0072 / DEC-0073の承認・信頼契約、HOLD / HARD_STOP、mandatory technical gate、protected capability、外部API / live / secret境界を変更しない。既存policy検査の6文言を保持し、検査script・testsを弱めない。開始時の正本文書読込義務を削減せず、DECISION_LOGの既存entryを書き換えない。
- 正本: Git、長寿命State、repo外Task Contextの役割を維持し、CURRENT_WORKは再開案内とする。snapshotは生成物であり、手編集・commitしない。V2以前のCURRENT_WORKへのbranch等の二重入力を復活させない。
- 工程順: PR #89のPH Bridge正式統合を確認済みの前工程とし、AGENTS.md軽量化 → marketplace-neutral ShopeeCatalogClient → SG production Category source identity → 後続SG工程とする。DEC-0084の製品基盤順を維持し、その前に今回の文書整理を置く。Catalog Client以降へ本承認だけで着手しない。
- 非対象: 製品コード、Safety、SLS、Mapper、Catalog Client、secret処理、governance/state.json、Config / gate / verifier、protected capabilityの変更は含めない。formal main mergeは現在対象のOwner Acceptance Summaryと明示的最終承認まで行わない。
- 理由: 必須原則の可視性と詳細手順の完全性を両立し、重複更新を減らすため。行数削減率を受入目標にせず、安全性を維持した配置整理の結果として測定する。
- rollback: 今回の5文書差分を通常revertできる。製品、State、credential、runtimeの変更はない。force pushやdirty resetを復旧手段にしない。
- 再検討条件: mandatory原則の欠落、必須参照先の消失、policy検査失敗、正本間矛盾を検出した場合は修正して再検証する。開始時の全文読込削減、承認境界・gate変更は本決定に含めず、別の設計・承認を要する。

## DEC-0088 — DECISION_LOGを正本のまま維持し関連Decisionの段階的読込へ移行する

- 日付: 2026-09-26
- 背景: AGENTS軽量化はPR #90でformal mainへ統合されたが、開始時のDECISION_LOG全文再読込は残り、約87 Decisionの履歴を毎タスク読み直していた。Ownerは正本性と安全境界を維持した読込軽量化の設計・実装・検証、local commit、push、Draft PR、CI確認を承認した。
- 決定: AGENTS / 適用下位AGENTS、CURRENT_WORK、PROJECT_ROADMAPを読み、DECISION_LOGの全Decision見出し一覧を確認する。CURRENT_WORKのRequired Decisionsの本文と、今回のmarketplace / module / phase・変更対象に直接関係するDECの本文を読む二段階方式を採用する。Required Decisionsだけで選択を閉じず、見出しだけで本文判断を代替しない。
- 検索拡大: 選択した本文の必要な参照DECと、選択IDを参照する後続DECを確認し、置換範囲を追跡する。根拠不足、競合・置換不明、shared core / Governance / approval boundaryへの影響、Required Decisionsの欠落・不備・漏れの疑いでは本文全体を検索対象へ広げる。それでも判断不能なら全文を読む。全文後も不明な承認・停止条件は依存作業を停止して報告する。未読・未記載を制約なしと扱わない。具体手順はRUNBOOK「Decision読込」を必須参照とする。
- 正本と保守: DECISION_LOGは完全な判断履歴のappend-only正本とし、過去DECを削除・分割・書換えしない。Required DecisionsはIDと短い理由だけの再開案内とし、単一作業・scope・phase変更時とhandoff時に見出し一覧と照合して更新する。本文複製や手動巨大index、新しい正本は作らない。将来の派生indexも見出しから再生成可能な非正本に限る。
- 置換範囲: DEC-0087の「開始時の正本文書読込義務を削減しない」のうちDECISION_LOG全文再読込だけを本決定の段階的読込へ置き換える。AGENTS / 適用下位AGENTSの全文読込、CURRENT_WORK / PROJECT_ROADMAPと条件付きREADME、実行時点の必須RUNBOOK参照は維持する。DEC-0087本文は改変しない。
- 工程順: AGENTS軽量化 完了 → DECISION_LOG読込軽量化 → marketplace-neutral ShopeeCatalogClient → SG production Category source identity → 後続SG工程。DEC-0087の順序へ本工程を挿入する。Catalog ClientやSG production確認の開始許可にはしない。
- 保護・非対象: DEC-0072 / DEC-0073、HOLD / HARD_STOP、mandatory technical gate、approval boundary、protected capabilityは不変。governance/state.json、Config / gate / verifier、policy検査、製品コード、Safety、SLS、Mapper、Catalog Client、credential、live API、runtime切替を変更・実行しない。formal main mergeはtechnical gatesと現在対象のOwner Acceptance Summaryの後、Owner明示的最終承認までWAITING_APPROVALで停止する。
- 理由: 完全な履歴を維持したまま通常タスクの読込量を抑え、短い参照欄の更新漏れを全見出し確認と検索拡大で補うため。
- rollback: 開始手順・再開案内・工程文書を通常revertで戻せる。判断撤回・訂正は新規DECで記録し、DEC-0088を含む履歴を削除しない。製品、State、credential変更は伴わない。
- 再検討条件: 関連DECの見逃し、Required Decisionsの陳腐化、置換追跡不足、文書矛盾、policy / Governance検証失敗が見つかった場合は補正して再検証する。gate緩和や製品責務変更へ自動拡張しない。


## DEC-0089 — ShopeeCatalogClientをPH/SG共通の明示marketplace bindingへ変更する

- 日付: 2026-09-26
- 背景: PR #91はformal mainに統合済みで、DEC-0088の次工程はDEC-0082 / DEC-0084が求めるmarketplace-neutral Catalog Clientである。既存ClientはPH固定で、SG用に複製すると認証・Catalog処理が重複する。
- 決定: 1つのShopeeCatalogClientを生成時にPHまたはSGへ明示bindする。環境factoryもmarketplace指定を必須とし、共通partner値と当該市場だけのshop_id / legacy Access Tokenを読む。既存のCategory / Attribute / Brand method引数は維持し、bindとの不一致、MY / TH指定は外部request前に停止する。
- 認証: 一時override → 明示ONのGoogle Sheet Access Token Source → legacy tokenの優先順位を維持する。Sourceへbind済みmarketplaceと当該shop_idを渡し、Source失敗時のlegacy fallbackは行わない。Refresh Token、Partner KeyのBridge読込、Mapper側refreshは行わない。
- API・運用境界: 既存3 endpointとnormalizationを共有し、市場別response分岐は実Evidenceまで追加しない。SGはoffline fake requestでのcode contractに限り、production live API、source identity受入、SG Mapper live接続、Brand / SLS runtime、listing_ready、handoff、deploy、operation ACTIVE化を許可しない。MY / TH runtimeは無効のままとする。
- 保護: PH Category Mapperの業務契約、Candidate 15列、Prelisting Gate、DB schema、Safety、SLS、Resolver、Expansion、governance/state.json、ph.beta.operation、sg.safety.baselineを変更しない。PH UI callerは明示PH bindとする。
- 既知制約: SG production response同一性は未確認。DEC-0086のBridge全面書込み障害時の旧token消去不可は今回変更しない。
- rollback: code / docsの通常revertで戻す。DB migration、credential変更、State変更、force pushを伴わない。


## DEC-0090 — ShopeeCatalogClient marketplace-neutral化をformal mainで正式受入する

- 日付: 2026-09-27
- 背景: OwnerはPR #92のaccepted head `536a8849dc4406660fca464d17f58d83646c0dc8`を最終承認した。GitHub上でhead、main base、9変更ファイル、mergeability、現在headのGovernance mandatory 6 gateとprotected PH / SGを再確認し、GitHub Owner証跡をbindしたformal-acceptance VerifierはCONTINUEとなった。
- 正式受入: PR #92を通常のmerge commit `7be1e78da7114dbaab2f423a70649342864cde8d`でformal mainへ統合し、DEC-0089の単一共通ShopeeCatalogClient、生成時PH/SG明示binding、市場不一致とMY/THのrequest前fail closed、既存認証優先順位、PH UIの明示PH binding、offline Category / Attribute / Brand contractを正式成果とする。
- 確認済み: GitHub PRはMERGED、GitHub mainとorigin/mainはmerge commitで一致し、accepted headはmerge commitの親に含まれる。governance/state.jsonは開始mainから不変。PHはACTIVE / ALLOWED、SGはINACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTED、`ph.beta.operation`と`sg.safety.baseline`はACCEPTEDを維持する。CI offline全体は1,458 passed・1 conditional skip、mandatory 6 gateはPASS。
- 未受入: SG production Catalog API、Category source identity、実catalog/実商品受入、SG Mapper live接続、SG Brand / SLS runtime、listing_ready、handoff、deploy、operation ACTIVE化、MY / TH runtime。次工程の「SG production Category catalog source identity確認」は別scopeであり、live API・credential操作に別Owner承認を必要とする。
- 既知制約: SG production responseの同一性は未確認。DEC-0086のBridge全面書込み障害時の旧token消去不可は変更しない。
- rollback: PR #92の製品・文書差分を通常revertで戻す。DB migration、credential変更、State変更、force push、dirty resetを伴わない。

## DEC-0091 — PR authorがOwnerの場合のGitHub Owner Acceptance証跡を定義する

- 日付: 2026-09-27
- 背景: Owner自身がauthorのPRではGitHubが自己Approve reviewを拒否する。PR #95のtechnical gatesはPASSしたが、既存GovernanceはGitHub Ownerコメントの取得・真正性検証とSummary binding完全一致を実装していないためformal acceptanceはHOLDである。
- 決定: GitHub PR ConversationのOwner承認コメントを独立Providerが取得し、repository identity、PR番号、Trust AnchorのOwner numeric actor ID、完全head SHA、verification input hash、Owner Acceptance Summary binding、明示APPROVED意思とscopeを検証する。Generator / Verifierは外部fetchを行わず、VerifierはProviderの短寿命Ed25519署名付きreceiptをrepo外Trust Anchor公開鍵でoffline検証する。GitHub確認のない手製GITHUB_OWNER JSONは受理しない。
- 失効: コメントの編集・削除・撤回、head・binding変更はProvider再観測でHOLDとする。receiptは5分で失効し、merge直前にGitHub再観測とformal Verifyを行う。offline検証は取得後のGitHub変更を即時には知れないため、再観測なしのmergeを許可しない。
- 信頼と保護: Trust Anchor v1.1.0の公開鍵とOwner管理下のProvider専用秘密鍵を必要とする。未設定はHOLD。既存mandatory technical gates、protected capability、final Owner approvalを維持し、GitHub repository設定、branch protection、governance/state.json、製品runtimeを変更しない。PR #95は本決定の候補PRに混在させず、現headのまま保留する。
- rollback: 本Governance差分を通常revertする。署名鍵の失効・紛失・漏洩、Provider/API契約の変更、受入証跡の偽装可能性が見つかった場合はmergeを停止し、Owner管理下で鍵交換と再設計を判断する。

## DEC-0092 — PR #96のTrust Anchor v1.1移行を一回限りの二重検証で行う

- 日付: 2026-09-27
- 背景: 現formal mainのv1.0 VerifierはTrust Anchor v1.1を受理しない。PR #96のmerge前に本番Anchorを置換すると現行Governanceが破綻する。OwnerはPR #96 headとCI成功を確認したが、最終merge承認は保留した。
- 決定: 本番v1.0 Anchorを変更せず、分離bootstrap/test環境のv1.1 AnchorとEd25519鍵で実OwnerコメントのProvider取得・署名・candidate offline Verifyを1回E2E確認する。同じ実GitHubコメント由来Evidenceに旧Verifier用binding mirrorを含め、candidate Verifierが署名済みreceiptとの同値を要求する。PR #96の完全head、現在のSummary binding、Owner承認scopeに固定し、現行v1.0 formal Verifyとcandidate v1.1 formal Verifyの両方がCONTINUEとなった後だけOwner最終merge判断へ進む。
- 順序: 鍵・test Anchor・本番backupの操作はOwner明示承認後。PR #96 merge後にだけ正式Anchorをv1.1へ原子的に切り替え、新formal mainでValidate・snapshot・read-only Verifyを再確認する。PR #95は現headのまま保留し、その後に新mainへ追従、全gateとSummary bindingを再生成して別Owner受入を得る。
- Trust Anchor履歴: `bootstrap_formal_commit`は初回Ver2 bootstrap起点の履歴値として維持する。今回のPR headやmerge commitに更新しない。repository identity・Owner actor ID・default branchも保持し、v1.1では公開鍵だけを追加する。
- 制限とrollback: これはPR #96のmigration専用手順であり、通常のOwner Acceptanceを恒久的に迂回しない。GitHub再観測後の編集・削除はofflineだけでは即時検出できず、receiptを5分で失効させmerge直前に再取得する。失敗時はmergeを停止し、本番Anchor切替後なら保護backupの同一bytesへ戻してHOLDを報告する。

## DEC-0093 — SG production Category catalog source identityを確認する

- 日付: 2026-09-27
- 背景: DEC-0090でPH/SG共通ShopeeCatalogClientのoffline契約をformal mainに採用したが、SG production Category responseのsource identityと現行normalizationとの互換性は未確認だった。OwnerがSG代表shop認証contextでの最小read-only確認を承認した。
- 決定: SG代表shopのshop_idをローカルexpected値とGoogle Sheet Access Token SourceのSG Bridge行で照合し、marketplace=SG、shop binding=MATCH、Source=AVAILABLEを確認した。Shopee production `https://partner.shopeemobile.com` の`GET /api/v2/product/get_category`を1 requestだけ実行し、API成功とresponse object、Category listを確認した。Refresh Token操作、別tokenへの切替、retry、Brand / Attribute APIは行っていない。
- Category Evidence: 現行`get_categories()`で2,285件を全件正規化できた。root 31件、leaf 1,962件、duplicate Category ID 0件、empty category name 0件、unresolved parent 0件、cycle 0件、rootへ到達不能 0件。`category_id`、`category_name`、`parent_category_id`、leaf判定を取得でき、rootからleafへのhierarchyを再構築できた。現行共通normalizationとの互換性はPASS。raw responseはファイル、DB、Git、Evidenceへ保存していない。production確認の実行時にrepository、credential、DB、Bridgeを追加変更していない。
- 判定と意味: `SOURCE_IDENTITY_PASS`。SG representative shopの正式認証contextで取得したproduction `/api/v2/product/get_category`を、SG production Category masterのsourceとして次工程のimport / acceptance検討に使用できる根拠を確認した。これはcatalog importや実catalog受入の完了ではない。
- 未受入: SG production catalog import、SG catalog DB replace、実catalog・実商品Category acceptance、SG Mapper live接続、SG Brand / Attribute runtime、SG SLS runtime、`listing_ready=true`、handoff、deploy、SG operation ACTIVE化、SG Minimum Beta完成、自動Category確定、自動出品。SG operationはINACTIVE、PHはACTIVE、MY / TH runtimeはNOT_STARTEDのまま。Safety、SLS、Candidate 15列、Prelisting Gate、DB schema、`ph.beta.operation`、`sg.safety.baseline`、governance/state.jsonは変更しない。
- rollback: 今回のdocs-only正本化は通常のrevertで戻せる。実行済みのread-only request自体は取り消せないため、確認事実の訂正が必要なら既存DECを書き換えず新しいDECで記録する。raw responseやcredentialの復旧操作は伴わない。
- 再検討条件: Shopee Category endpointまたはresponse schemaの変更、SG代表shop bindingの変更、Category ID・parent・leaf・hierarchyの不整合、現行normalizationとの差異が観測された場合はsource identityを再評価する。import / DB replace、実商品受入、Brand、SLS、listing_ready、handoff、operation ACTIVE化は別scope・別Owner承認とtechnical gatesで判断する。


## DEC-0094 — SG Category importのoffline変換経路とproductionデータ不足の停止境界を固定する

- 日付: 2026-09-28
- authority: OwnerがSG production Category catalog import offline preflightの実装・検証を依頼し、開始Git状態不一致のSTOP後、同一タスクでformal main起点のclean worktreeとrepo外Task Context作成、CONTINUE後の実装継続を明示承認した。既存dirty PH作業ツリーを編集・整理しない。
- 決定: SG-local pure function `build_sg_category_catalog_csv(categories, marketplace="SG")`で共通Clientのnormalized Category全件から正式6列CSVを生成する。IDはpositive integer、重複・空名・市場混在・不正parent・missing parent・cycle・root/leaf欠落・leafとtree構造の矛盾を拒否する。root parentは現行normalized値の0 / Noneだけをcanonical空欄へ変換し、ID昇順、UTF-8 BOM、LFで決定的に出力する。pathは親関係だけから生成し、入力pathや既存DBを参照しない。
- 再利用: 生成CSVを既存parse_sg_category_catalog / CategoryCatalogで全件validationし、既存SG-only transactional replaceへ渡す。SG-local parserとreplace入口にparent path + nameの完全一致validationを追加し、shared Coreのprefix validationだけで許されていた余分なsegmentを拒否する。Client、shared AI Core、Store、save_categories、DB schemaは変更しない。
- 確認済み: SG suite 63 passed、適合Streamlit環境でoffline全体1,515 passed、PH/SG protected回帰598 passed。fixture / tmp DBで決定的出力、階層、不正入力時DB不変、SG完全置換、旧SG ID削除、PH / schema不変、INSERT失敗時rollbackを確認した。保存済みSG mappingのcurrent catalog再validation、listing_ready=falseは既存testsで維持した。既定Pythonの古いStreamlitによる既存UI test失敗は適合環境で解消し、製品への互換修正は加えない。
- 判定: `IMPORT_PREFLIGHT_STOP`、reason=`PRODUCTION_NORMALIZED_CATEGORY_DATA_NOT_AVAILABLE_OFFLINE`。DEC-0093はraw responseを保存しておらず、既知のsource identity作業出力にもprovenanceと対象bindingを確認できるnormalized全2,285件を見つけられなかった。synthetic / fixtureだけのPASSを実production catalog受入またはIMPORT_PREFLIGHT_PASSにしない。本差分は検証済み候補であり、formal main採用を意味しない。
- 境界: production API、Google Bridge・credential変更、token本文表示・保存、production raw response保存、実運用DB replace、migration、SG実商品受入、Brand / Attribute / SLS runtime、listing_ready=true、handoff、deploy、operation ACTIVE化、自動確定・出品、MY / TH runtimeを許可しない。PH operation、Safety、Shared Battery、Community NG、Candidate 15列、Prelisting Gate、Resolver、Expansion、governance/state.json、両protected capabilityを維持する。SLS資産をCategory masterへ流用しない。
- Governance: SG-local実装でも既存path ownershipに従い変更分類はSHARED_COREとし、PH/SG protected gatesを適用する。範囲内commit / push / Draft PR / CI / read-only reviewまで通常開発承認内とし、formal mergeは別Owner Acceptance境界を維持する。
- 次の最小操作: binding / provenanceを確認できるproduction normalized全件をGit外offline入力として用意する。再取得が必要ならproduction read-only requestとnormalized全件のGit外保存に別Owner明示承認を得る。新しいAPI実行・保存を本決定だけで許可しない。
- rollback: 今回のSG-local code / tests / docs差分を通常revertする。DB migration、State、credential、PHのユーザー変更を戻す操作はない。force pushとdirty resetを行わない。


## DEC-0095 — 承認済みSG production Category GETの失敗をretryせず停止する

- 日付: 2026-09-28
- authority: Ownerが同一タスクで、SG representative shopの既存認証context、production GET /api/v2/product/get_category 1回、現行normalization、normalized全件だけのGit外保存とPR #98のtmp DB import検証を明示承認した。retry、Brand / Attribute API、raw response保存、credential表示・保存、Bridge・実運用DB変更、migration、SG ACTIVE化、listing_ready=true、merge、deployは禁止を維持した。
- 実行: PR #98 head eefceb039d8658e9481f6808b931638029384008のclean worktreeとread-only Verify CONTINUEを確認した。DEC-0093で使った既存Bridge参照とローカルexpected SG shopにbindingし、shop binding MATCH、Google Sheet Access Token Source AVAILABLEを確認した。production Category GETは1 request。request前のGit外試行記録で再実行を拒否し、redirectとretryを設けない。
- 結果: ClientがShopeeCatalogErrorを返し、normalized Category全件は取得できなかった。HTTP status / API error codeは記録しておらず、期限切れ・権限・response不整合等の原因は未特定。request前のhelper import失敗ではAPIを実行しておらず、rootから実行した1 requestだけを計数する。retryは0。
- 判定: IMPORT_PREFLIGHT_STOP、reason=PRODUCTION_CATEGORY_REQUEST_FAILED。今回の全Category / root / leaf / duplicate / empty name / missing parent / cycle / root到達不能 / path / leaf整合は未評価。今回のproduction normalized全件によるPH不変 / schema不変 / 古いSG ID削除も未評価であり、既存fixture結果を代用しない。IMPORT_PREFLIGHT_PASSまたはproduction catalog acceptanceに昇格しない。
- 保護: normalizedデータ、raw response、credentialの保存はなし。secret本文は表示しない。Bridge、実運用DB、schema、製品code、governance/state.json、両protected capability、SG operationは変更しない。Brand / Attribute API、merge、deploy、listing_ready=trueは未実行。Git外にはsecretを含まないrequest試行記録とSTOP集計だけを残す。
- 次の最小操作: Ownerが既存管理側でSG認証contextの現状を確認する。再requestによる原因確認が必要なら、安全なHTTP status / API error code記録を含む別の1回のread-only診断に新たなOwner明示承認を必要とする。今回の1回承認をretry許可へ拡張しない。formal main mergeは行わずOwner判断待ちで停止する。
- rollback: 今回のdocs-only結果記録は通常revertできる。実行済みread-only requestは取り消せない。試行記録を消して承認済みrequest枠を再利用せず、secret・Bridge・DBの復旧操作を行わない。


## DEC-0096 — 更新後SG認証で取得したnormalized全件のimport offline preflightをPASSとする

- 日付: 2026-09-28
- authority: OwnerがBridgeのSG Access Token更新を通知し、同一タスクでSG shop binding / Access Token Source再確認、production GET /api/v2/product/get_categoryをread-onlyで新たに1回、成功時だけnormalized全件のGit外offline保存とPR #98のtmp DB import検証を明示承認した。DEC-0095の失敗枠を再利用せず、別試行記録を保存する。retry、Brand / Attribute API、raw response・credential表示保存、Bridge・実運用DB変更、merge、deploy、SG ACTIVE化は禁止を維持する。
- 開始確認: PR #98 head eefceb039d8658e9481f6808b931638029384008で製品code / protected State不変。Task Contextを今回の承認へ更新した。古いlocal EvidenceはSTALE_BINDINGで一時HOLDだったため、現在HEADでGovernance Validate・PS5.1・PS7、offline 1,515 passed、PH/SG protected 598 passedを再実行し、local-validation CONTINUE / blockerなしを得てから本番requestへ進んだ。
- 取得: 既存SG expected shopとBridge SG行を照合しshop binding MATCH、Google Sheet Access Token Source AVAILABLE。Shopee production GET /api/v2/product/get_categoryは今回の承認で1 request、HTTP 200、retry 0、redirect追随なし。現行get_categories("SG")で全2,285件を正規化し、source Category countとの全件数一致を確認した。raw responseはmemory内だけとし保存しない。token・credential本文は表示保存しない。
- offline入力: Git除外outputs/sg-production-import-preflight-20260928-owner-recheck/normalized-categories.jsonにnormalized Categoryの5項目だけを保存した。provenanceはrepo/head/marketplace/endpoint/request数/取得時刻、shop・Bridge参照digest、normalizer・transformer source hash、normalized hashを含みsecretを含まない。normalized SHA-256は1b43516a56ad7d3a101f95b8adf1c38f242a105e5940c4efca95f0330e7d1f12。
- 全件検証: total 2,285 / root 31 / leaf 1,962。duplicate ID、empty name、missing parent、cycle、root到達不能、path不整合、leaf不整合はすべて0。DEC-0093参考値との差はtotal/root/leafすべて0。PR #98の6列CSV生成を入力逆順でもbyte一致と確認し、既存parserで全件validationを行った。catalog SHA-256は927651f1f3f5c01046669fd4834c7a2de71dc4d89f4f0cf25248b69a1c261cc6。
- tmp DB: 明示tmp DBにPH fixtureと旧SG fixtureをseedし、normalized全件catalogを既存SG-only replaceへ渡した。SG ID集合と保存件数・parent/path/leaf全件一致、旧SG ID削除、PH catalog / PH sync state不変、sqlite_master schema不変を確認した。実運用DBは開かずmigrationしない。
- helper補正: 初回は全検証成立後のWindows tmp DB cleanupでPermissionErrorとなったため、そのSTOP記録を保存した。helperのconnection close / GCだけを補正し、保存済みnormalized hashとprovenance・source hashを確認して、network / credential lookupを含まないoffline helperで全件validationとfresh tmp DB検証を再実行した。cleanup完了、追加API 0。製品codeを変更せず、初回STOP集計を最終PASSで上書きしない。
- 判定: IMPORT_PREFLIGHT_PASS、reason=ALL_REQUIRED_PRODUCTION_NORMALIZED_AND_TEMP_DB_CHECKS_PASS。最終EvidenceはGit除外offline-revalidation-report.json。DEC-0094 / DEC-0095の過去STOP事実は書き換えない。今回PASSはnormalized全件によるoffline import preflight成立を意味し、formal main採用・production catalog acceptance・実運用DB replace・SG実商品受入ではない。
- 保護・停止: Bridge、実運用DB、DB schema、製品code、governance/state.json、PH operation、両protected capabilityは不変。Brand / Attribute API、raw・credential保存、retry、SG ACTIVE化、listing_ready=true、merge、deployは未実行。PR #98はDraftのまま、追加commit / pushを行わず結果文書をローカル記録してOwner判断待ちで停止する。次工程の受入範囲は別Owner判断を必要とする。
- rollback: 結果docsは通常revertできる。実行済みread-only requestを取り消せず、試行記録を消して承認枠を再利用しない。DB、Bridge、credential、dirty PH作業ツリーを復旧・変更する操作はない。


## DEC-0097 — Owner受理済みIMPORT_PREFLIGHT_PASSを同じDraft PRへ正本化・公開する

- 日付: 2026-09-28
- authority: OwnerはDEC-0096のIMPORT_PREFLIGHT_PASSを受理し、同じタスクでCURRENT_WORK更新、既存DECを書き換えないDecision追記、関連tests / Governance、secret / 無関係混入確認、local commit、同じbranchへのpush、PR #98更新、CI / mandatory gates確認、read-only reviewを明示承認した。追加production APIとformal main mergeは承認に含めない。
- 正本化: 成功結果はDEC-0096の全2,285件 / root 31 / leaf 1,962、全不整合0、決定的6列catalog、全件validation、tmp DB SG-only replace、PH / schema不変、旧SG ID削除とする。DEC-0094 / DEC-0095の過去STOPとDEC-0096の初回cleanup失敗・offline補正の履歴を維持する。今回受理はoffline import preflight成立に限定し、production catalog acceptanceやformal main採用ではない。
- Git対象: CURRENT_WORKとDECISION_LOGの結果文書だけを追加公開する。既存PRのSG-local code / testsは変更しない。normalized全件、provenance、offline report、request試行記録、helper、tmp DB、credential、snapshotはGitへ含めない。過去DECを削除・書換えしない。
- 検証: 現在対象へbindした関連testsとGovernanceを再実行し、commit / push後は最新headのmandatory technical gates・protected PH / SG・secret checkを確認する。read-only reviewは成功証拠と製品差分の範囲・停止条件を確認し、未実行または古いheadをPASSとしない。
- 停止境界: PR #98はDraftを維持する。追加production API、Bridge / credential操作、実運用DB変更、migration、Brand / Attribute API、SG operation ACTIVE化、listing_ready=true、deploy、mergeを行わない。technical gate完了後も現在対象のOwner Acceptance SummaryとOwner明示的最終承認を待ち、formal main受入と実catalog / 実商品受入を別範囲で判断する。
- rollback: 公開した結果文書は通常revertできる。read-only request、Bridge、実運用DB、credential、dirty PH作業ツリーを変更・復旧する操作はない。force pushとdirty resetを行わない。


## DEC-0098 — PR #98のSG Category import offline実装とpreflight PASS結果をformal mainへ正式採用する

- 日付: 2026-09-28
- authority: OwnerはPR #98 head ac5cb0c7dc1f8564d7332c61e0a53095aac7ba10と現在の9項目Owner Acceptance Summaryを最終承認した。Provider鍵未設定によるHOLD後、PR #96でOwner管理下に作成した既存DPAPI保護鍵の一時利用、公開鍵一致確認、現在Summaryに対応するPR Conversation承認コメント投稿、fresh Provider / formal Verify、CONTINUE時のみmerge、merge後のformal main確認・Validate / snapshot / read-only Verifyを明示承認した。新しい鍵の生成・秘密鍵本文出力保存を許可しない。
- Owner Evidence: 既存DPAPI保護seedを同一ユーザーでメモリ内だけに復号し、Trust Anchor v1.1公開鍵との一致とGitHub actorのOwner numeric ID一致を確認した。Owner承認コメント https://github.com/hagiwara777/shopee-expansion-tool/pull/98#issuecomment-5864443804 をProviderがGitHubから取得して署名した。環境変数GOVERNANCE_OWNER_EVIDENCE_PRIVATE_KEYはProvider実行中だけ設定して即時解除した。秘密鍵を表示・保存・Git・Task Context・Evidenceへ記録せず、既存保護鍵とTrust Anchorを変更しない。
- Formal確認: 現在headのmandatory 6 gateとGitGuardian SUCCESS、CI Evidenceのhead/tree/config/workflow/job/run/actor bindingを確認した。fresh署名付きOwner EvidenceはPR番号、Owner、現在head、verification input hash、Summary binding、scopeに一致し、formal-acceptance VerifyはCONTINUE / blockerなし。comment取得、Provider、Verify、通常mergeをreceipt有効時間内に連続実施し、head一致を要求した。承認済みbindingとreceiptはGit除外accepted-pr98へ保存した。
- 正式採用: PR #98を通常merge commit 9a77f5c9754e7171f7f6cb186dbbb7ce5d17fae0でformal mainへ統合した。GitHub PRはMERGED、GitHub mainとorigin/mainと専用checkout HEADはmerge commitで一致し、accepted headはmerge commitの親に含まれる。offline SG-local normalized全件→決定的6列catalog→全件validation→SG-only replace経路と、完全parent/name path一致の制約、DEC-0096のproduction全件によるtmp DB preflight成立を正式成果とする。
- 検証事実: normalized全2,285件 / root 31 / leaf 1,962、duplicate・empty name・missing parent・cycle・root到達不能・path/leaf不整合すべて0。決定的出力、tmp DBのSG ID集合全件一致、旧SG ID削除、PH catalog / sync state不変、DB schema不変はDEC-0096のEvidenceによる。merge時にproductionを再取得せず、fixtureのみをproduction受入へ昇格しない。CI offline1,514 passed / 1 conditional skip、protected598 passed、read-only self-review指摘なし。
- merge後: formal main checkoutのtreeはaccepted headのtreeと一致した。Validate PASS、snapshot生成PASS、read-only Verify CONTINUE。governance/state.jsonは開始mainから不変、PH ACTIVE、SG INACTIVE、MY / TH INACTIVE / NOT_STARTED、両protected capability ACCEPTEDを維持する。別worktreeでcheckout中のlocal main branchやdirty PH作業ツリーを切替・更新・編集しない。
- 未受入: 実運用DB replace、実catalog / 実商品Category acceptance、SG Brand / Attribute / SLS runtime、SG operation ACTIVE化、listing_ready=true、handoff、deploy、自動確定・出品。今回mergeとIMPORT_PREFLIGHT_PASSをこれらの許可に読み替えない。追加production API、Bridge・Shopee credential変更、実運用DB変更、DB migrationは未実行。
- 次の単一作業: このmerge後のCURRENT_WORK / DEC-0098ローカル受入記録を公開する。PR #98のaccepted headを変更せず、別の通常文書差分として扱う。後続の本番DB・実商品受入等は別Owner scope判断を必要とする。
- rollback: PR #98のcode/tests/docsを通常revertする。DB migration、Bridge、credential、PH user data、Stateの変更やforce pushを伴わない。mergeしたread-only検証事実の訂正は既存DECを書き換えず新Decisionで記録する。


## DEC-0099 — SG実catalog・6実商品のCategory acceptance受入設計と実行承認境界を固定する

- 日付: 2026-09-28
- authority: Ownerの今回の依頼文による受入設計scope。実商品受入実行の別明示承認、formal main最終merge承認を推定しない。承認待ちはWAITING_APPROVALでありDONEではない。
- 前工程: GitHubでPR #98 / #99のMERGEDと最新mainを確認した。PR #99によるDEC-0098 / CURRENT_WORKの最終正本化は完了しており再実行しない。DEC-0096のIMPORT_PREFLIGHT_PASSとDEC-0098のoffline正式成果を実商品受入PASSへ読み替えない。
- 対象: 本物のSG production catalogと1つの実データ由来の正式SG Prelisting Gate eligible CSVから6商品を選ぶ。SG・全行ELIGIBLE・単一source_type・ASIN重複なしを必須とし、variation偏重を避け、可能なら3商品群以上、同一brand原則最大2件、容易な5件程度と曖昧な1件程度とする。synthetic、REVIEW / EXCLUDE、raw Candidate、複数source混合で代用しない。適切な実Gate入力がなければSTOPする。
- Catalog: DEC-0096のnormalized全件または現formal mainの正式変換処理による決定的6列catalogだけを用い、provenance / source / hash binding、total 2,285 / root 31 / leaf 1,962、全不整合0を確認する。artifact不足はSTOP、API再取得が必要なら別Owner承認までWAITING_APPROVAL。fixtureやSLS資産を流用しない。
- 隔離: 明示DB経路または子process限定LOCALAPPDATAの専用acceptance DBだけへload・mapping保存する。製品変更なしの既存経路を用いる。実運用PH / SG DB、PH operation / data、Bridge、credential、State、Safety、Shared Battery、Community NG、own penaltyを変更・解除しない。
- 人間確認: Categoryだけを商品単位に判断し、current ID存在・leaf=true・hierarchy完全一致path・商品の実体に対する妥当性を人間が確認する。Codex / AIは自動確定しない。判断不能は保存せず理由付き商品REVIEWとして残し、Safety / Brand / Attribute / SLS判断を混ぜない。
- PASS候補: 手順書の14条件をすべて満たし、6件人間レビュー、CONFIRMED最低4件、理由付きREVIEW最大2件、最低1実商品の保存→アプリ再読込/再起動→同じ入力再読込→current ID / path / leaf再validation・再利用を成立させる。全商品listing_ready=false、SG export / handoff閉鎖、production DB / PH不変、非対象runtime未実行、secret非表示・非保存を確認する。既存negative contract testsは実商品Evidenceと分け、人工catalog破壊を実商品受入MUSTに追加しない。
- STOP: catalog binding / hash / 件数不一致、不正Gate入力の通過、catalog外 / non-leafの確定、stale path再利用、PH / production DB影響、listing_ready=true、SG出口開放、安全停止解除、secret露出、artifact代用が必要な場合はscopeを拡大して修正しない。原因と最小修正候補をOwnerへ報告する。
- 正本化: 詳細手順はdocs/SG_REAL_PRODUCT_CATEGORY_ACCEPTANCE.md、進捗はCURRENT_WORK、タスク固有bindingはrepo外Task Context、実商品・raw catalog・DB・詳細EvidenceはGit除外artifactとする。Roadmap工程順は変えず重複追記しない。製品code / tests / Stateは変更しない。結果公開・formal main採用はmandatory technical gatesと現在対象のOwner Acceptanceおよび明示的最終承認を必要とする。
- 非対象: production DB replace、production API再取得、Bridge / credential変更、SG live OpenAI・AI精度Benchmark、Brand / Attribute / SLS runtime、listing_ready=true、export / handoff、deploy、SG ACTIVE化、自動確定・出品、MY / TH。他marketplace Brand ID流用も行わない。
- rollback: 隔離DBとGit除外acceptance artifactは受入完了後または失敗時に破棄可能とするが、過去request試行記録とDEC-0096 Evidenceを削除しない。文書差分だけ通常revertする。実運用DB・PH・Bridge・credentialの復旧を必要とする構成にしない。force push / dirty reset禁止。


## DEC-0100 — 実catalog bindingを確認し6実商品入力不足でCategory acceptanceをSTOPする

- 日付: 2026-09-28
- authority: Ownerが同じタスクで、既存SG production catalog Evidence / 実SG Gate CSV検証、適格6件選定、隔離DBだけでの人間Category確認・保存・再読込・保存済みCategory再validationを明示承認した。production API再取得、実運用DB、Bridge / credential、Brand / Attribute / SLS、listing_ready=true、handoff / deploy、SG ACTIVE化、自動確定・出品は禁止を維持する。catalog / 商品適格性問題時は代用・scope拡大せずSTOPする。
- Catalog確認: DEC-0096 normalized SHA-256とprovenanceが一致し、正式変換の決定的6列catalog SHA-256もDEC-0096値へ完全一致した。全件parser validation、total 2,285 / root 31 / leaf 1,962、parent / path / leaf整合、入力逆順でbyte一致を確認した。repo / SG / production endpoint / shop bindingのprovenanceも確認した。
- Source binding: 最初のhelperはGit blobのLF bytesだけで比較してnormalizer hash不一致として停止した。read-only診断によりprovenanceがnormalizerのWindows CRLF bytes、transformerのLF bytesを記録していることを確認し、それぞれhistorical bytesへ完全一致、現formal mainのGit blobも両方不変と確認した。normalized / catalogのhashは変換せず厳密一致。製品code・provenance・過去Evidenceを書き換えていない。
- Gate確認: 発見した3候補CSVは正規filenameで正式parserを通り、SG / ELIGIBLE / EXPANSION / ASIN重複なし。2ファイルは同じsynthetic 1商品で本受入には禁止。残る1ファイルは46商品がすべて同一brandで、同一brand原則最大2件を維持すると6件選定は不能（最大2件）。後者の実Gate出所の正式受入は未確定。合成商品の正式parser通過を実商品受入へ昇格しない。商品title / categoryのreplacement characterは0。
- 判定: STOP、reason=SUITABLE_REAL_SG_GATE_INPUT_NOT_AVAILABLE_IN_DISCOVERED_FILES。条件緩和・複数CSV結合・synthetic・商品情報改変・live取得で代用しない。6件選定0、人間レビュー0、確定0。商品REVIEW件数と保存済み実商品再validationは未評価であり0成功としない。隔離DBも作成せずload / mapping保存なし。
- Evidence: Git除外outputs/sg-real-product-category-acceptance/input-verification-report.jsonにcatalog / source / input hash bindingと最小集計・未実施を保存した。管理文書へ商品名・ASIN一覧・raw catalog・credentialを貼らない。既存DEC-0096 artifact / request記録を保持する。
- 保護: production API 0、実運用DB・PH data / operation・Bridge・credential・State・製品code / tests・Safety / SLS不変。Brand / Attribute / SLS runtime、listing_ready=true、export / handoff、deploy、SG ACTIVE化、自動確定・出品未実行。実商品受入PASS / formal main採用 / DONEではない。既存dirty PH変更に触れない。
- 次の単一作業: Ownerが実データ由来の1つの正式SG Gate eligible CSVで、6商品とbrand / variation等の選定条件を満たす入力を用意し、Codexが出所・parser・適格性を再確認する。既存の実行承認を維持し同じタスクで継続する。実運用DB replace等は別独立工程へ残す。
- rollback: 今回のdocs-only記録は通常revert。新規隔離DB / mappingはないためDB復旧操作は不要。過去Evidence・試行記録・PH / Bridge / credentialを削除・変更せず、force push / dirty resetしない。


## DEC-0101 — SG実商品Category acceptanceのbrand上限を目安へ戻し用途の異なる6件で継続する

- 日付: 2026-09-28
- authority: OwnerはDEC-0100のSTOPを確認し、同一brand原則最大2件は多様性確保の目安で必須条件ではないと明示修正した。同一brandを許し、既存46件から商品種類ができるだけ異なる6件を選び、可能なら異なるCategory候補へ分散する。同一family・色違い・容量違い等だけで6件を構成せず、6件が実質的に同じ商品群しかない場合だけ選定多様性理由のSTOPとする。既存の実行承認により同じタスクで継続する。
- 置換範囲: DEC-0099のbrand原則最大2件を必須とする運用解釈と、DEC-0100の単一brandを根拠とする再開入力要件だけを置き換える。両Decisionの本文、STOP当時の観測・hash・未実施履歴、他の受入条件を削除・上書きしない。catalog binding、正式SG / ELIGIBLE / 単一source_type / ASIN重複なし、synthetic禁止、6件人間レビュー・確定最低4件・理由付きREVIEW最大2件、保存再validation、安全停止、formal main承認は維持する。
- 選定方式: 同じ46件の正式CSVから元cellを変えず6件を抽出し、元source / Gate audit / Candidateとのbindingと選定理由をGit外記録へ残す。対象機器・用途の異なる商品familyを優先し、Category候補の違いは分散確認にだけ使い、Categoryを自動確定しない。収納ケースを対象機器本体と取り違えず、Keepa categoryだけで確定しない。
- 隔離実行: 製品codeを変更せず、専用DBとGit外wrapperから既存SG商品単位UI / validation / mapping保存を再利用する。LOCALAPPDATAは受入子process内だけを隔離領域へ向ける。読込・catalog load・表示準備はCodexが実行し、Categoryの妥当性と確定・未保存REVIEWは人間が商品単位で判断する。wrapperや抽出CSV・DB・商品詳細はGitへ追加しない。
- 禁止維持: production API再取得、実運用DB変更、Bridge / credential変更、Brand / Attribute / SLS runtime、listing_ready=true、export / handoff、deploy、SG ACTIVE化、自動Category確定・出品、MY / THは禁止。同一brand許容を既存Safety / Shared Battery / Community NG / own penalty解除へ拡張しない。catalog / 入力contract問題のSTOPは維持する。
- 正本化: CURRENT_WORKと受入手順を本Decisionに整合させる。工程順を変更せずRoadmap重複追記はしない。実商品PASSやformal main採用は人間レビュー・保存再validation・全14条件・mandatory technical gates・現在対象Owner Acceptance・明示的最終merge承認後だけ判断する。
- rollback: 今回のscope修正文書は通常revert。隔離DB / wrapper / Git外artifactは復旧可能な範囲で扱い、既存production Evidenceと過去STOP記録を保持する。実運用DB / PH / Bridge / credential復旧を必要とする構成にせず、force push / dirty resetは禁止。


## DEC-0102 — SG実catalog・6実商品の人間Category確認と保存再validationをPASS候補として記録する

- 日付: 2026-09-28
- authority: Ownerの既存実行承認とDEC-0101のscope修正を適用し、Ownerが受入専用画面で6商品のCategoryを人間確認した後、同じタスクで「レビュー完了」と通知した。通知は商品レビュー完了であり、結果PR / exact head / Summaryに対するformal main最終merge承認へ読み替えない。
- 入力・catalog: 元実Gate46件とCandidate49件 / Gate audit49件のELIGIBLE46件の対応、元cell改変なしの用途別6件抽出、正式SG / 全行ELIGIBLE / EXPANSION単一source / ASIN重複なしを確認済み。DEC-0096のnormalized / catalog厳密hash一致、production provenance / historical source / current source binding、全2,285件 / root31 / leaf1,962、全件validation成立を維持した。production API再取得0。
- 人間結果: 6件すべて商品単位レビュー、CONFIRMED6 / REVIEW0。人間が選択・確定したcurrent leaf Categoryは5つのroot / 5 Category IDへ分散した。Codexは分類の妥当性判断や確定操作を代行していない。全6件は同一brandの保護ケースだが、色 / 容量違いだけではなく対象機器 / 用途の異なる6familyである。標本制約を広い商品群の精度保証へ拡張しない。
- 保存・再読込: 初期ブラウザsessionの保存済み0件とOwner確定後6件保存を記録し、Codexが同じ画面をブラウザ再読込した。別session IDで同じhash bindingの正式6件Gateを再読込し、6件すべてUSER_CONFIRMED_REUSE、current Category ID存在 / path完全一致 / leaf=trueをDBとproduction catalogへ再照合した。保存再validationの最低1件条件を6件で満たした。新しい人工catalog破壊testは追加していない。
- 安全停止: 全6件listing_ready=false、SG export / handoffは閉鎖。実運用DBのfile digest / size / mtimeは開始時と一致。専用DBのPH初期seed全table行とschemaはfresh初期化referenceと一致し、SG-only load / mapping保存でPHを変更していない。既存StoreのPH seed1件による初回helper停止と補正はselection Evidenceに保持し、製品codeを修正していない。
- 判定: 14必須条件をすべて満たしCATEGORY_ACCEPTANCE_PASS_CANDIDATE。商品レビュー・6件保存・current再validation成立は実商品Evidenceであり、synthetic test結果を代用していない。現段階はローカル結果記録で、formal mainへの正式採用・SG実運用完成・タスクDONEは未完了。
- Evidence: Git除外outputs/sg-real-product-category-acceptance/reselection-v2/acceptance-result.jsonに14条件と件数、binding、human progress / reload event / operational baseline digestを保存する。商品名 / ASIN一覧、raw catalog、専用DB、wrapper、credential、snapshotをGitまたは管理文書へ大量保存しない。DEC-0099 / DEC-0100の履歴・過去STOP Evidenceを維持する。
- 非対象維持: production API、実運用DB replace、Bridge / credential変更、Brand / Attribute / SLS runtime、listing_ready=true、listing export / handoff、deploy、SG operation ACTIVE化、自動Category確定・出品、MY / THを実行しない。製品code / tests、State、Safety / Shared Battery / Community NG / own penalty、PH operationは不変。
- 次の単一作業: 結果文書の検証と最小差分公開を進め、mandatory technical gates / CIと現在対象Owner Acceptance Summary、明示的最終merge承認を成立させた後だけformal mainへ採用する。merge後のformal main / PR MERGED / binding / Validate / snapshot / read-only Verifyまで同じタスクで完了する。実運用DB replace等は後続の別独立工程へ残す。
- rollback: 結果・scope文書は通常revert。今回の専用DB / Git除外artifactは隔離領域に保持し、実運用DB・PH・Bridge・credentialの復旧を必要としない。過去request / production Evidence・Decision履歴を削除せず、force push / dirty reset禁止。


## DEC-0103 — SG実catalog・6実商品のCategory acceptanceをPR #100で正式採用し最終正本化後にSG Brandへ進む

- 日付: 2026-09-28
- authority: OwnerはPR #100の現在headとOwner Acceptance Summaryを確認し、SG実catalog・6実商品のCategory acceptance結果のformal main採用を最終承認した。続いてPR #100 mergeとmerge後検証を確認し、未更新のCURRENT_WORK / Decision等の最終正本化だけを同じタスクで継続し、docs-only commit / push / PR / formal mergeとmerge後検証後に本タスクを終了、次工程SG Brandは新規Codexタスクとするよう明示指示した。
- 正式Git事実: PR #100はMERGED。accepted headは`5aa666a3d66627491e77f0a0beec0702435a8d91`、通常merge後のformal mainは`6123c052bc105b8776def4e0717859de6d5d9b70`。merge時の最新mainとPR merge commitが一致し、accepted headとmerge commitのtree内容に差分なし、対象はCURRENT_WORK / DECISION_LOG / SG_REAL_PRODUCT_CATEGORY_ACCEPTANCEの3文書だけと確認した。これらは採用時の歴史bindingであり、次タスクで最新main確認を省略する固定値ではない。
- 正式受入: 必須CI6 gateのhead / tree / repo / workflow / job / run / actor bindingとPASSを確認した。現在対象の9項目Summary、Ownerの最終承認に対応するGitHub Ownerコメント、既存DPAPI保護鍵とTrust Anchor公開鍵の一致、fresh署名付きOwner Evidence、formal Verify CONTINUEを得て通常mergeした。Providerの初回はWindows文字コードで日本語応答の読込が停止し、UTF-8起動指定で解消した。製品code・鍵・Anchorを変更せず、失敗時点ではmergeしていない。
- 採用範囲: DEC-0101の用途別6family選定とDEC-0102の実行結果を正式採用した。CONFIRMED6 / REVIEW0、保存再利用6、current ID / path / leaf再validation6、全14条件成立、全件listing_ready=falseを維持。全6件は同一brandの保護ケース標本で、人間確定結果は5root / 5Category IDに分散した。広い商品群の精度保証やSG実運用完成へ拡張しない。
- merge後確認: 正式main / PR MERGED / accepted内容一致、PowerShell 5.1 / 7 Validate双方PASS、snapshot生成とread-only Verify CONTINUE、clean checkout、実運用DB fingerprint不変、SG INACTIVE / PH ACTIVE不変、State変更なしを確認した。PR #100のCIはoffline1,514 passed / 1 skipped、PH / SG protected回帰598 passed。skipはGit外ローカルBenchmark artifactがCIにない既存条件で、jobはSUCCESS。local offline1,515 passedと実商品Evidenceを区別する。
- 正本化不足の補正: PR #100の採用とmerge後検証は成立したが、formal mainのCURRENT_WORKと手順書はPASS候補 / 未完了表示のままで、DecisionもDEC-0102までだった。Git外Task ContextをCLOSEDとして先にタスク終了を宣言したことでは文書の最終正本化は完了しない。Owner指示により同じタスクを再開し、本Decisionをappend-only追記し、CURRENT_WORKと手順書の現在状態を正式採用済みへ更新する。DEC-0099 / DEC-0100 / DEC-0101 / DEC-0102の本文・STOP履歴・Evidenceを上書きしない。
- 次の単一作業: SG Brandのscope・受入条件定義を新規Codexタスクで行う。共通Catalog Client / Access Token Sourceの既存責務と未確定停止を維持し、Brand / No Brandの対象・人間確認・保存再validation・offline / live承認境界を先に定義する。本タスクではBrand実装・取得・runtimeを開始せず、新規タスクを自動作成・dispatchしない。Roadmapの後続SG工程順を変更せず重複追記しない。
- 終了条件: 今回の最終正本化文書をdocs-only PRで公開し、その現在対象のmandatory technical gates / Owner Acceptance / fresh Evidence / formal Verify CONTINUE後に通常mergeする。merge後の最新formal main、PR MERGED、採用内容、Validate / snapshot / read-only Verifyと文書整合まで確認してから本タスクを終了する。公開・merge未完了を再びDONEとしない。
- 非対象: production API再取得、実運用DB replace、Bridge / credential変更、Brand / Attribute / SLS runtime、listing_ready=true、export / handoff / deploy、SG ACTIVE化、自動Category確定・出品、MY / TH。製品code / tests / State / Safety / Shared Battery / Community NG / own penalty / PH運用は変更しない。
- Evidenceとrollback: Git外formal-adoption-result.json、accepted-pr100のcontext / Summary / Owner Evidence / formal Verifyとpostmerge-pr100のsnapshot / read-only Verifyを保持する。管理文書に商品名 / ASIN一覧 / raw catalog / credentialを貼らない。今回の最終文書だけ通常revertでき、実運用DB・PH・Bridge・credential復旧を必要としない。過去Evidence・request試行・Decision履歴を削除せず、force push / dirty reset禁止。

## DEC-0104 — SG Brand / No Brand Minimum Betaの設計を確定しdocs-onlyで正本化する

- 日付: 2026-09-29
- authority: OwnerはSG Brand / No Brand設計修正版のDESIGN_PASSを受理し、同じ設計タスクでDECISION_LOG / CURRENT_WORK / PROJECT_ROADMAP / READMEの4文書だけを正本化することを承認した。local編集・検証・commit・push・Draft PR・CI・read-only reviewまで同じタスクで継続する。formal mergeは現在headのmandatory technical gates完了、9項目Owner Acceptance Summary提示、Ownerの明示的最終承認後だけとする。
- 判定と現在地: DESIGN_PASS。これは実装前設計の成立であり、Brand製品実装、DB schema実体への適用、production Brand API、実商品Brand確認・受入は未実施。本docs-only承認をこれらの実行許可へ読み替えない。前工程のSG production catalog・6実商品Category acceptanceはDEC-0103の正式成果として保持し、再実行しない。
- 目的・入力: 全行ELIGIBLEの正式SG Gate入力から、人間確定済みCategoryをcurrent ID / path / leafで再validationした商品だけを対象とする。そのCategoryのBrand候補提示、人間Brand / No Brand確定、保存・再読込・current再validationまでをMinimum Betaとする。Brand側からCategoryを変更せず、Safety停止を解除しない。
- Brand authority: SG production `/api/v2/product/get_brand_list`を正式Brand ID authorityとし、Brand listはmarketplace + confirmed Category ID単位で扱う。PH / 他marketplaceのBrand ID、Amazon / Keepa brand、Resolver title、SLS資産、過去の文字列mapping、推測IDをauthorityにしない。Amazon / Keepa brandとtitleは候補探索Evidenceに限る。
- 初回判断: exact / normalized / title一致は自動候補提示のみ。文字列一致やconfidenceだけで新規mappingをCONFIRMEDにしない。人間が商品brandとcurrent Brand ID / nameを確認して確定する。
- real Brand保存・再利用: 既存brand_aliasesを最大限再利用する。SG、同じconfirmed Category、同じsource brand mapping、人間確認済み、今回のcurrent listに同じIDが存在、name一致、real Brand / No Brand区分一致をすべて必須とする。ID / name / 区分変更、stale、source正規化衝突・曖昧さは自動再利用せずREVIEW。No Brandをaliasへ保存しない。
- No Brand判断: Brand未発見はNo Brand選択を意味しない。今回のcurrent listにNo Brand選択肢が存在し、人間が商品実体を確認して明示選択した場合だけ確定する。No Brand ID=0を固定仮定せず、APIで確認した選択肢のID / nameを使用する。No Brand区分が曖昧なら確定しない。
- No Brand保存contract: 最小の`product_no_brand_confirmations` tableを設計する。必須fieldは`marketplace`、`candidate_asin`、`confirmed_category_id`、`no_brand_id`、`no_brand_name`、`source_brand`、`product_evidence_digest`、`user_confirmed`、`last_verified_at`。primary keyはmarketplace + candidate_asin + confirmed_category_id。商品ごとの確認を個別保持し、同じ商品・Categoryの再確認だけを同じ行へ保存する。今回はSGだけで使用する。
- 最小schema案: 新table 1つだけとし、IDはINTEGER（Category正整数 / No Brand非負整数）、文字列・digest・UTC日時はTEXT、user_confirmedは0 / 1制約、必須fieldはNOT NULLとする。人間の明示確認でのみuser_confirmed=1とし、last_verified_atは最後の人間確認日時とする。No Brandからreal Brandへ人間が変更した場合は、対象商品のNo Brand記録の無効化とreal Brand保存を同一transactionで行う。大きなhistory / Evidence frameworkを作らない。
- PH policy・note境界: 既存listing_brand_policiesとbrand_aliasesのschema・PHデータを変更・移行・廃止しない。共有policy keyやfree-text noteにASIN等を埋めて商品単位No Brand authorityにしない。旧policy / noteから新tableへ自動移行しない。
- Evidence digest: candidate ASIN、product title、Keepa brand、Keepa category、Resolver補助title、source_type、source_asinを固定field・固定順序のcanonical JSONとしてversion付きSHA-256化する。CSV行順・改行に依存させない。入力から得たsource brandを保持し、架空値で補完しない。digest / version一致は記録したEvidenceの一致を表し、未知の商品Factの保証へ拡張しない。
- No Brand再利用: SG、同一candidate ASIN、同一confirmed Category ID、current Category ID / path / leaf成立、product Evidence digest一致、source brand一致、user_confirmed、今回のcurrent Brand listにNo Brand存在、No Brand ID一致、No Brand name一致の全条件を要求する。1条件でも崩れたらREVIEW。失効した商品No Brand記録からreal aliasへ黙って切り替えない。
- strict current取得: 共通Clientを複製せず、第一候補は`get_brand_list(..., strict=True)`、既定値Falseとする。raw不正rowが通常normalizationで除外される前にopt-in検証し、SGの完全取得制御から使用する。PHの既存呼出し・production挙動を無条件に変更しない。通常BrandPageだけの後処理で、黙って除外されたraw行を完全検証済みと扱わない。
- strict検証: 非Mapping row、Brand ID欠損 / 不正（boolean・小数等）/ 負値、必要なname契約不成立、同一IDの内容矛盾、pagination不正、offset非前進・循環・異常なページ反復、marketplace / Category binding不一致をfail closedで拒否する。同一ID・同一name・同一区分の重複は計数して一意化できるが、矛盾を黙って除外しない。Client bindingと取得runの市場・Categoryを固定する。
- lazy取得・予算: 必要なCategoryだけ取得し、全Category一括収集を要件にしない。対象Categoryはoffset=0から終端まで取得する。初期内部予算はstatus=NORMAL、page_size=100、最大10 pages / Categoryであり、Shopee公式上限ではない。10ページ目でもhas_next_page=trueならcurrent完全取得・Brand不存在判定・replaceを行わず、Category単位REVIEW / 未完了とする。11ページ目以降へ自動進行せず、追加取得は別Owner承認とする。
- catalog replace: 正常終端まで全ページをメモリ内で収集・validationしたCategoryだけ、marketplace + Category ID単位でtransactional replaceする。旧対象Brand削除、current全件INSERT、sync state成功 / complete更新を単一transactionでcommitする。削除済みIDを残さず、他Category / 他市場を変更しない。途中page失敗、validation失敗、page上限到達ではreplaceせず、DB write失敗はrollbackする。
- currentの意味: 今回の取得sessionで正常完全取得し、DB commitまで成功した結果へ市場・Category・catalog digestをbindする。取得開始時に対象Categoryの今回current状態を失効させ、再利用・人間確定の直前に成功結果とDB内容を照合する。旧catalogを保持しても過去SUCCESS / is_complete / timestampだけで今回currentにしない。新session / 再起動後、再取得失敗、catalog変更では再確認が必要。画面rerunだけでAPIを自動実行しない。
- REVIEW: Brand複数候補、未登録、名前対応曖昧、Keepa brand欠損、manufacturerのみ一致、商品brandとの意味の違い、No Brand判断不能、pagination未完了、stale mapping、ID / name / 区分不一致は商品単位REVIEW。Brand REVIEWはSafety BLOCKではなく未確定の準備停止である。未確定を確認済みmappingとして保存せず、理由を表示しGit外受入Evidenceへ記録する。
- DB境界: 新No Brand tableは後続Minimum Beta受入の隔離acceptance DBへだけ明示初期化する。通常の既存production CategoryMapperStore初期化へ無条件に追加しない。実運用DBへのschema導入は将来の別判断。本正本化ではschema実体、PH / SG実運用DB、PH operation / data / schemaを変更しない。
- 実商品受入案: 約6件を目安にケース多様性を優先し、登録Brand正常系約3件、実No Brand最低1件、未解決 / 曖昧最低1件、残りを別Brandまたは別Categoryとする。固定比率や6ブランドを要求せず、Category acceptanceの同一brand 6商品だけでBrand全体を受入しない。安全な実No Brand商品がなければsyntheticで代用せず、No Brand実商品受入を未実施とし、全体受入PASSへ昇格しない。
- 受入条件: SG production Brand GET、shop / marketplace binding、pagination contract、Category別完全取得、実商品人間確認、Brand / No Brand明示確定、mapping保存、新session / 再起動後の読込・再取得・再利用、current ID / name再validation、stale非再利用、PH operation / data不変、production DB不変、Safety非解除、全件listing_ready=false、SG export / handoff閉鎖、Attribute / SLS未実行、credential非表示・非保存を必要とする。正常BrandとNo Brandの保存再利用、未解決商品の理由付きREVIEW保持を確認する。offline / synthetic testsを実商品Evidenceへ昇格しない。
- offline確認: 商品単位保存の非上書き、市場 / ASIN / Category / digest / source / user flag / ID / name不一致、No Brand fallback禁止、alias区分変更、raw strict不正、全ページ / 上限 / pagination異常、replace削除・rollback・PH不変、失敗後過去SUCCESS非採用、新session current失効、明示初期化、既存PH経路・SG停止境界を追加testsで検証する。これは後続実装のtest計画であり、新仕様の実行済みEvidenceではない。
- live承認境界: 今回production API / live requestは0。後続liveはSG代表shop、production get_brand_list、Category ID allowlist、request / page上限と再validation run数、Bridge read-only Access Token取得、shop / marketplace binding、retry方針、Git外Evidence保存範囲、隔離acceptance DB、実商品範囲を具体化した別Owner承認を必要とする。初期retry方針は自動retryなしで、失敗・上限後の追加requestを承認枠へ黙って追加しない。過去Category GET承認をBrand GETへ流用しない。
- 認証責務: DEC-0084〜0086を維持する。Refresh Token系列の唯一の管理者は既存在庫管理ツール、Mapperは専用BridgeからAccess Tokenをread-only取得しrefreshしない。Source明示ON時にlegacy tokenへsilent fallbackせず、Bridge取得成功をtoken freshness保証としない。token / credential本文をGit、DB、log、snapshot、Evidenceへ保存・表示しない。
- STOP: 市場 / shop / Category binding不一致、API契約・pagination異常、他市場ID混入、current確認なしのstale利用、No Brand自動fallback、production DB書込みやPH影響が必要、protected capability緩和、Safety解除、listing_ready=true、SG出口開放、secret露出、syntheticの実商品昇格、scope外Attribute / SLS / deploy変更が必要な場合は工程STOP。正常な内部page上限による未完了は対象Category REVIEWとして区別する。原因と最小修正候補をOwnerへ報告し、scope拡張して修正しない。
- 保護・非対象: SG operation INACTIVE、PH operation、ph.beta.operation / sg.safety.baseline、Safety / Shared Battery / Community NG / own penalty、Candidate 15列、Prelisting Gate、既存Source / Bridge / credential、Attribute / SLS runtime、SG listing_ready=false / export / handoff閉鎖を維持する。製品code / tests / governance/state.json、schema実体、実商品、live API、deploy、SG ACTIVE、自動確定・出品、MY / THを本正本化で変更・実行しない。
- 文書整合: CURRENT_WORKは設計完了・製品未実装と次工程を案内する。ROADMAPは工程順を変えずCategory import / 実商品acceptance完了、SG Brand設計完了・次に最小実装 / offline検証へ状態表記だけを合わせる。READMEは古いcatalog未完了表記を補正し詳細を正本へ参照させる。DEC-0103以前の本文・履歴・Evidenceを上書きしない。
- 正式化・終了: mandatory technical gates成功後に現在対象の9項目Summaryを提示してWAITING_APPROVALで停止する。Owner最終承認後に同じタスクでfresh Owner Evidence、formal Verify CONTINUE、通常merge、最新formal main / PR MERGED / 採用内容一致、Validate / snapshot / read-only Verifyと文書整合を確認して終了する。未確認・HOLD / HARD_STOP・merge未完了をDONEにしない。
- 次の単一作業: formal採用後のSG Brand Minimum Beta最小実装・offline検証は新規Codexタスクとする。目的・主要成果物が設計文書から製品へ変わるため、現在タスクで実装を開始せず新規タスクを自動作成・dispatchしない。live / 実商品受入はoffline成立後も別承認のままとする。
- rollback: 今回の4文書差分だけを通常revertできる。Decision撤回・訂正は新Decisionで記録し、既存entryや前工程のEvidence / request記録を削除・改変しない。製品、実運用DB、PH、Bridge、credential、Stateの復旧を必要としない。force push / dirty reset禁止。


## DEC-0105 — SG Brand Minimum Beta offline実装をPR #103で正式採用しmerge後検証を完了する

- 日付: 2026-09-29
- authority: OwnerはPR #103 head `7928086a2e870018943d9483acdc1684fc439fdf`と9項目Owner Acceptance Summaryを確認し、SG Brand Minimum Betaのoffline最小実装だけをformal mainへ採用する最終承認を与えた。production Shopee / Bridge API、実商品Brand / No Brand受入、production DB / schema変更、Attribute / SLS runtime、`listing_ready=true`、SG export / handoff、deploy、SG operation ACTIVE化、自動確定・出品は承認範囲外。
- Owner Evidence / formal: PR #103への現在head・verification input hash・Summary binding・offline限定scopeを持つOwner承認コメントをProviderがGitHubから取得し、既存CurrentUser DPAPI保護seedでfresh署名Evidenceを生成した。Trust Anchor公開鍵との一致を確認し、PR番号・Owner actor・head・Summary bindingにbindしたformal VerifyはCONTINUE、mandatory technical gatesは6 / 6 PASS。
- 正式採用: PR #103を通常merge commit `c1cfab9fef0283532fd3bf5968ea75c438179233`でformal mainへ採用した。GitHub上でPR MERGED、headは`7928086a2e870018943d9483acdc1684fc439fdf`。main treeとaccepted head treeの一致を確認し、製品差分に追加変更はない。
- 検証事実: local offline suite 1,615 passed。PR #103 CIはoffline 1,614 passed / 1 skipped、protected PH / SG 598 passed、Governance / PowerShell 5.1 / 7の各checkを含めmandatory 6 / 6 SUCCESS。skipは既存formal local Benchmark artifacts未配置による条件で、PASS数へ含めない。merge後のPowerShell 5.1 / 7 Validate、context snapshot生成、read-only Verify CONTINUEを確認した。
- 製品状態: Client marketplace / shop、request Category、取得run、session binding、strict raw Brand contract、最大10 pageのcomplete取得、Category単位transactional replace、商品単位No Brand Evidence digest / 明示確認、real Brand alias current再validationをoffline実装として採用した。API responseにmarketplace / Category echoがないため、server内部の別Category誤応答をresponse内容から独立検出したとは主張しない。No Brand tableは隔離acceptance DBへの明示初期化に限る。
- 保護・未実施: SG operation INACTIVE、PH operation / data / schema、`ph.beta.operation` / `sg.safety.baseline`、`listing_ready=false`、SG export / handoff閉鎖を維持する。production API / Bridge request、実商品受入、実運用DB schema適用、Attribute / SLS runtime、deploy、SG ACTIVE、自動確定・出品は未実施。offline / synthetic成果をlive acceptanceへ昇格しない。
- 次の工程: SG production Brand取得、expected SG shop照合、Category allowlist下のlive request、実商品Brand / No Brand受入には、対象・request予算・Bridge read-only取得・Evidence保存・隔離DB・商品範囲を定義した別Owner承認を要する。過去Category API承認を流用しない。
- rollback: offline code / testsと今回の最終正本化文書は通常revertできる。production DB migration / 復旧を伴わず、既存Category acceptance、PH、Bridge、credential、protected Stateを変更しない。


## DEC-0106 — Owner Acceptanceコメントを明示承認後のbinding搬送へ変更する

- 日付: 2026-09-30
- authority: OwnerはOwner Acceptanceの手動技術値コピー廃止を目的とする設計報告を受理し、方式Bを正式方針として指定した。credential separationは今回の必須条件としない。現在の方式でもGitHub actorだけから人間による手入力を独立証明できないため、その保証を新方式へ主張しない。
- 決定: mandatory technical gates完了後、現在のrepository / PR / exact headと9項目Owner Acceptance Summary、scopeをOwnerへ提示して`WAITING_APPROVAL`で停止する。Ownerがその対象のformal main採用を明示的に最終承認した後だけ、Codex/helperが現在のverification input hash、Summary bindingと承認scopeを含む定型`OWNER_ACCEPTANCE`コメントをOwner GitHub認証で投稿する。Owner silence、CI PASS、Codex判断、Summary生成を承認へ昇格しない。
- Evidenceの意味: コメントはOwner最終承認後に対象を固定するmachine-readable binding / transport Evidenceである。Owner本人がGitHub UIで手入力した独立human-origin proofとは定義しない。GitHub APIのOwner actor IDは認証アカウントを示すが、操作経路を区別しない。独立human-origin proofが必要になれば別Security工程で設計する。
- 維持: ProviderはGitHubからrepository identity、PR、head、Owner numeric actor ID、未編集コメント、撤回を再観測し、repo外Trust Anchor対応の専用鍵で署名する。Verifierはverification input hash、再計算したSummary binding、exact head、PR、5分以内のreceiptを検証する。mandatory checks、HOLD / HARD_STOP、protected capability、merge直前fresh再観測とformal Verifyを維持する。head、Summary、scope、主要リスク、protected capability影響の変更時はOwnerへ再提示し再承認を得る。
- 実装範囲: RUNBOOK、CURRENT_WORK、append-only Decision、最小コメント搬送helperとoffline testsのみ。製品機能、governance/state.json、Trust Anchor、Provider / Verifierの受入条件、credential保存、GitHub設定、Actions secret、branch protection / rulesetを変更しない。helperはformal mainに同一版が採用されるまで起動を拒否する。
- 移行境界: 本Governance移行PR自身は現在formal mainの旧方式で受入する。Owner本人が現在の対象にbindした完全形式のGitHub PRコメントを投稿し、既存Provider、fresh Evidence、formal Verifyで確認する。新方式で自己承認しない。formal main mergeは現在対象の9項目SummaryとOwner明示最終承認まで実行しない。
- rollback: 本変更を通常revertして手動コメント方式へ戻す。旧Decision・Evidenceを改変せず、force push、secret移動、Trust Anchor交換をしない。

## DEC-0107 — PR #105でOwner Acceptance方式Bを正式採用しGovernance taskを閉じる

- 日付: 2026-09-30
- authority: OwnerはPR #105の現在headとOwner Acceptance Summaryを最終承認し、旧方式の完全形式Owner AcceptanceコメントをPR Conversationへ投稿した。Provider再取得、fresh signed Owner Evidence、formal Verify CONTINUE後の通常merge、およびmerge後検証を指示した。
- 正式採用: PR #105をaccepted head `629c7fc7c6f3dc22335a09ffcbecf4d1d391b34f`から通常mergeし、formal main `1bfd4ee065b4121ef7e9d081d902a25cb9b40ef1`でMERGEDを確認した。これにより方式Bを正式運用し、OwnerのHEAD / verification_input_hash / summary_binding等のGitHub手動コピーを廃止する。Ownerの明示的な現在対象への最終承認は必須のままとする。GitHub OWNER_ACCEPTANCEコメントはその承認後に対象を固定するmachine-readable binding / transport Evidenceであり、Owner本人のGitHub UI手入力を独立証明しない。
- 検証: Governance tests 96 passed、protected regression 612 passed、mandatory CI 6 / 6 PASS。Provider再取得からfresh Owner Evidenceとformal Verify CONTINUEを確認してmergeし、merge後Validate、snapshot生成、read-only Verify CONTINUEを確認した。
- 維持: exact repository / PR / head / verification_input_hash / summary_binding / scope、Owner actor ID、Provider署名、repo外Trust Anchor、5分freshness、変更時再承認、編集・削除・REVOKED・API / Provider失敗時HOLD、formal Verify、merge直前fresh再観測を維持する。helperは最新REVOKEDをAPPROVEDで自動上書きせず、新しいOwner明示判断後の完全形式コメントだけを稀なfail-closed復旧経路として許す。Provider / Verifier / Trust Anchor / State / PH / SG protected capabilityおよび製品runtimeは不変。
- 文書正本化と次工程: CURRENT_WORKとRUNBOOKのPR #105限定例外・REVOKED時復旧境界の明確化、本記録の追記を行うdocs-only PRも方式Bを使い、technical gates後に9項目Summaryを提示してWAITING_APPROVALで停止する。明示的最終承認と正式helper経由のProvider / Evidence / Verifyを経てmergeした場合にGovernance taskをCLOSEDとし、次のSG SLS runtime工程は新規Codex taskとして開始する。
- rollback: 今回の正本化文書は通常revertする。DEC-0106その他の過去Decisionを変更せず、credential separation、第二GitHub account、branch protection / ruleset、Actions secret、Trust Anchor交換、製品runtime変更を行わない。


## DEC-0108 — SG SLSを専用offline最小runtimeとして実装し出口閉鎖を維持する

- 日付: 2026-09-30
- authority: Ownerはcurrent SG production Categoryとformal SLS SG assetのread-only設計監査をDESIGN_GATE_PASSとして受入し、同じtaskでoffline最小実装・tests・local commit・push・Draft PR・CI・read-only reviewを指示した。formal main mergeは現在対象のOwner最終承認まで行わない。
- 決定: B（SG専用最小追加）を採用する。load_sg_contextはcanonical / SGと各manifestのみを読み、hash・schema・transform・market・taxonomy・ID・source_refs・data-only metadata・明示notice scopeを検証する。SG専用evaluatorを追加し、PH load_ph_context / evaluate_ph_categoryのpublic behaviorを変えない。正式assetのaction=null / basis=DATA_ONLY_RUNTIME_NOT_EVALUATEDは維持する。
- 判定: runtime JOIN authorityはUnique Category ID exact matchのみ。人間確認済みCategoryとcurrent SG catalogの同ID / path / leafを前提とし、NOはquantityに優先してEXCLUDE、YES + No limitはALLOW候補、Shopee確認・数量・below 5kg・unknown / missing / unresolvedはREVIEW、未確定はUNCHECKED、資産またはcurrent catalog検証失敗はUNAVAILABLEとする。名前・Amazon / Keepa・fuzzy・親・旧ID推測によるmappingは行わない。
- notice / drift: SLS_SOURCE_TRANSFORM_V1の明示Pet Food scope（100906–100915）だけを検証して禁止noticeを適用し、別IDへ継承しない。exact ID取得後にcanonical pathとの明らかなidentity driftを停止させ、空白差は許容する。巨大なtaxonomy reconciliationは追加しない。現在catalogは時刻・件数だけのcacheを信用せず、全内容の再読取・構造検証・digestと資産versionでresultをbindしてrerun / 確定 / 再利用時に再評価する。
- 保護: SLSはSG recommendation上の独立状態で、Category / Brand / manual review / upstream Safetyを上書きしない。Brand操作がSLS REVIEW / EXCLUDEを解除しない。Shared Battery・Community NG・own penalty・COMMON / SG BLOCK / REVIEWを維持する。SG listing_readyは常にfalse、groups CSV / listing TXT / handoff / external exportを追加しない。DB approval table、SLS ALLOW永続化、migration、production DB変更、State変更はない。
- 検証・採用境界: 対象SG / PH / Guardrail tests、全offline pytest、protected.ph / protected.sg、Governance / PowerShell 5.1・7とcurrent head CIを必須とする。shared loader変更はSHARED_COREとして両protected capabilityを適用する。正確な実行結果はGit外EvidenceとGitHub checksを参照する。実装候補の成立はformal採用・live acceptance・SG Minimum Beta完成を意味しない。technical gates後に9項目SummaryとWAITING_APPROVAL、明示承認後に方式Bで受入する。
- 未実施・後続: production Shopee / Keepa / OpenAI API、Bridge、credential変更、実商品受入、production DB / schema、Attribute、deploy、SG ACTIVE、自動確定・出品は今回対象外。current catalogでSLS ruleがない5 leafはREVIEWとし、別ID fallbackしない。SG Minimum Beta完成判定はRoadmap Step 8、live工程・出口開放は別承認で扱う。
- rollback: 今回のcode / tests / 文書を通常revertする。DB migrationやproduction復旧は伴わず、正式assets、PH、State、credential、Trust Anchor、過去DecisionとEvidenceを変更・削除しない。

## DEC-0109 — PR #107 SG SLS offline最小runtimeを正式採用しmerge後確認を完了する

- 日付: 2026-10-01
- authority: OwnerはPR #107 head e11f71cc74e936ce637f461f6bf81ca83a9b65b4と9項目Owner Acceptance Summaryのscopeで、SG SLS offline最小runtimeをformal mainへ採用することを明示的に最終承認した。この承認はPR #107と提示scopeに限る。
- Owner Acceptance / formal: PRをready-for-reviewへ変更し、head / base a0217fd8922a4159a172f45bcd2b305e2098ee5a / CIをfresh確認した。formal main採用済みowner_acceptance_transport helperを使い、既存CurrentUser DPAPI保護seedとTrust Anchor v1.1公開鍵の対応をProviderで検証した。Owner承認後のbinding commentを反映し、ProviderがGitHubから再取得した署名付きOwner Evidenceはrepository / PR / owner actor / head / verification input / Summary binding / scopeへ一致した。formal Verifyはmandatory gates全件PASSでCONTINUEし、merge直前にもProvider再取得とformal Verify CONTINUEを確認した。秘密seed・秘密鍵本文を表示、保存、Evidence / Git / Task Contextへ追加していない。
- 正式採用: PR #107を通常mergeし、merge commit 10d54992caf45fa1ce5ad442b5c8dfc876af510dでformal mainへ統合した。GitHub PR MERGED、PR headがmainの祖先であること、GitHub mainとorigin/mainおよびformal main checkoutがmerge commitへ一致することを確認した。
- 検証: current head CIはgovernance.validate / governance.ps51 / governance.ps7 / tests.offline / protected.ph / protected.sgのmandatory 6 / 6 SUCCESS、およびGitGuardian SUCCESS。CI offlineは1,721 passed / 1 skipped、protected PH / SGは616 passed。local accepted-head offlineは1,722 passed。skipは既存formal local Category AI Benchmark artifacts未配置条件であり、PASSへ数えない。PowerShell 5.1 / 7 Validate、merge後snapshot生成、read-only Verify CONTINUEを確認した。
- 受入内容: canonical + SGのみを読むhash / schema / transform / taxonomy / source-ref validated loader、SG専用evaluator、current production Category ID / path / leaf・human confirmation・全content digest / asset version binding、独立SG Mapper SLS resultと理由表示UIをoffline採用した。Pet Food noticeはassetが明示bindするscopeだけに適用し、missing ID等を推測mappingしない。採用SG production catalog 1,962 leavesのread-only評価はALLOW候補1,799 / EXCLUDE95 / REVIEW68。ALLOW候補はCategory条件に限り、商品全体のSafety保証ではない。
- 維持 / 未実施: PH public runtime / assets / export contract、Shared Battery、Safety / Guardrail、DB schema / migration、State、SG operation INACTIVE、listing_ready=false、export / handoff閉鎖を維持した。production API / Bridge、credential変更、production DB、実商品/live SLS受入、Attribute、deploy、SG ACTIVE、自動確定・出品は未実施。Roadmap Step 8 / SG Minimum Beta全体の受入を意味しない。
- 後続正本化 / 承認: CURRENT_WORK、append-only Decision、READMEのformal-state表示を更新するdocs-only PRは、同じタスク内で別のOwner Acceptance対象とする。PR #107承認を後続PRへ流用しない。technical gates後、新PR専用9項目Summaryを提示しWAITING_APPROVALで停止する。明示承認後だけ方式Bに従う。
- rollback: PR #107 code / testsと本記録を通常revertする。production DB migration・復旧を伴わず、正式assets、PH、State、Trust Anchor、credential、過去DecisionとEvidenceを変更・削除しない。force push / dirty reset禁止。

## DEC-0110 — PR #108のDEC-0108訂正を正式採用しSG SLS offline runtime文書を最終正本化する

- 日付: 2026-10-01
- authority: OwnerはPR #108のaccepted head `335f1e2296212978a3c3caa6b38e433558832fd9`と提示済みOwner Acceptance Summaryのscopeでformal main採用を明示承認した。この承認はPR #108およびそのSummary scopeに限る。
- 変更・正式採用: PR #108でDEC-0108の既存文言をformal main上の原文へ完全に復元し、PR #107採用記録であるappend-only DEC-0109を維持した。通常merge commit `d1b6b8daf7062f15bcfd675e784242506fcb3f35`でformal mainへ統合し、GitHub MERGED、accepted head、最新main一致を確認した。
- Owner Acceptance / formal: formal mainの`owner_acceptance_transport` helperを用い、ProviderでOwner承認bindingをfresh取得し、fresh signed Owner Evidenceを生成した。merge直前のfresh再確認とformal Verify CONTINUE後に通常mergeした。mandatory technical gatesはcurrent headで6 / 6 PASS。
- 検証: merge後にPowerShell 5.1 / 7 Validate PASS、Context Snapshot生成、read-only Verify CONTINUEを確認した。Verifyのmandatory `governance.ps51` / `governance.ps7`は実行済みlocal evidenceへbindした。最新formal mainは`d1b6b8daf7062f15bcfd675e784242506fcb3f35`。
- 維持・未実施: DEC-0108の技術判断と既存scope、DEC-0109の採用記録を維持した。SG operation INACTIVE、`listing_ready=false`、export / handoff閉鎖を維持し、production / live API、実商品受入、production DB / schema、Attribute、deploy、SG ACTIVE、自動確定・出品は実施していない。
- 正本化・次工程: CURRENT_WORKをPR #108のformal採用・merge後検証済みへ更新した。SG SLS offline runtimeの正式採用で本taskの対象を完了し、Roadmap Step 8、live受入、runtime切替・出口開放は別scope・別承認とする。
- rollback: 本docs-only変更は通常revert可能。製品code、正式assets、PH、State、credential、Trust Anchor、過去Evidenceを変更・削除せず、force push / dirty resetを行わない。

## DEC-0111 — SG Minimum Beta Step 8の半自動完成候補とStep 9の承認境界を固定する

- 日付: 2026-10-01
- authority / 状態: Ownerは本Decisionを含むdocs-only候補を作成し、mandatory technical gates完了後にStep 8の9項目Owner Acceptance Summaryを提示して`WAITING_APPROVAL`で停止するよう指示した。`COMPLETION_GATE_PASS_CANDIDATE`はformal mainとread-only auditに基づく完成候補であり、Step 8のformal Owner受入ではない。このDecisionは候補PRの記録であり、Ownerの当該Summaryへの明示的最終承認およびformal main採用前は未採択である。
- 完成候補: 現行formal mainの成果と商品単位の人間確認により、候補 → SG Safety / Prelisting Gate → Category確認 → Brand / No Brand確認 → SLS確認 → 必須Attribute等の確認 → Seller Centerへの商品単位の手動出品までを少量商品で行う半自動Betaが成立可能である。read-only auditでは追加のBeta MUST実装は確認されなかった。既存BLOCK / REVIEW / Battery停止の維持は既存保護の継続であり、新規Beta MUST実装の残作業を意味しない。
- Betaで実現すること: 商品ごとのGate、安全停止、Category人間確認、Brand / No Brand人間確認、SLS Category結果の確認、Seller Centerでの必須Attribute・商品固有条件の人間確認、結果記録、手動出品を行う。小さな商品群で開始し、少量運用の成立を確かめる。
- Betaで実現しないこと: 全商品自動判定、production Brand GETを必須経路とすること、Brand / No Brand live API acceptance、自動Attribute、自動export / handoff、自動出品、完全live連携、全商品・全Categoryの精度・安全保証、Battery type自動確定、SDS自動判定・生成、G-form自動提出を要求しない。
- 人間作業: 商品画像・説明・商品実体の疑義、Safety上の追加確認、Category妥当性、Brand / No Brand、商品ごとのSeller Center必須Attribute、商品固有の発送・SLS条件を確認する。確認結果と出品対象を記録し、Seller Centerへ手動入力・出品する。Brand候補が見つからないことだけでNo Brandを選ばない。Seller Center上で解消できない場合、またはGate / SLS上の停止が残る場合はその商品を出品しない。人間確認はGateの`REVIEW`、BLOCK、SLS REVIEW / EXCLUDE / UNCHECKED / UNAVAILABLEを解除しない。
- 商品受入条件: 対象はSG Prelisting Gate `ELIGIBLE`、人間確認済みCategory、人間確認済みBrandまたはNo Brand、SLS `ALLOW`候補、Seller Centerで必須Attribute確認・入力済み、商品実体と発送条件に重大な未解決疑義なしをすべて満たすものに限る。`BLOCK`、未解決`REVIEW`、`EXCLUDE`、`UNCHECKED`、`UNAVAILABLE`、Category / Brand未確認、Battery / 危険物 / 許認可等の未解決疑義は出品対象から除く。既存Safety、Shared Battery、Community NG、own penalty、COMMON / SG BLOCK / REVIEWおよびSLS停止条件を緩和しない。
- Beta開始時の許容制約: `listing_ready=false`、SG export / handoff閉鎖、SG operation `INACTIVE`、production Brand GET・実商品Brand / No Brand live acceptance・production DB schema未適用、Attribute自動化なし、実商品SLS live acceptance未実施、Seller Centerまでの実操作未検証を許容する。`ELIGIBLE`、`SAFE`、SLS `ALLOW`候補は商品全体の安全保証ではない。実運用開始を含む承認ではない。
- 未実施事項の分類: production Brand GET / Brand live acceptance / production Brand schema / Attribute自動化 / 自動export・handoff / 全商品・全Categoryの拡張精度 / Battery type・SDS・G-form自動化は`BETA_AFTER`。Brand / No Brand・Category・Attribute・商品実体・発送条件の個別確認と記録は`HUMAN_MANUAL`。SLS実商品確認は追加の開始前live acceptance gateにせず、初回少量運用の商品ごとに人間が条件を確認・記録する（`HUMAN_MANUAL`）。その結果はSLS停止やGate `REVIEW`を解除しない。Seller Center end-to-end実操作と追加API / live連携は`BETA_AFTER`。listing_readyをtrueにすること、自動出品、SG ACTIVE化は手動Beta成立に不要で`NOT_REQUIRED`。既存BLOCK / REVIEW / Battery保護の維持は新規実装ではなく、必須の変更対象でもない。
- Beta後改善: 初回実利用でSeller Center E2EとSLS実商品ケースを記録する。実際に負担となったBrand取得、Attribute入力、export / handoff、人間確認を順に評価し、具体的に観測されたREVIEW / 停止事例へ対応する。新しい不明点だけを理由にBeta MUSTを増やさない。
- 承認境界・保護: Step 8のOwner Acceptanceはこの半自動完成線のformal main採用だけに適用する。Step 8受入時もSG operationは`INACTIVE`、`listing_ready=false`、SG export / handoff閉鎖を維持し、PHは`ACTIVE / ALLOWED`、SGは`INACTIVE / ALLOWED`、`ph.beta.operation` / `sg.safety.baseline`は`ACCEPTED`を維持する。Step 9のSG実運用開始、SG ACTIVE化、listing_ready変更、出口開放、production API / DB、deploy、自動出品はすべて別scope・別途明示承認を要する。
- 次の単一作業: current headのlocal validation、commit、push、Draft PR、mandatory technical gates、read-only reviewを完了し、9項目Owner Acceptance Summaryを提示して`WAITING_APPROVAL`で停止する。明示的なStep 8最終承認前にmergeしない。承認scopeをSG実運用開始へ拡張しない。Step 9はStep 8 formal main採用・merge後検証完了後に別途判断する。
- rollback / 非対象: docs-only差分だけを通常revertできる。Product code / tests、`governance/state.json`、Safety資産、PH operation、credential、production API / DB、Bridge、deploy、SG ACTIVE、export / handoff、`listing_ready`を変更・実行しない。過去Decisionはappend-onlyで維持し、force push / dirty resetを行わない。

## DEC-0112 — PR #110でSG Minimum Beta Step 8の半自動完成線を正式採用しmerge後確認を完了する

- 日付: 2026-10-01
- authority: OwnerはPR #110の提示済み9項目Owner Acceptance Summaryとaccepted head `223577f2b4b11b99e3d0dd96528398b96949d40d`を確認し、「SG Minimum Beta Step 8の半自動完成線をformal mainへ正式採用する」ことを明示的に最終承認した。承認はStep 8の完成線までで、Step 9のSG実運用開始を含まない。
- Owner Acceptance / formal: current headのGitHub Actions run #68の実artifactとworkflow / job / actor / commit / resultを照合し、mandatory technical gates 6 / 6 PASSをformal Verifyで確認した。Step 8専用のrepo外Task Contextを作成し、以前のTask Context不足によるHOLDを解消した。提示済み9項目を同じ内容でSummaryにbindし、formal main採用済み方式B helperでOwner承認scopeを搬送した。日本語scopeの取得時に文字コードエラーが出たためUTF-8で既存未編集コメントを再確認し、重複投稿せず復旧した。ProviderがGitHubからfresh取得した署名付きOwner Evidenceとformal Verify CONTINUEを連続して確認してから通常mergeした。Trust Anchor・credentialを変更せず、署名seedをログ・Git・Task Context・Evidenceへ追加していない。
- 正式採用: PR #110を通常merge commit `7529025744922f4c80ee604098c56c5e73d58cd6`でformal mainへ統合した。GitHub MERGED、accepted headがmainの祖先であること、採用4文書の内容一致、GitHub main / origin/main / 隔離formal checkoutの一致を確認した。無関係なdirty cloneと古いlocal mainを無断変更しない。
- merge後検証: formal main上のPowerShell 5.1 / 7 Validate PASS、Context Snapshot生成、read-only Verify CONTINUEを確認した。Git外の受入snapshot、Summary、CI artifact、Owner Evidence、formal Verifyとmerge後結果を保持する。未実行のlocal testをPASSへ昇格しない。
- 採用内容: DEC-0111で示した`COMPLETION_GATE_PASS_CANDIDATE`の半自動完成線を正式採用した。Gate ELIGIBLE、人間確認済みCategory・Brand / No Brand、SLS ALLOW候補、Seller Center必須Attribute・商品固有条件確認済みの少量商品だけを対象とする。未解決停止・疑義のある商品は出品せず、既存Safety / Battery / SLSを人間確認で解除しない。追加Beta MUST実装は確認されていない。DEC-0111の6項目と分類は変更しない。
- 維持・未実施: PH ACTIVE / ALLOWED、SG INACTIVE / ALLOWED、両protected capability ACCEPTED、listing_ready=false、SG export / handoff CLOSED、Safety非緩和を維持する。production API / Brand GET / Bridge / DB / schema、deploy、SG ACTIVE、出口開放、自動出品は未実施・未承認。Brand / SLS live acceptance、Seller Center E2E、全商品・全Categoryの安全保証は成立済みと扱わない。
- 最終正本化・次工程: CURRENT_WORK、README、Roadmapの現在表示をStep 8正式採用済みへ最小更新し、本Decisionをappend-onlyで追加する。同一タスクのdocs-only最終正本化候補はPR #110と別head / Summaryの受入対象であり、technical gatesとread-only review後に9項目Summaryを提示してWAITING_APPROVALで停止する。PR #110の承認を流用してmergeしない。Step 9は未承認・未着手で、このタスクでは進めない。
- rollback: 最終正本化文書だけを通常revertできる。過去Decision、製品code / tests、State、Safety資産、PH、Trust Anchor、credential、過去Evidenceを変更・削除せず、force push / dirty resetを行わない。

## DEC-0113 — PR #111でStep 8最終正本化を正式採用しStep 8を終了する

- 日付: 2026-10-01
- authority / scope: OwnerはPR #111のaccepted head `148b9d53600583b12bbde6d21655258d87424695`とdocs-only正本化Summaryを確認し、PR #110のStep 8正式採用・merge後検証結果を記録する4文書の最終正本化を明示承認した。この記録補正はその既承認scope内の事実をCURRENT_WORKとappend-only Decisionへ反映するだけで、Step 8の完成条件やStep 9 scopeを変更しない。
- Owner Acceptance / formal採用: PR #111のOwner最終承認後、GitHubのcurrent-head mandatory technical gates 6 / 6 PASS、fresh署名付きOwner Evidence、formal Verify CONTINUEを確認後に通常mergeした。PR #111はMERGED。accepted headはmainの祖先であり、merge commitは`9d37cf1a60475b6e1a0347744397cf9833f7cfc7`。GitHub main、origin/main、formal checkoutの一致とaccepted内容一致を確認した。
- merge後確認: formal main上でPowerShell 5.1 / 7 Validate PASS、Context Snapshot生成、read-only Verify CONTINUEを確認した。`governance/state.json`、PH operation、SG operation、protected capabilitiesは不変。旧Step 8 Task ContextはCLOSEDのまま保持し、本補正用Task Contextを分けて管理した。
- docs-only対象: PR #111は`docs/CURRENT_WORK.md`、`docs/DECISION_LOG.md`、`docs/PROJECT_ROADMAP.md`、`README.md`を更新した。既存DEC-0111の半自動完成線と完成条件、DEC-0112のPR #110正式採用記録は変更しない。PR #111のmerge後受入結果を本Decisionに記録し、現在のStep 8状態をCLOSEDとして明確化する。
- 完了状態・保護: Step 8は正式採用・最終正本化まで完了しCLOSED。新規Beta MUST実装の残作業はない。SG operation `INACTIVE`、`listing_ready=false`、SG export / handoff CLOSED、PH `ACTIVE / ALLOWED`、SG `INACTIVE / ALLOWED`、`ph.beta.operation` / `sg.safety.baseline` `ACCEPTED`、既存Safety / Battery / SLS停止条件を維持する。Brand / SLS live acceptanceとSeller Center E2Eは未実施。production API / DB変更、deploy、SG ACTIVE化、自動出品は未承認・未実施。
- 次工程境界: 次の独立工程はRoadmap Step 9「SG実運用」。Step 9は未承認・未着手であり、新規Task Contextを用いる別タスクとOwnerの別途明示承認後にだけ開始できる。本Step 8補正タスクでは着手しない。
- rollback: 今回のCURRENT_WORKとDecision追記は通常のdocs-only revertで戻せる。既存Decision、State、製品code / tests、Safety資産、credential、Trust Anchor、過去Evidenceは変更・削除しない。force push / dirty resetを行わない。

## DEC-0114 — Post-Merge Stabilityと正本化連鎖防止を恒久Governanceルールにする

- 日付: 2026-10-01
- 背景: 同一成果物の採用結果を記録する文書PRに短命状態を置き、そのPRのmerge・検証成功を再度Gitへ記録すると、正本化PRが再帰的に必要になる。
- 決定: Git管理文書の現在状態は、そのPRを今formal mainへmergeした直後にも正しくする。再開案内と恒久判断は成果物と同一PRへ含める。CURRENT_WORKはformal状態、完了工程、次の独立工程、既知制約、停止条件、Required Decisionsだけを保持し、PR処理状態はGitHub、タスク固有状態はrepo外Task Context、検証結果はEvidenceへ置く。
- 終了・Decision必要条件: 成果物・tests・安定した正本文書・mandatory technical gates・Owner Acceptance・merge・formal main確認・Validate・snapshot・read-only Verifyを経て、新しい実障害・正本矛盾・恒久判断変更がなければTask ContextをCLOSEDとして終了する。成功記録だけの追加PRやDecisionは作らない。恒久仕様・Safety / Risk方針・完成条件・Owner承認境界・Governanceルール・再利用する設計判断が変わる場合だけDecisionをappend-onlyで追加する。
- 受入前確認: 変更したGit管理文書を反実仮想mergeでread-only確認し、merge直後に不成立となる現在状態があればPOST_MERGE_STABILITY_FAILとして同一PR内で修正する。PASSは9項目Summaryの確認済みEvidenceへ含め、項目数・binding・明示的最終承認を維持する。
- 連鎖fuse: 同一独立成果物の前の正本化 / closeout状態を補正するだけのdocs-only corrective PRを2件目として提案する場合、FORMALIZATION_LOOP_DETECTEDで自動継続を止め、新PR作成前に不安定だった原因、volatile stateの記録先、正本責務混同、新PR不要で判断できるかを分析してOwnerへ報告する。PR番号の増加や独立した実障害だけでは発火しない。
- 置換範囲: DEC-0103 / DEC-0107 / DEC-0109 / DEC-0110 / DEC-0112 / DEC-0113等の過去正本化・closeoutにある、採用・merge後検証成功を記録する後続文書PRを通常終了工程とする部分だけを本ルールへ置き換える。既存本文・受入事実・Evidenceは保持し、Step 8完成条件とStep 9別承認境界は変更しない。
- 最小検査: 専用docs contract testでCURRENT_WORKの明確なtransient markerをmandatory tests.offlineから検出する。現在文書とstable textのPASS、marker差込みのFAILを確認する。一般語・accepted済み過去PR参照は許容し、歴史正本DECISION_LOGへ禁止語検査を適用しない。詳細手順はRUNBOOK「Post-Merge Stability」に置く。
- 保護・非対象: DEC-0072 / DEC-0073 / DEC-0106の承認・Trust契約、mandatory gates、HOLD / HARD_STOP、PH / SG protected capabilityを維持する。engine / manifest / schema / gate定義、governance/state.json、製品runtime、Safety / Battery / SLS、live API、production DB、credential、deployを変更しない。Step 8はCLOSED、次の独立工程Step 9は未承認・未着手で、別タスク・別Owner承認を要する。
- rollback / 再検討: 本ルールとdocs contract testを通常revertできる。判断の撤回・訂正は新Decisionへ追記し、歴史本文・過去Evidenceを削除しない。false positive、意味確認漏れ、正本矛盾が実際に見つかった場合だけ最小補正を判断する。force push / dirty resetを使わない。

## DEC-0115 — PH / SGの操作入口を共通化し未提供機能の境界を表示する

- 日付: 2026-10-04
- authority: OwnerはPH / SGで国ごとに操作が変わる負担を減らすことと普段の起動先・データ調査を依頼し、範囲を「まず操作を統一し、SGの機能差は表示する」と指定した。
- 決定: Category Mapper入口でPH / SGを選択し、商品CSV、Category、Brand / No Brand、発送条件（SLS）、出品準備情報の段階とCategory検索・採用ボタンの表記を共通化する。選択していない市場の画面・入力・操作を実行しない。PHは既存グループ確認、SGは既存商品単位確認を維持し、SGのcatalog取込を設定領域へまとめる。
- 機能差: SGはAI候補提示、Brand / No Brand確認結果のUI保存、CSV / TXT出力を未提供として明示する。Seller Centerでの人間確認案内は確認済み記録や停止解除へ昇格しない。SG listing_ready=false、export / handoff CLOSED、operation INACTIVEを維持する。
- 非対象: Safety / Battery / SLS判定、Candidate schema、DB schema、catalog内容、認証契約、実API、SG実運用開始、PH稼働環境、ショートカット変更、データ移行、credential変更、deploy、MY / THを変更しない。起動先・保存データの所在調査は読み取りだけとし、設定値や商品本文を報告へ出さない。共有UIはPH / SGの既存保護を回帰確認する。
- 完成線: この操作統一を新しいBeta MUSTやSG実運用開始前の追加live gateへ昇格しない。SG Step 8の受入内容とStep 9別承認境界（DEC-0111〜0113）は維持する。正式採用には既存technical gatesと現在対象のOwner最終承認を必要とする。
- rollback: UIと関連テスト・説明文書を通常revertで戻せる。実運用DB、PH稼働環境、認証、過去Evidenceの復旧を伴わず、既存Decisionを変更しない。

## DEC-0116 — 固定PH Betaを各国の初期目標としSG機能統一から共通化する

- 日付: 2026-10-04
- authority: Ownerは現状PH BetaをSG / MY / THの最初の到達目標とし、共通機能を共通moduleで更新、判断材料を国別に更新する方針を指定した。SGをPHへ揃え、その後MY / THの仕組みを作る順序を確認し、このチャットで開発を進めることを指示した。
- 決定: 2026-10-04のPH Betaを固定基準とし、SGの画面と支援機能を揃える。後続PH改善で初期目標を自動的に増やさない。機能目標と共通 / 国別分離、実装順はPH_BETA_MARKET_PARITY.mdを正本とする。現状の共通基盤を再利用し、国ごとのツール全体複製は行わない。
- 履歴と置換: DEC-0111〜0113の半手動SG Beta受入は保持するが、これだけでPH相当の機能統一済みとは扱わない。DEC-0115の操作統一のみという当面の開発scopeを、PH相当を目指す段階的local開発へ拡張する。RoadmapはSG機能統一をSG実運用判断・MY / TH展開より先に置く。従来の独立工程ごとの新チャット指定は今回Ownerが指定した同じチャット内の開発には強制しない。repo外Task Contextのscopeを更新し、既存gateと停止条件は緩和しない。
- 最初の実装: PH / SG共通のBrand候補検索と、既存strict SG Brand契約を使う隔離offlineの画面部品。人間の選択・商品確認、保存・current再検証、商品情報やcatalog変更後の未確認化を検証する。No Brandの実IDを保持し、商品間へNo Brand確定を転用しない。PHのUI / 保存契約とSG SLS・Safety停止を維持する。
- 承認境界: scope内local開発とoffline testは今回の開発指示で進める。live API / 有料API実行、通常DB migration、credential、起動先変更、deploy、formal main merge、SG実運用開始は本開発指示だけで実行しない。今回のBrand部品を通常SG画面へ接続せず、実API factory・環境変数による有効化を追加しない。SG listing_ready=false / export閉鎖は今回の実装で変更しない。出口開放を目指す後続設計・開発と、実運用出口の正式採用は区別する。
- MY / TH: 同じ固定PH基準と共通moduleを使う後続目標。SG段階ではMY / TH runtime・国別ルール実装・Stateを変更しない。
- 保護とrollback: PH / SG protected capability、既存Safety / Battery / SLS、現在の通常DB・起動環境を維持し、local code / tests / 文書差分を通常revertできる。過去DecisionとEvidenceを変更・削除せず、未実施live確認をPASSにしない。

## DEC-0117 — SG隔離開発版で一連操作を接続しlive採用と分ける

- 日付: 2026-10-04
- authority: Ownerの「残りの開発も終わらせてください」に基づき、DEC-0116内のlocal開発を個別部品から操作可能な隔離入口まで接続する。live・通常環境移行・formal採用の承認をこの依頼から推定しない。
- 決定: SG用の別入口・起動script・合成再生資料を用意する。明示初期化した新規隔離DBへ、現在SG catalog、Candidate・説明・未評価画像を取り込み、Category AI候補・人間採用、Brand / No Brand、属性、商品説明・画像確認、共通formatterの準備候補CSV / TXTまで接続する。shop / Category / offset、商品・catalog・request profile、画像requestへの結合を検証し、不一致・欠落で外部接続や架空の候補へfallbackしない。
- 画像対象: 隔離開発用の一括対象は、現在SG Gate ELIGIBLE・SAFEでKeepa資料がある商品全部。PH専用4 rootの適用やSG合法性の推測をせず、選択だけでは問い合わせない。明示一括実行前に対象全件の人間確認を失効させ、全体失敗で出力を閉じる。これをliveの費用・運用方針の受入と扱わない。実接続時の実費・対象範囲は採用時に判断する。
- 保存・変更: 既存DBを上書き・複製・移行しない。再生資料の変更・削除・再初期化で結果・確認widgetを破棄する。画像素材は再生資料としてsession内に保持するが、評価結果・DBには画像bytesを保存しない。再生資料のSHA一致はserver由来・現況・所有者受入を証明しない。
- 維持: 通常PH / SG画面、State、Safety / Battery / SLS、credential / Bridge、通常起動先、SG listing_ready=false / export CLOSEDを維持する。通常経路のAPI factory・環境変数による有効化は設けない。MY / TH runtime・国別Ruleには着手しない。
- 完成・次工程: offlineの一連確認とlive実精度・認証・正式出力・環境採用は別である。手順と採用時の説明はSG_LOCAL_REVIEW_GUIDE.mdへ置く。ローカル結果だけでSG機能統一・実運用・正式採用の完了を宣言しない。
- rollback: 追加入口の利用を停止し、コード・tests・文書を通常revertできる。通常PHデータと過去Decision / Evidenceを変更・削除しない。

## DEC-0118 — SG隔離実接続を最大3商品・OpenAI上限1米ドルで検証する

- 日付: 2026-10-04
- authority: Ownerは隔離環境で最大3商品、OpenAI費用上限1米ドルの実API検証を明示許可し、既存シートからAccess Tokenを取得する仕組みの再利用を指定した。
- 決定: 通常画面と別の明示CLIに限定してKeepa / Shopeeの読み取りとOpenAI接続を検証する。商品数・SG shop・隔離DBを結合し、有料問い合わせ前に保守的な費用上限を予約する。再試行・timeoutも予約を返却せず、上限を超える問い合わせと既存実行ledgerの再初期化を拒否する。費用予約は実際の請求額の証明ではない。
- 認証: 既存Access Token Sourceの優先順位と明示ON時のfail-closedを再利用する。指定Bridgeは隔離processだけへ設定し、認証失敗時に別tokenへfallbackしない。元管理シートからの直接取得、Mapper refresh、シート編集・権限変更・通常設定の変更は実行しない。
- 置換範囲: DEC-0116 / DEC-0117のlive未承認境界を今回の少量検証に限り置換する。通常SG UIのlive閉鎖、SG operation INACTIVE、listing_ready=false、formal export / handoff CLOSED、PH環境、MY / TH未着手は維持する。接続成功からCategory / Brand・画像の人間確認や正式採用を自動生成しない。
- 完成と停止: transport確認と人間確認を含む一連実用確認は区別する。認証・取得資料の不一致・Safety停止・予算上限等は未確認として記録し、過去受入を新しい実接続PASSへ転用しない。通常移行、起動先変更、正式出口採用、自動出品は別scopeである。
- rollback: 隔離CLIの利用を停止し、追加コード・tests・文書を通常revertできる。通常DB・認証・過去Evidenceの復旧を伴わない。

## DEC-0119 — PH同期を維持しSGの自動受渡しを別Bridgeへ準備する

- 日付: 2026-10-04
- authority: OwnerはSGの自動同期調査後、判断・承認が必要になるまで作業を進めるよう指定した。Google側の反映・実行・共有変更をこの指示から推定しない。
- 背景: 設置済みの既存同期projectはPH専用であり、同じBridgeにSG行が存在してもこの処理では更新しない。共通Sourceは全行を検証するため、SGの空欄化・不正行が同じBridgeのPH取得も停止させ得る。
- 決定: 既存PHコード・5分トリガー・Bridgeを保持し、同じApps Script projectへのSG追加ファイルと別のSG専用Bridgeを準備する。共通read-only Sourceを再利用し、通常SG factory・通常設定を有効化しない。SGのexpected shopは既存設定へbindし、元表・Bridgeのshop不一致を停止する。元表はSG行のB / C / Eだけを読み、Refresh Token更新責務を既存在庫管理ツールに保持する。
- 停止・保護: SG旧tokenを先に空にし、取得・検証・書込み・読戻し失敗でSG側を無効化する。PH / 元表をSG targetにした場合は書込み前に拒否する。SGの失敗でPHを変更しない。全面書込み障害やlock取得不能時の旧token消去、3列contractによるfreshness独立証明は保証しない。
- 承認境界: local候補コード・tests・反映手順を先に完成する。新SGシート作成、既存readerへのViewer共有、Google側コード / Script Properties追加、初回同期実行と5分トリガー有効化は具体的な対象を提示して別承認を得る。現Google状態はこのDecisionだけで変更しない。SG同期の受入、少量実API確認、正式利用・通常移行を区別する。
- 維持・rollback: PH protected capability、SG Safety、SG INACTIVE / listing_ready=false / formal export CLOSED、MY / TH未着手を維持する。local候補を通常revertできる。反映後の復旧はSGトリガー停止・SG専用token消去・SG reader停止に限定し、PHを保つ。詳細はSG_ACTIVATION.mdを参照する。


## DEC-0120 — 専用末端全件比較と関連分類探索後に適切なOthersを候補にする

- 日付: 2026-10-04
- authority: Ownerは大分類を探索開始点として見直し可能にし、専用末端を全件比較、関連別分類も確認した後で適切なOthersを候補にする方向の修正と数商品のAPI testを明示承認した。
- 決定: 市場共通の明示V2探索moduleを隔離SGへ用意する。最初の大分類内の専用末端全件を最大80件のbatchへ分割し、すべてのbatchを評価して候補を比較する。専用候補がない場合に別の関連大分類を探す。最大3大分類の上限到達は探索完了と扱わず保留する。
- Others境界: 商品の正体・用途を理解でき、専用カテゴリーがなく、残る大分類に適合する関連先がないと判断した場合だけ、探索済み大分類のOthers末端を比較する。親pathに適合しないOthersや商品不明を推測で採用しない。API失敗・不正ID・不完全探索はOthers fallbackへ変換しない。候補は現在catalog ID/path/leaf再検証と人間採用を必要とし、正解・Safety保証ではない。
- Version・保護: V1 Benchmark promptとPH通常AIを変更しない。V2のprompt/hash/探索契約を区別し、旧評価の性能保証を転用しない。SG_OFFLINE_REPLAY_V2と明示隔離CLIでだけ選択する。PH/SG Safety・Battery・SLS、DB schema、通常起動先、SG INACTIVE/listing_ready=false/正式出口閉鎖、MY/TH未着手を維持する。
- 検証・承認境界: 合成testと実APIの候補提示確認、人間による正解確認、正式採用を区別する。今回の少量API検証の対象と費用記録はrepo外Task Context/Git外Evidenceへ保持する。通常UIのlive有効化、正式採用、DB移行、出品をこの決定から推定しない。
- rollback: 隔離V2の選択を停止し、追加module・接続・tests・文書を通常revertできる。V1と既存データ、過去Decision/Evidenceを維持する。

## DEC-0121 — SG BrandのNo Brand表記差をstrict検証で扱う

- 日付: 2026-10-05
- authority / 背景: Ownerは傘以外の4商品のCategory案を確認し、SG Brand・属性確認を含む開発続行を指示した。許可済みの隔離API確認で、SG Brand応答の表示名`No brand`と元名`NoBrand`が従来の空白付き完全一致検証で区分不一致となることを観測した。
- 決定: strict parserは両name欄のtrim / casefold後の`no brand`と`nobrand`だけを同じNo Brand区分と認識する。原文nameとAPIの実IDを保持し、ID 0からの区分推定、名前欠落の補完、部分一致、商品Brand不明からのNo Brand自動確定をしない。片方が実Brand名・未対応表記なら従来どおり拒否する。
- 保護: 既存ID / name / pagination / complete取得 / session / shop / Category binding、商品単位の明示確認、current再validation、SG Safety / Battery / SLS停止を維持する。PHの通常permissive parserは変更しない。通常DB・起動先・credential・SG INACTIVE / listing_ready=false / 正式出口閉鎖・MY / TH未着手を維持する。
- 境界: API取得成功はBrand人間確認や一連実商品受入の代替にしない。元Candidate・全SGショップの既存出品資料との結合がない実商品資料はGate ELIGIBLEへ昇格させない。今回の隔離確認と結果はTask Context / Git外Evidenceへ保持する。
- rollback: parser・関連tests・説明を通常revertできる。実運用データと過去Evidenceは変更・削除しない。

## DEC-0122 — 隔離Brand取得の追加承認枠をCategoryと累積ページ上限へ結合する

- 日付: 2026-10-05
- authority: Ownerはイヤホン・美容液・カメラ用マウントの3カテゴリーについて、各最大50ページ、合計最大150回のSG Brand読み取り、追加OpenAIなし・自動retryなしを明示許可した。DHCは既存SLS発送不可、傘はCategory未確認として今回の取得対象から除外する。具体的なASIN / Category / 取得結果はTask Context / Git外Evidenceへ保持する。
- 決定: `SGLiveValidationScope`へ明示Brandページ上限と最大3Categoryのallowlistを追加する。既定10ページ、明示設定の最大50ページとし、10を超える設定はCategory allowlistを必須にする。同じscope内の対象Category別requestを送信前に累積予約し、失敗や同じCategoryの再取得でも予約を返却しない。API default transport・shop・隔離DB・Category bindingとcomplete取得後のtransactional replaceを維持する。
- 置換範囲: DEC-0104の10ページ初期内部上限は通常 / offline・既定liveに維持する。Ownerが具体的な追加読み取り枠を承認した隔離検証でだけ、当該枠の値へ拡張できる。コード設定だけでOwner承認や全件取得を証明しない。実行先は新規Git外保存先を用い、request ledgerを保持し、既存実行を再初期化しない。
- 停止・保護: 対象外Category、上限、不完全取得、API / 契約失敗はcurrent Brand不存在・No Brand確定・準備完了へ変換しない。PH通常挙動、SG Safety / Battery / SLS、通常DB・起動先・credential、SG INACTIVE / listing_ready=false / 正式出口閉鎖、MY / TH未着手を維持する。商品単位のBrand確認、元Candidateと全ショップGate資料の必要条件を緩和しない。
- rollback: 追加scope設定の利用を停止し、コード・tests・説明を通常revertできる。通常DB・過去Evidence・旧予算ledgerを変更・削除しない。


## DEC-0123 — 画像AI対象選択の共通化と国別設定

- 日付: 2026-10-05
- authority: Ownerは画像対象をカテゴリーで絞るPH仕様を確認し、「基本処理を共通module、判断材料を国別設定」とする変更と、MY / THも同じ仕組みで動く設計準備を明示指示した。
- 決定: 画像AIの武器形状疑義検出transportは既存の共通再利用を維持し、Amazon / Keepa rootによる対象選択を共通moduleへ移す。対象rootは市場別JSONへ分離する。PH / SG / MY / THの初期設定はDEC-0053の4 root（おもちゃ、ホビー、スポーツ＆アウトドア、DIY・工具・ガーデン）とする。Shopee CategoryやAI予測Categoryをこの選択根拠へ読み替えない。
- 選択: root不明・不正は対象、その他の正常rootは対象外・未実行、既存BLOCKは除外優先とする。設定欠落・不正・未知市場は停止し、他市場へのfallbackをしない。選択だけでは実APIを呼ばず、対象外をNO_SIGNAL・安全保証にしない。
- 置換範囲: DEC-0117のSG隔離開発版で全SAFE / ELIGIBLE Keepa商品を対象とした部分を、SG国別設定による対象選択へ置換する。対象外では画像AIを準備条件に要求せず、商品説明・画像の人間確認、理由、既存Safety / Battery / SLS停止を維持する。rootを商品資料bindingへ含め、rootまたは市場設定が変われば古い人間確認を失効させる。
- MY / TH境界: 共通selectorと独立国別設定の初期準備だけを今回行う。市場のSafety・runtime・認証・出品機能の実装または有効化、規制適合性の受入を意味しない。国別情報は後続の具体的Evidenceにより更新する。
- 保護: PHの画像対象4 root・不明対象化・BLOCK優先・AIモデル・結果契約を維持する。既存PH評価・人間判断をSGへ流用しない。通常起動先・DB・credential、SG INACTIVE・listing_ready=false・正式出口閉鎖、実API承認境界を維持する。
- rollback: 共通selectorへの接続と国別設定を通常revertできる。実運用DBと過去Evidenceを変更・削除しない。


## DEC-0124 — 承認枠を保持する隔離SG実接続画面と準備確認

- 日付: 2026-10-05
- authority: OwnerはPH Betaとの差分説明を受け、残る接続・出力に必要な開発を指示した。local実装・合成testを進め、実APIの追加実行枠・通常環境反映・正式採用は既存の承認境界を維持する。
- 決定: SG開発版へ明示起動だけのread-only実接続modeを追加する。起動時に指定する承認済みrun設定へSG shop・最大3 ASIN・Brand対象Category・各上限・OpenAI上限0〜1 USDを結合する。設定ファイル・authorization_refはOwner承認そのものの証明ではなく、承認済み枠の搬送に限る。再生modeは既定のままとし、通常PH / SG画面を変更しない。
- 接続: 初期化・再描画では外部APIを呼ばず、明示操作だけで既存SG Bridgeから最新Access Tokenを取得してShopeeへ渡す。Mapperでrefreshせず、PHのtoken・環境変数へ書き戻さない。対象外shop / 商品 / Categoryは拒否する。live catalogは明示取得し、失敗時はBrand / 属性 / AI / 準備候補を閉じる。
- 上限: 同じ承認枠は一つの隔離runに結合する。request ledgerを送信前に永続化し、失敗・同Category再取得・再起動でも取得数・費用予約を返却・再初期化しない。同一runの同時起動をOS lockで拒否し、記録欠落・不正・grant変更は停止する。OpenAI枠0ではCategory AI / 画像APIを生成せず、画像対象商品の検査必要条件は維持する。
- 準備: current Category / Brand・SLS・商品資料・対象画像検査・人間確認を一つの準備確認処理へまとめ、商品ごとの不足手順を表示する。開発用CSV / TXTもこの処理を使う。属性取得状態は別に表示し、件数を入力完了と扱わない。
- 保護: 正式出力・SG ACTIVE・listing_ready=trueを今回開放しない。通常DB・起動先・credential・PH挙動・既存Safety / Battery / SLS停止を維持する。Keepa追加取得や過去PH評価・人間判断の流用をしない。MY / THの市場接続は後続工程とする。
- rollback: 隔離実接続modeの利用を停止し、追加runtime・画面接続・testsを通常revertできる。既存DB・過去Evidence・消費記録を変更・削除しない。

## DEC-0125 — 全商品の説明・画像の人間確認を削除し画像用途を武器疑義へ限定する

- 日付: 2026-10-06
- authority: Ownerは追加されたASINと説明・画像の内容一致を人間が確認する必要性を問い、「必要のない機能なら削除」「画像は武器の確認以外では現状必要ありません」と明示した。
- 決定: 全商品へ説明・画像の人間確認、両方の確認チェック、商品確認理由を要求する追加機能と準備候補の必須条件を削除する。画像は武器・武器形状の疑義検出と、その疑義に対する人間判断に限定する。
- PH整合: 国別root設定による対象外は画像未実行のまま通し、対象の検査がCOMPLETED / NO_SIGNALなら追加の人間確認を要求しない。疑義あり・判断不能は停止し、武器画像の人間判断だけを記録する。未取得画像を疑義なしへ変換しない。
- 維持: ASIN・元Candidateとsidecarの自動照合、SG Guardrail / Shared Battery、Category / Brandの確認、SLS、認証失敗の停止を維持する。対象外は画像資料の有無で停止せず、root不明は従来どおり武器画像検査の対象とする。通常PH・DB・credential・SG operation INACTIVE・正式出口閉鎖を維持し、追加実APIは行わない。
- 置換範囲: DEC-0117 / DEC-0123 / DEC-0124と市場展開仕様に含まれた全商品の説明・画像の人間確認、およびNO_SIGNAL後も人間確認を求める条件だけを置換する。過去の実行記録・消費枠を変更・リセットせず、削除された確認をOwner確認済みとして記録しない。
- rollback: 今回の武器限定処理と画面・tests・文書の変更を通常revertできる。過去Evidenceと通常環境を変更しない。

## DEC-0126 — SGベータ入口と手動出品準備出力の採用候補を実装する

- 日付: 2026-10-06
- authority: Ownerは開発版の残り検証の報告を受け、「SGのベータ版としての完成」を依頼し、MY / TH Guardrailに必要な情報の準備状況を質問した。
- 決定: SGベータ用の入口と、現行のCategory / Brand / SLS / 説明Safety / 武器画像条件を再検証したPH形式の手動出品準備CSV / TXTを実装する。対象商品だけの準備出力にlisting_ready=TRUEとSG_BETA_MANUAL_PREPARATIONを付ける。自動出品・Seller Centerの属性入力完了・全面的な安全保証を意味しない。SG Category確認だけのobjectは従来どおりlisting_ready=false。
- 採用境界: 既存canonical StateでSG ACTIVE / ALLOWED、PH / SG保護capability ACCEPTED、blocking open itemなしの場合だけ入口と出力を利用できる。出力生成前後にも現在Stateを再確認する。local実装や合成testでStateを変更しない。正式採用は現在対象のtechnical gates・Owner最終承認、実環境反映は対象と復旧手順の確認後に行う。
- 再利用: 既存の別SG DB・Bridge token取得・grant・永続ledgerを再利用する。1枠最大3商品・OpenAI最大1米ドルを維持し、使い切った枠をリセットしない。新しい実API実行・通常PH DB移行・デスクトップ起動先変更・credential変更・自動出品は今回実行しない。
- MY / TH: 情報の所在と不足をread-onlyで監査する。既存SLS・Community NG・販売規制ガイド・武器画像初期設定は土台として保持するが、国別辞書・評価処理・資料現行性は未完成。市場runtimeや新しい禁止規則を先行実装しない。
- 置換範囲: DEC-0116 / DEC-0117 / DEC-0124の正式出力未実装を、別入口の採用候補として実装済みにする。正式採用前の実出口閉鎖、SG INACTIVE、PH operation、既存Safety停止、過去Evidenceを維持する。
- rollback: SGベータ入口の利用を止め、今回の追加入口・出力部品・tests・docsを通常revertできる。通常PH環境や過去の消費記録を復旧対象へ含めない。
