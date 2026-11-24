'use strict';

const assert = require('node:assert/strict');
const {readQuickGameScrimmage,selectMatchup} = require('../../tools/web-audit-matchup.cjs');

function checkScrimmage(){
  const offset = 0x10000;
  const memory = new DataView(new ArrayBuffer(offset + 0xE61000));
  const word = (va, value) => memory.setUint32(offset + va, value, true);
  const seconds = (va, value) => memory.setFloat32(offset + va, value, true);
  global.window = {auditMemory: memory};
  try{
    word(0xE602C4, 1);
    word(0xE6028C, 0xE60300);
    word(0xE602EC, 0xE60400);
    word(0xE60404, 1);
    seconds(0xE602B0, 300);
    seconds(0xE60310, 296.5);
    assert.equal(readQuickGameScrimmage(offset), false, 'reject kickoff and its return');
    word(0xE602B4, 4);
    seconds(0xE60310, 300);
    assert.equal(readQuickGameScrimmage(offset), false, 'reject a full quarter clock');
    seconds(0xE60310, 296.5);
    const sample = readQuickGameScrimmage(offset);
    assert.ok(Number.isFinite(sample.at));
    assert.deepEqual(sample, {at:sample.at, period:1, down:1, seconds:296.5});
    word(0xE6028C, 0xFFFFFFFF);
    assert.equal(readQuickGameScrimmage(offset), false, 'reject an invalid clock pointer');
  }finally{delete global.window;}
}

async function run(){
  const clubs = [
    {slot: 1, code: '25', category: 0},
    {slot: 2, code: '10', category: 0},
    {slot: 3, code: '10', category: 4},
  ];
  const index = {home: 1, away: 2};
  const sides = ['away', 'neutral', 'home'];
  let position = 2;
  let dropDirection = true;
  const read = async () => ({home: clubs[index.home], away: clubs[index.away]});
  const press = async button => {
    if(button === 'left' || button === 'right'){
      if(dropDirection){dropDirection = false;return;}
      position = Math.max(0, Math.min(2, position + (button === 'left' ? -1 : 1)));
    }else if(position !== 1){
      const side = sides[position];
      index[side] = (index[side] + (button === 'rt' ? 1 : 2)) % clubs.length;
    }
  };
  const wait = async () => {};
  assert.deepEqual(await selectMatchup({home:'25', away:'10'}, read, press, wait),
    {home: clubs[0], away: clubs[1]});
  assert.deepEqual(await selectMatchup({}, read, assert.fail, wait), await read());
  await assert.rejects(selectMatchup({home:'99'}, read, press, wait), /Could not reach/);
  await assert.rejects(selectMatchup({home:10}, read, press, wait), /two-digit/);
  index.home = 0;
  await assert.rejects(selectMatchup({home:'10'}, read, async () => {}, wait), /No team change/);
  let triggers = 0;
  const retry = await selectMatchup({home:'10'}, read, async button => {
    if(button === 'rt' && ++triggers === 4) index.home = 1;
  }, wait);
  assert.equal(retry.home.code, '10');
  assert.equal(triggers, 4);
  index.home = 0;
  await assert.rejects(selectMatchup({home:'10'}, read, async button => {
    if(button === 'rt') index.away = 0;
  }, wait), /Controller changed the away team/);

  const centerOnly = {centerController:true};
  index.away = 1;
  const readController = async () => ({...await read(), controllerSide:sides[position]});
  position = 2;
  dropDirection = true;
  let moves = 0;
  const centered = await selectMatchup(centerOnly, readController, async button => {
    assert.equal(button, 'left');
    moves++;
    await press(button);
  }, wait);
  assert.equal(centered.controllerSide, 'neutral');
  assert.equal(moves, 2, 'retry an ignored centering input');
  assert.deepEqual(await selectMatchup(centerOnly, readController, assert.fail, wait), centered);
  position = 0;
  await assert.rejects(selectMatchup(centerOnly, readController, async button => {
    assert.equal(button, 'right');
  }, wait), /Controller did not reach neutral/);
  assert.deepEqual(await selectMatchup(centerOnly, readController, async button => {
    assert.equal(button, 'right');
    await press(button);
  }, wait), centered);
  assert.deepEqual(await selectMatchup({home:'25', away:'10', ...centerOnly}, readController, press, wait),
    centered, 'confirm both clubs and a neutral controller');
}

checkScrimmage();
run().then(() => console.log('PASS retail matchup selection and first-quarter scrimmage detection'));
