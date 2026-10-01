# CURRENT WORK

本書はformal mainで成立する状態と次工程の再開案内。長寿命の承認済み状態は
`governance/state.json`、branch / HEAD / PR / checksはGit / GitHub、
タスク固有状態はrepo外Task Context、実行結果はGit外Evidenceを参照する。

## 現在の正式状態と次の独立工程

正本化連鎖防止ルールを採用済み（DEC-0114）。Git管理文書の現在状態をmerge後にも正しい形で
同一PRへ含め、post-merge確認成功後はTask ContextをCLOSEDにして終了する。
詳細手順はRUNBOOK「Post-Merge Stability」を適用する。

SG Minimum Beta完成判定（Roadmap Step 8）は正式採用済みでCLOSED。
半自動完成線はDEC-0111 / DEC-0112、Step 8終了はDEC-0113を参照する。
新規Beta MUST実装の残作業はない。

次の独立工程はRoadmap Step 9「SG実運用」。Step 9は未承認・未着手であり、
開始には新規の独立タスクとOwnerの別途明示承認が必要である。

## 成立済み成果と保護境界

- PHはACTIVE / ALLOWED、SGはINACTIVE / ALLOWED、MY / THはINACTIVE / NOT_STARTED。
  `ph.beta.operation`と`sg.safety.baseline`はACCEPTED。
- SG production Category source確認、catalog import offline成果、6実商品の人間Category確認・
  保存・再利用・current ID / path / leaf再validationは正式採用済み（DEC-0093 / DEC-0098 / DEC-0103）。
  6件は同一brandの異なる用途の保護ケース標本であり、広い商品群の精度保証ではない。
- SG Brand / No Brandのoffline最小実装は正式採用済み（DEC-0104 / DEC-0105）。
  商品単位No Brand保存、strict完全取得、current再validationを維持する。
  No Brand tableは隔離acceptance DBへの明示初期化だけで、production schemaへ適用していない。
- SG SLSのoffline最小runtimeは正式採用済み（DEC-0108 / DEC-0109）。
  SLS ALLOW候補はCategory条件の成立に限り、商品全体のSafety保証ではない。
- Owner Acceptance方式Bは正式採用済み（DEC-0106 / DEC-0107）。
  Ownerの技術値手動コピーは不要だが、現在対象への明示的最終承認とfresh Evidence・formal Verifyは必須。
  GitHubコメントは承認後のbinding搬送であり、人間のUI手入力を独立証明しない。

## 既知制約・停止条件

Step 8で採用した完成線は、少量商品ごとのSG Gate `ELIGIBLE`、
人間Category・Brand / No Brand確認、SLS `ALLOW`候補、Seller Center必須Attribute・
商品固有発送条件確認を経た手動出品である。未解決BLOCK / REVIEW / EXCLUDE / UNCHECKED /
UNAVAILABLE、Category / Brand未確認、Battery / 危険物 / 許認可等の未解決疑義があれば出品しない。
人間確認でSafety / Battery / SLS停止を解除しない。

SG operation INACTIVE、`listing_ready=false`、SG export / handoff CLOSEDを維持する。
Brand / No Brand・SLS live acceptanceとSeller Center E2Eは未実施。
production API / DB / schema、Bridge / credential変更、runtime切替、deploy、
SG ACTIVE化、listing_ready変更、出口開放、自動確定・出品は別scope・別途明示承認を要する。
MY / TH実装には着手しない。未実施事項だけを新しいBeta MUSTへ昇格しない。

共通Catalog / Access Token Sourceの既存責務は維持する。Mapper側refreshは行わず、
Source明示ON時のsilent fallbackを許さない。Bridge全面書込み障害時の旧token無効化は保証しない。
SG Brand responseにmarketplace / Category echoがないため、server内部の別Category誤応答の独立検出は保証しない。

## Required Decisions

- DEC-0114 — 正本化連鎖防止、同一PRのmerge後安定性、Decision必要条件と終了責務。
- DEC-0111 / DEC-0112 / DEC-0113 — Step 8完成線・正式採用・CLOSED、Step 9別承認境界。
- DEC-0072 / DEC-0073 / DEC-0087 / DEC-0088 — Governance・formal承認・必須手順配置・Decision読込。
- DEC-0091 / DEC-0092 / DEC-0106 / DEC-0107 — Owner Evidence、freshness、限定移行と方式B。
- DEC-0071 / DEC-0075 / DEC-0076 / DEC-0077 — SG Safety・Shared Battery・SLS資産とPH runtime保護。
- DEC-0079 / DEC-0080 / DEC-0081 — SG商品単位Category確認、current再validation、live OpenAI閉鎖。
- DEC-0082 / DEC-0084 / DEC-0085 / DEC-0086 / DEC-0089 / DEC-0090 — 共通認証・Catalog責務と既知制約。
- DEC-0093 / DEC-0096 / DEC-0098 / DEC-0099 / DEC-0100 / DEC-0101 / DEC-0102 / DEC-0103 —
  source・import・実商品Category受入と過去STOPの置換範囲。
- DEC-0104 / DEC-0105 / DEC-0108 / DEC-0109 — Brand・SLS offline成果とlive・production別承認境界。
