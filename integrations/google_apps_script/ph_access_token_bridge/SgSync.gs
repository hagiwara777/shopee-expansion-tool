/** Optional SG add-on in the existing project; activation requires owner approval.
 * Keep Code.gs and its PH trigger unchanged. SG uses a DIFFERENT Bridge file.
 */
function sgBridgeFailure_() {
  return new Error('SG Access Token Bridge sync failed.');
}

function sgPositiveShop_(value) {
  const shop = typeof value === 'number' && Number.isSafeInteger(value)
    ? String(value) : value;
  if (typeof shop !== 'string' || !/^[1-9][0-9]{0,19}$/.test(shop)) {
    throw sgBridgeFailure_();
  }
  return shop;
}

function sgClearTokens_(sheet, rows) {
  for (const row of rows) sheet.getRange(row, 3).clearContent();
  SpreadsheetApp.flush();
  for (const row of rows) {
    if (sheet.getRange(row, 3).getValue() !== '') throw sgBridgeFailure_();
  }
}

function syncSgAccessToken() {
  // Same project lock as PH: no overlapping PH/SG runs in this project.
  const lock = LockService.getScriptLock();
  try { lock.waitLock(30000); } catch (_) { throw sgBridgeFailure_(); }
  let sheet;
  let sgRows = [];
  let mayClear = false;
  try {
    const properties = PropertiesService.getScriptProperties();
    const sourceId = properties.getProperty('SOURCE_SPREADSHEET_ID');
    const phId = properties.getProperty('BRIDGE_SPREADSHEET_ID');
    const sgId = properties.getProperty('SG_BRIDGE_SPREADSHEET_ID');
    // Reject PH/source targets BEFORE any write or source cell read.
    if ([sourceId, phId, sgId].some(id => typeof id !== 'string' || !id.trim())
        || sgId.trim() === phId.trim() || sgId.trim() === sourceId.trim()) {
      throw sgBridgeFailure_();
    }
    sheet = SpreadsheetApp.openById(sgId.trim()).getSheetByName('Bridge');
    if (!sheet || sheet.getLastRow() < 2) throw sgBridgeFailure_();
    const rows = sheet.getRange(1, 1, sheet.getLastRow(), 3).getValues();
    if (['marketplace', 'shop_id', 'access_token'].some((h, i) => rows[0][i] !== h)) {
      throw sgBridgeFailure_();
    }
    sgRows = rows.slice(1).flatMap((row, i) => row[0] === 'SG' ? [i + 2] : []);
    // A PH row means this is not the dedicated SG target; never touch it.
    if (rows.slice(1).some(row => row[0] !== 'SG') || sgRows.length === 0) {
      throw sgBridgeFailure_();
    }
    mayClear = true;
    sgClearTokens_(sheet, sgRows);
    if (sgRows.length !== 1) throw sgBridgeFailure_();
    const expectedShop = sgPositiveShop_(properties.getProperty('SG_EXPECTED_SHOP_ID'));
    if (sgPositiveShop_(rows[sgRows[0] - 1][1]) !== expectedShop) throw sgBridgeFailure_();
    const source = SpreadsheetApp.openById(sourceId.trim()).getSheetByName('設定');
    if (!source || source.getLastRow() < 1) throw sgBridgeFailure_();
    const count = source.getLastRow();
    // Refresh Token (D), Partner Key, and order data are not read.
    const markets = source.getRange(1, 2, count, 1).getValues();
    const matches = markets.flatMap((row, i) => row[0] === 'SG' ? [i] : []);
    if (matches.length !== 1) throw sgBridgeFailure_();
    const sourceRow = matches[0] + 1;
    const shop = sgPositiveShop_(source.getRange(sourceRow, 3).getValue());
    const token = source.getRange(sourceRow, 5).getValue();
    if (shop !== expectedShop || typeof token !== 'string' || !token || /\s/.test(token)
        || [...token].some(ch => ch.charCodeAt(0) < 32)) throw sgBridgeFailure_();
    // Preserve market and shop; write ONLY this SG target's token cell.
    sheet.getRange(sgRows[0], 3).setValues([[token]]);
    SpreadsheetApp.flush();
    const result = sheet.getRange(sgRows[0], 1, 1, 3).getValues()[0];
    if (result[0] !== 'SG' || String(result[1]) !== shop || result[2] !== token) {
      throw sgBridgeFailure_();
    }
  } catch (_) {
    if (mayClear && sheet && sgRows.length) {
      try { sgClearTokens_(sheet, sgRows); } catch (_) { /* See write-outage limit. */ }
    }
    throw sgBridgeFailure_();
  } finally { lock.releaseLock(); }
}

function installSgFiveMinuteTrigger() {
  const lock = LockService.getScriptLock();
  try { lock.waitLock(30000); } catch (_) { throw sgBridgeFailure_(); }
  try {
    const handler = 'syncSgAccessToken';
    if (ScriptApp.getProjectTriggers().some(t => t.getHandlerFunction() === handler)) {
      throw sgBridgeFailure_();
    }
    ScriptApp.newTrigger(handler).timeBased().everyMinutes(5).create();
  } catch (_) {
    throw sgBridgeFailure_();
  } finally { lock.releaseLock(); }
}
