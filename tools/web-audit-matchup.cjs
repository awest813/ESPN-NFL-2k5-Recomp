'use strict';

// Serialized by Playwright. Guest addresses and offsets match src/nfl2k5_teams.c.
function readQuickGameTeams(offset){
  const view=new DataView(window.auditMemory.buffer);
  const word=va=>view.getUint32(offset+va,true);
  if(word(0xACF614)!==1)throw Error('Expected Quick Game Team Select');
  function team(side){
    const ptr=word(0xACF63C+4*side);
    const code=ptr && word(ptr+0x10C);
    if(!code)throw Error('Missing Team Select record');
    let text='';
    for(let i=0;i<8;i++){
      const c=view.getUint16(offset+code+2*i,true);
      if(!c)return {code:text,category:word(ptr+0x128),slot:ptr};
      text+=String.fromCharCode(c);
    }
    throw Error('Invalid team asset code');
  }
  // The title stores the assignment for the first controller at E5FE88.
  const controllerSide=['neutral','home','away'][word(0xE5FE88)];
  return {home:team(0),away:team(1),controllerSide};
}

// Serialized by Playwright. Uses the match state fields from
// src/nfl2k5_presentation.cpp and the browser clock used for frame reports.
function readQuickGameScrimmage(offset){
  const memory=new DataView(window.auditMemory.buffer);
  const word=va=>memory.getUint32(offset+va,true);
  const phase=word(0xE602B4),period=word(0xE602C4);
  if(phase!==4 || period!==1)return false;
  const clock=word(0xE6028C),downs=word(0xE602EC);
  if(!clock || !downs || offset+clock+0x14>memory.byteLength ||
    offset+downs+8>memory.byteLength)return false;
  const down=word(downs+4);
  const seconds=memory.getFloat32(offset+clock+0x10,true);
  const quarter=memory.getFloat32(offset+0xE602B0,true);
  if(down<1 || down>4 || !(seconds>0 && seconds<quarter && quarter<4000))return false;
  return {at:performance.now(),period,down,seconds};
}

async function selectMatchup(requested,readTeams,press,wait){
  let result=await readTeams();
  for(const [side,other,direction] of [['away','home','left'],['home','away','right']]){
    if(requested[side]===undefined)continue;
    if(typeof requested[side]!=='string'||!/^\d{2}$/.test(requested[side]))throw Error('Expected a two-digit team code');
    // Crossing from the opposite side takes two presses. Allow one missed
    // input during a guest stall. Pressing again at the edge stays there.
    for(let i=0;i<3;i++){await press(direction);await wait(700);}
    result=await readTeams();
    const seen=new Set();
    let trigger='rt';
    while(result[side].code!==requested[side]||result[side].category!==0){
      if(result[side].category!==0)trigger='lt';
      const key=trigger+':'+result[side].slot;
      if(seen.has(key)||seen.size>=100)throw Error('Could not reach '+side+' club '+requested[side]);
      seen.add(key);
      const before=result;
      // The roster changes before Team Select finishes animating. On a slow
      // frame the next trigger can arrive while the menu still ignores input.
      for(let attempt=0;attempt<4;attempt++){
        if(attempt===1){await press(direction);await wait(700);}
        await press(trigger);
        for(let i=0;i<12;i++){
          result=await readTeams();
          if(result[other].slot!==before[other].slot)throw Error('Controller changed the '+other+' team');
          if(result[side].slot!==before[side].slot)break;
          await wait(150);
        }
        if(result[side].slot!==before[side].slot)break;
      }
      if(result[side].slot===before[side].slot)
        throw Error('No team change on '+side+' from '+before[side].code+' using '+trigger);
    }
  }
  if(requested.centerController){
    for(let attempt=0;attempt<6 && result.controllerSide!=='neutral';attempt++){
      const side=result.controllerSide;
      if(side!=='home' && side!=='away')throw Error('Unknown Team Select controller assignment');
      await press(side==='home'?'left':'right');
      for(let i=0;i<12;i++){
        result=await readTeams();
        if(result.controllerSide!==side)break;
        await wait(150);
      }
    }
    if(result.controllerSide!=='neutral')throw Error('Controller did not reach neutral on Team Select');
  }
  for(const side of ['home','away']){
    if(requested[side]!==undefined && (result[side].code!==requested[side]||result[side].category!==0))
      throw Error('Final '+side+' selection differs from requested club');
  }
  return result;
}

module.exports={readQuickGameTeams,readQuickGameScrimmage,selectMatchup};
