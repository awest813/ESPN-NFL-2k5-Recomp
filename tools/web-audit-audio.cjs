'use strict';

// Serialized by Playwright and executed on the page, alongside log draining.
// Report counter changes even when no explicit audio snapshot was requested.
function drainAuditRows() {
  const rows=window.auditPending?.splice(0)||[];
  const module=window.nfl2k5Module,s=module?.nfl2k5Audio;
  const previous=window.auditAudioUnderruns||0;
  if(s && s.underruns>previous) {
    rows.push({at:performance.now(),kind:'audio-underrun',line:'[AUDIO-UNDERRUN] '+JSON.stringify({
      blocks:s.underruns,missingFrames:s.underrunFrames,maxGapFrames:s.maxUnderrunFrames,
      contextTime:module.nfl2k5AudioContext?.currentTime,
      firstGapTime:s.firstUnderrunTime,lastGapTime:s.lastUnderrunTime,
      available:s.lastUnderrunQueued,required:s.lastUnderrunRequired,queued:s.queued,
    })});
  }
  window.auditAudioUnderruns=s?.underruns||0;
  return rows;
}

module.exports={drainAuditRows};
