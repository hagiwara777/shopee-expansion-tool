/** PH-only bridge sync. Run this as a dedicated Apps Script project. */
const SOURCE_SHEET_NAME = '設定';
const BRIDGE_SHEET_NAME = 'Bridge';
const SOURCE_SPREADSHEET_ID_PROPERTY = 'SOURCE_SPREADSHEET_ID';
const BRIDGE_SPREADSHEET_ID_PROPERTY = 'BRIDGE_SPREADSHEET_ID';
const BRIDGE_HEADERS = ['marketplace', 'shop_id', 'access_token'];

function bridgeFailure_() {
  // Never include a Sheets exception, cell value, or spreadsheet ID in the error.
  return new Error('PH Access Token Bridge sync failed.');
}

function phBridgeRows_(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 1) throw bridgeFailure_();
  const values = sheet.getRange(1, 1, lastRow, 3).getValues();
  if (BRIDGE_HEADERS.some((header, index) => values[0][index] !== header)) {
    throw bridgeFailure_();
  }
  const rows = [];
  for (let index = 1; index < values.length; index += 1) {
    if (values[index][0] === 'PH') rows.push(index + 1);
  }
  return rows;
}

function invalidatePh_(sheet, rows) {
  for (const row of rows) sheet.getRange(row, 3).clearContent();
  SpreadsheetApp.flush();
  for (const row of rows) {
    if (sheet.getRange(row, 3).getValue() !== '') throw bridgeFailure_();
  }
}

function sourcePh_(spreadsheetId) {
  const sheet = SpreadsheetApp.openById(spreadsheetId).getSheetByName(SOURCE_SHEET_NAME);
  if (!sheet) throw bridgeFailure_();
  const lastRow = sheet.getLastRow();
  if (lastRow < 1) throw bridgeFailure_();
  // Read only B, C, and E. Column D and all other source data stay untouched.
  const markets = sheet.getRange(1, 2, lastRow, 1).getValues();
  const shops = sheet.getRange(1, 3, lastRow, 1).getValues();
  const tokens = sheet.getRange(1, 5, lastRow, 1).getValues();
  const matches = [];
  for (let index = 0; index < lastRow; index += 1) {
    if (markets[index][0] === 'PH') matches.push(index);
  }
  if (matches.length !== 1) throw bridgeFailure_();
  const index = matches[0];
  const rawShop = shops[index][0];
  const shop = typeof rawShop === 'number' && Number.isSafeInteger(rawShop)
    ? String(rawShop) : rawShop;
  if (typeof shop !== 'string' || !/^[1-9][0-9]{0,19}$/.test(shop)) {
    throw bridgeFailure_();
  }
  const token = tokens[index][0];
  if (typeof token !== 'string' || !token || /\s/.test(token)
      || [...token].some(character => character.charCodeAt(0) < 32)) {
    throw bridgeFailure_();
  }
  return {shop, token};
}

function syncPhAccessToken() {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000);
  } catch (_) {
    throw bridgeFailure_();
  }
  let bridgeSheet;
  let phRows = [];
  try {
    const bridgeId = PropertiesService.getScriptProperties()
      .getProperty(BRIDGE_SPREADSHEET_ID_PROPERTY);
    if (typeof bridgeId !== 'string' || !bridgeId.trim()) throw bridgeFailure_();
    const bridge = SpreadsheetApp.openById(bridgeId.trim());
    bridgeSheet = bridge && bridge.getSheetByName(BRIDGE_SHEET_NAME);
    if (!bridgeSheet) throw bridgeFailure_();
    phRows = phBridgeRows_(bridgeSheet);
    // A missing PH row already makes the existing reader fail closed.
    if (phRows.length === 0) throw bridgeFailure_();
    // Remove the old token before any source read or new write can fail.
    invalidatePh_(bridgeSheet, phRows);
    if (phRows.length !== 1) throw bridgeFailure_();

    const sourceId = PropertiesService.getScriptProperties()
      .getProperty(SOURCE_SPREADSHEET_ID_PROPERTY);
    if (typeof sourceId !== 'string' || !sourceId.trim()) throw bridgeFailure_();
    const {shop, token} = sourcePh_(sourceId.trim());
    const row = phRows[0];
    bridgeSheet.getRange(row, 1, 1, 3).setValues([['PH', shop, token]]);
    SpreadsheetApp.flush();
    const written = bridgeSheet.getRange(row, 1, 1, 3).getValues()[0];
    if (written[0] !== 'PH' || String(written[1]) !== shop || written[2] !== token) {
      throw bridgeFailure_();
    }
  } catch (_) {
    if (bridgeSheet && phRows.length) {
      try {
        invalidatePh_(bridgeSheet, phRows);
      } catch (_) {
        // A Google write outage cannot be repaired inside this three-column contract.
      }
    }
    throw bridgeFailure_();
  } finally {
    lock.releaseLock();
  }
}

function installFiveMinuteTrigger() {
  const handler = 'syncPhAccessToken';
  const existing = ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === handler);
  if (existing.length > 0) throw bridgeFailure_();
  ScriptApp.newTrigger(handler).timeBased().everyMinutes(5).create();
}
