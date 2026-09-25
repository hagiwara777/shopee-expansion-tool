# PH Access Token Bridge sync (Minimum Beta)

This versioned Apps Script template runs as a dedicated Bridge sync project.
It does not change the existing inventory management Apps Script, the Mapper, or
the read-only GoogleSheetAccessTokenSource. No IDs or credentials belong in Git.

## Sheet contract

- Existing inventory spreadsheet: tab `設定`; B = marketplace, C = shop_id,
  D = Refresh Token, E = Access Token. The script reads **B, C, and E only**
  across all populated rows and requires exactly one `PH` row.
- Dedicated Bridge spreadsheet: tab `Bridge`; A1:C1 must be exactly
  `marketplace`, `shop_id`, `access_token`. Prepare one PH row with A = `PH`,
  B = the expected shop ID, and C empty. The script finds the PH row by A;
  it does not rely on a row number.
- The existing Service Account remains a **Viewer of the Bridge only**. Do not
  share the inventory spreadsheet with that account. The Apps Script runs
  under the owner-authorized Google identity that can read the inventory
  spreadsheet and edit the Bridge.

## Owner-controlled activation (not performed by this repository)

1. Confirm the source and Bridge permissions and the Bridge A:C contract.
2. Create a dedicated Apps Script project and copy
   `Code.gs` into it. In Script Properties, set `SOURCE_SPREADSHEET_ID` to the
   inventory spreadsheet ID. Set `BRIDGE_SPREADSHEET_ID` to the dedicated
   Bridge spreadsheet ID. Keep both IDs out of the code, repository, logs,
   and Evidence.
3. Authorize the script's spreadsheet access with the intended Google identity.
   Run `syncPhAccessToken` once, then verify that the Bridge has exactly one
   valid PH row and that the existing reader succeeds. Compare token values
   privately as match/mismatch only; never paste their contents into evidence.
4. Create one **time-driven trigger** for `syncPhAccessToken`, every 5 minutes.
   If the Apps Script UI cannot save the trigger, run `installFiveMinuteTrigger`
   once after approving its additional Google permission. It refuses to create
   a duplicate. Monitor failed executions. A failed run must be investigated before treating
   the Bridge value as current. Do not create additional overlapping triggers.

The function clears and confirms the Bridge PH token **before** reading the
source, then writes and reads back A:C. Source or validation failures leave C
empty, which makes the existing GoogleSheetAccessTokenSource stop. If the new
write or read-back fails, the function attempts to clear C again. It throws
only a generic error and never logs source cells or exceptions.

**Availability limit:** Google may reject the invalidation write or its
confirmation. Under that failure, a three-column Bridge and the unchanged
reader cannot prove that a previously valid token was removed. The script
stops before reading the source and reports failure, but the old Bridge value
may still be visible to the reader. Strict fail-closed behavior during a total
Bridge write outage requires a separate reader-side freshness contract and
separate approval. Do not claim this Minimum Beta meets that stronger case.

The source tab may contain other markets, but this script writes PH only. It
never calls the Shopee API, handles Refresh Token or Partner Key, or enables
SG/MY/TH runtime. Rollback is to disable the trigger and clear the Bridge PH
token under owner control; leaving an old value in C is not a safe rollback.

Offline check: `node --test tests/js/ph_access_token_bridge.test.js`.
