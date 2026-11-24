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
  return {home:team(0),away:team(1)};
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
  for(const side of ['home','away']){
    if(requested[side]!==undefined && (result[side].code!==requested[side]||result[side].category!==0))
      throw Error('Final '+side+' selection differs from requested club');
  }
  return result;
}

module.exports={readQuickGameTeams,selectMatchup};
