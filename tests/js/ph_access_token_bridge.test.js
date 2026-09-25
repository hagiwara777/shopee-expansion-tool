const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const code = fs.readFileSync(path.join(__dirname, '../../integrations/google_apps_script/ph_access_token_bridge/Code.gs'), 'utf8');
const SYNTHETIC_VALUE = 'synthetic_test_value';

function setup(sourceRows, options = {}) {
  const sourceReads = [];
  const logs = [];
  const bridgeRows = [
    ['marketplace', 'shop_id', 'access_token'],
    ['PH', '456', 'old_synthetic_value'],
  ];
  const bridge = sheet(bridgeRows, [], options);
  const source = sheet(sourceRows, sourceReads);
  const context = {
    Logger: {log: value => logs.push(value)},
    console: {log: value => logs.push(value), error: value => logs.push(value)},
    LockService: {getScriptLock: () => ({waitLock: () => {}, releaseLock: () => {}})},
    SpreadsheetApp: {

      openById: id => {
        if (id === 'bridge-id') return {getSheetByName: name => name === 'Bridge' ? bridge : null};
        if (options.sourceError) throw new Error(`private ${SYNTHETIC_VALUE}`);
        return {getSheetByName: name => name === '設定' ? source : null};
      },
      flush: () => {},
    },
    PropertiesService: {
      getScriptProperties: () => ({getProperty: key => key === 'BRIDGE_SPREADSHEET_ID' ? 'bridge-id' : 'source-id'}),
    },
  };
  vm.createContext(context);
  vm.runInContext(code, context);
  return {run: () => context.syncPhAccessToken(), sourceReads, bridgeRows, logs};
}

function sheet(rows, reads, options = {}) {
  return {
    getLastRow: () => rows.length,
    getRange(row, column, height = 1, width = 1) {
      reads.push({row, column, height, width});
      return {
        getValues: () => Array.from({length: height}, (_, i) =>
          Array.from({length: width}, (_, j) => rows[row - 1 + i]?.[column - 1 + j] ?? '')),
        getValue: () => rows[row - 1]?.[column - 1] ?? '',
        clearContent: () => {
          if (options.clearError) throw new Error(`private ${SYNTHETIC_VALUE}`);
          rows[row - 1][column - 1] = '';
        },
        setValues: values => {
          if (options.writeError) throw new Error(`private ${SYNTHETIC_VALUE}`);
          values[0].forEach((value, j) => { rows[row - 1][column - 1 + j] = value; });
        },
      };
    },
  };
}

function expectFailure(sourceRows, options = {}) {
  const fixture = setup(sourceRows, options);
  let failure;
  try { fixture.run(); } catch (error) { failure = error; }
  assert.ok(failure);
  assert.equal(failure.message, 'PH Access Token Bridge sync failed.');
  assert.equal(String(failure).includes(SYNTHETIC_VALUE), false);
  assert.deepEqual(fixture.logs, []);
  if (!options.clearError) assert.equal(fixture.bridgeRows[1][2], '');
  return fixture;
}

test('one PH row at an arbitrary source row syncs only three Bridge values', () => {
  const rows = Array.from({length: 10}, () => ['', 'SG', '123', 'do_not_read', 'other']);
  rows.push(['', 'PH', 456, 'do_not_read', SYNTHETIC_VALUE]);
  const fixture = setup(rows);
  fixture.run();
  assert.deepEqual(fixture.bridgeRows[1], ['PH', '456', SYNTHETIC_VALUE]);
  assert.deepEqual(fixture.logs, []);
  assert.deepEqual(fixture.sourceReads.map(({column, width}) => [column, width]),
    [[2, 1], [3, 1], [5, 1]]);
});

test('missing or duplicate PH clears the old Bridge token', () => {
  expectFailure([['', 'SG', 123, 'do_not_read', SYNTHETIC_VALUE]]);
  expectFailure([
    ['', 'PH', 456, 'do_not_read', SYNTHETIC_VALUE],
    ['', 'PH', 456, 'do_not_read', SYNTHETIC_VALUE],
  ]);
});

test('invalid shop ID or empty token clears the old Bridge token', () => {
  for (const shop of [0, -1, 1.5, 'abc', '000456', '']) {
    expectFailure([['', 'PH', shop, 'do_not_read', SYNTHETIC_VALUE]]);
  }
  expectFailure([['', 'PH', 456, 'do_not_read', '']]);
});

test('source failure and new-value write failure leave PH invalid', () => {
  expectFailure([], {sourceError: true});
  expectFailure([['', 'PH', 456, 'do_not_read', SYNTHETIC_VALUE]], {writeError: true});
});

test('Bridge invalidation failure stops before reading the source', () => {
  const fixture = expectFailure([['', 'PH', 456, 'do_not_read', SYNTHETIC_VALUE]],
    {clearError: true});
  assert.deepEqual(fixture.sourceReads, []);
});

test('five-minute trigger installer creates one and refuses duplicates', () => {
  const triggers = [];
  let minutes;
  const context = {
    ScriptApp: {
      getProjectTriggers: () => triggers,
      newTrigger: handler => ({
        timeBased: () => ({
          everyMinutes: value => ({create: () => { minutes = value; triggers.push({getHandlerFunction: () => handler}); }}),
        }),
      }),
    },
  };
  vm.createContext(context);
  vm.runInContext(code, context);
  context.installFiveMinuteTrigger();
  assert.equal(minutes, 5);
  assert.equal(triggers.length, 1);
  assert.throws(() => context.installFiveMinuteTrigger(), /sync failed/);
  assert.equal(triggers.length, 1);
});
