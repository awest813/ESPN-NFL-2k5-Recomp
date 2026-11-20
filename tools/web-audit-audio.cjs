'use strict';

// Serialized by Playwright and executed on the page, alongside log draining.
// Snapshot mode shares the same clock sampling without draining pending rows or
// acknowledging underruns. Periodic mode samples clocks only on a new failure.
function drainAuditRows(snapshotOnly=false) {
  const module=window.nfl2k5Module,s=module?.nfl2k5Audio,ctx=module?.nfl2k5AudioContext;
  // Counters belong to one output stream. A replacement may already report
  // a smaller/equal nonzero count; it must not inherit the previous baseline.
  const previous=window.auditAudioStream===s && window.auditAudioContext===ctx
    ? window.auditAudioUnderruns||0 : 0;
  const changed=s && s.underruns>previous;
  let sample;
  if(snapshotOnly || changed) {
    // Bracket currentTime: it is a block-stepped render position, not a wall
    // clock. The SDK pthread QPC domain is timeOrigin + performance.now().
    const readBeginMs=performance.now(),time=ctx?.currentTime;
    const readEndMs=performance.now();
    let outputTimestamp=null;
    try {
      const value=ctx?.getOutputTimestamp?.();
      if(value && Number.isFinite(value.contextTime) && Number.isFinite(value.performanceTime))
        outputTimestamp={contextTime:value.contextTime,performanceTime:value.performanceTime};
    }catch{} // Missing/failing diagnostics must not hide a real underrun.
    sample={at:readEndMs,clock:{originMs:performance.timeOrigin??null,readBeginMs,readEndMs,outputTimestamp},
      context:ctx?{state:ctx.state,rate:ctx.sampleRate,time,baseLatency:ctx.baseLatency,outputLatency:ctx.outputLatency}:null,
      output:s?{state:s.state,played:s.played,rendered:s.rendered,underruns:s.underruns,underrunFrames:s.underrunFrames,
        maxUnderrunFrames:s.maxUnderrunFrames,queued:s.queued,firstUnderrunTime:s.firstUnderrunTime,
        lastUnderrunTime:s.lastUnderrunTime,lastUnderrunQueued:s.lastUnderrunQueued,lastUnderrunRequired:s.lastUnderrunRequired,
        peak:s.peak,frequency:s.frequency}:null};
  }
  if(snapshotOnly)return sample;
  const rows=window.auditPending?.splice(0)||[];
  if(changed) {
    rows.push({at:sample.at,kind:'audio-underrun',line:'[AUDIO-UNDERRUN] '+JSON.stringify({
      blocks:s.underruns,missingFrames:s.underrunFrames,maxGapFrames:s.maxUnderrunFrames,
      contextTime:sample.context?.time,clock:sample.clock,
      firstGapTime:s.firstUnderrunTime,lastGapTime:s.lastUnderrunTime,
      available:s.lastUnderrunQueued,required:s.lastUnderrunRequired,queued:s.queued,
    })});
  }
  window.auditAudioStream=s;window.auditAudioContext=ctx;
  window.auditAudioUnderruns=s?.underruns||0;
  return rows;
}

module.exports={drainAuditRows};
