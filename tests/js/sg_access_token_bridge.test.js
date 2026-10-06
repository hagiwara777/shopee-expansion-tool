const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const directory = path.join(__dirname, '../../integrations/google_apps_script/ph_access_token_bridge');
const code = fs.readFileSync(path.join(directory, 'Code.gs'), 'utf8') + '\n' +
  fs.readFileSync(path.join(directory, 'SgSync.gs'), 'utf8');

function fixture(options = {}) {
  const ph = [['marketplace', 'shop_id', 'access_token'], ['PH', '456', 'ph-original']];
  const sg = options.bridge || [['marketplace', 'shop_id', 'access_token'], ['SG', '123', 'sg-old']];
  const source = options.source || [['', 'PH', 456, 'never-read-refresh', 'ph-new'],
    ['', 'SG', 123, 'never-read-refresh', 'sg-new']];
  const reads = [], writes = [], triggers = [{getHandlerFunction: () => 'syncPhAccessToken'}];
  const properties = {SOURCE_SPREADSHEET_ID:'source', BRIDGE_SPREADSHEET_ID:'ph',
    SG_BRIDGE_SPREADSHEET_ID:'sg', SG_EXPECTED_SHOP_ID:'123', ...options.properties};
  let clearAttempts = 0, released = 0;
  function sheet(rows, name) {
    return {getLastRow: () => rows.length, getRange(row, column, height = 1, width = 1) {
      reads.push({name, row, column, height, width});
      return {
        getValues: () => Array.from({length:height}, (_, i) =>
          Array.from({length:width}, (_, j) => rows[row-1+i]?.[column-1+j] ?? '')),
        getValue: () => rows[row-1]?.[column-1] ?? '',
        clearContent: () => {
          clearAttempts++;
          if (options.clearError) throw new Error('private-material');
          writes.push({name, row, column, operation:'clear'});
          rows[row-1][column-1] = '';
        },
        setValues: values => {
          if (options.writeError) throw new Error('private-material');
          writes.push({name, row, column, operation:'set'});
          values[0].forEach((value,j) => {rows[row-1][column-1+j] = value;});
          if (options.corruptWrite) rows[row-1][column-1] = 'corrupt';
        },
      };
    }};
  }
  const context = {
    PropertiesService:{getScriptProperties:()=>({getProperty:key=>properties[key]})},
    LockService:{getScriptLock:()=>({waitLock:()=>{if(options.lockError)throw Error('private-material');},
      releaseLock:()=>{released++;}})},
    SpreadsheetApp:{flush:()=>{},openById:id=>{
      if(id==='source' && options.sourceError)throw Error('private-material');
      return {getSheetByName:name=>name===(id==='source'?'設定':'Bridge')?
        sheet(id==='source'?source:id==='ph'?ph:sg,id):null};
    }},
    ScriptApp:{getProjectTriggers:()=>triggers,newTrigger:handler=>({timeBased:()=>({
      everyMinutes:minutes=>({create:()=>{
        if(options.triggerError)throw Error('private-material');
        triggers.push({minutes,getHandlerFunction:()=>handler});
      }}),
    })})},
  };
  vm.createContext(context); vm.runInContext(code, context);
  return {context,ph,sg,reads,writes,triggers,get released(){return released;},get clearAttempts(){return clearAttempts;}};
}

function failed(options, unchanged = false) {
  const f = fixture(options);
  assert.throws(()=>f.context.syncSgAccessToken(),error=>error.message==='SG Access Token Bridge sync failed.');
  assert.deepEqual(f.ph,[['marketplace','shop_id','access_token'],['PH','456','ph-original']]);
  if(unchanged) assert.equal(f.writes.length,0);
  else assert.equal(f.sg[1][2],'');
  return f;
}

test('SG source row and isolated Bridge update; only B/C/E reads and C writes',()=>{
  const f=fixture(); f.context.syncSgAccessToken();
  assert.deepEqual(f.sg[1],['SG','123','sg-new']);
  assert.equal(f.ph[1][2],'ph-original');
  assert.deepEqual(f.reads.filter(x=>x.name==='source').map(x=>[x.column,x.width]),[[2,1],[3,1],[5,1]]);
  assert.ok(f.writes.every(x=>x.name==='sg' && x.column===3));
  assert.equal(f.released,1);
});

test('PH code works unchanged when SG add-on is loaded',()=>{
  const f=fixture(); f.context.syncPhAccessToken();
  assert.deepEqual(f.ph[1],['PH','456','ph-new']);
  assert.equal(f.sg[1][2],'sg-old');
});

test('PH/source destination IDs rejected before reads or writes',()=>{
  for(const target of ['ph',' source ','']) {
    const f=failed({properties:{SG_BRIDGE_SPREADSHEET_ID:target}},true);
    assert.equal(f.reads.length,0);
  }
});

test('mixed-market or malformed target never modified',()=>{
  failed({bridge:[['marketplace','shop_id','access_token'],['PH','456','ph-original'],['SG','123','sg-old']]},true);
  failed({bridge:[['bad','shop_id','access_token'],['SG','123','sg-old']]},true);
});

test('missing/duplicate source and duplicate target clear SG without touching PH',()=>{
  failed({source:[['','PH',456,'never-read-refresh','ph-new']]});
  failed({source:[['','SG',123,'never-read-refresh','sg-new'],['','SG',123,'never-read-refresh','sg-new']]});
  const f=failed({bridge:[['marketplace','shop_id','access_token'],['SG','123','sg-old'],['SG','123','sg-old']]});
  assert.equal(f.sg[2][2],'');
});

test('shop mismatch and malformed token fail before new value publication',()=>{
  for(const shop of [999,0,1.5,'00123','']) failed({source:[['','SG',shop,'never-read-refresh','sg-new']]});
  for(const token of ['', 'bad token', 'bad\u0000token']) failed({source:[['','SG',123,'never-read-refresh',token]]});
  failed({properties:{SG_EXPECTED_SHOP_ID:'999'}});
});

test('source/write/readback failures leave only SG cleared',()=>{
  failed({sourceError:true}); failed({writeError:true}); failed({corruptWrite:true});
});

test('write outage cannot guarantee invalidation and prevents source reads',()=>{
  const f=failed({clearError:true},true);
  assert.equal(f.sg[1][2],'sg-old');
  assert.equal(f.reads.filter(x=>x.name==='source').length,0);
});

test('lock failure performs no reads/writes and does not unlock another run',()=>{
  const f=failed({lockError:true},true);
  assert.equal(f.reads.length,0); assert.equal(f.released,0);
});

test('separate five-minute SG trigger retains PH and rejects duplicates',()=>{
  const f=fixture(); f.context.installSgFiveMinuteTrigger();
  assert.equal(f.triggers.length,2);
  assert.equal(f.triggers[0].getHandlerFunction(),'syncPhAccessToken');
  assert.equal(f.triggers[1].getHandlerFunction(),'syncSgAccessToken');
  assert.equal(f.triggers[1].minutes,5);
  assert.throws(()=>f.context.installSgFiveMinuteTrigger(),/SG Access Token Bridge sync failed/);
  assert.equal(f.triggers.length,2);
});

test('trigger service failure hides provider details and preserves PH trigger',()=>{
  const f=fixture({triggerError:true});
  assert.throws(()=>f.context.installSgFiveMinuteTrigger(),error=>error.message==='SG Access Token Bridge sync failed.');
  assert.equal(f.triggers.length,1);
  assert.equal(f.triggers[0].getHandlerFunction(),'syncPhAccessToken');
  assert.equal(f.released,1);
});
