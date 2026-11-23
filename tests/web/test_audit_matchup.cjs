'use strict';

const assert = require('node:assert/strict');
const {selectMatchup} = require('../../tools/web-audit-matchup.cjs');

async function run(){
  const clubs = [
    {slot: 1, code: '25', category: 0},
    {slot: 2, code: '10', category: 0},
    {slot: 3, code: '10', category: 4},
  ];
  const index = {home: 1, away: 2};
  let assigned = 'home';
  const read = async () => ({home: clubs[index.home], away: clubs[index.away]});
  const press = async button => {
    if(button === 'left') assigned = 'away';
    else if(button === 'right') assigned = 'home';
    else index[assigned] = (index[assigned] + (button === 'rt' ? 1 : 2)) % clubs.length;
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
    if(button === 'rt' && ++triggers === 2) index.home = 1;
  }, wait);
  assert.equal(retry.home.code, '10');
  index.home = 0;
  await assert.rejects(selectMatchup({home:'10'}, read, async button => {
    if(button === 'rt') index.away = 0;
  }, wait), /Controller changed the away team/);
}

run().then(() => console.log('PASS retail matchup navigation and failure detection'));
