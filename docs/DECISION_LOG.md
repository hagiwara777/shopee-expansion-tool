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
