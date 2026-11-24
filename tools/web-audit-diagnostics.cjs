'use strict';

// File-not-found probes, queue occupancy and known guest TODO sites are
// evidence rather than failures. Actual missing audio frames are failures.
function isGameStop(row) {
  return row.kind === 'error' && String(row.line || '').startsWith('The game stopped:');
}

function isAuditFailure(row) {
  const line = String(row.line || '');
  return isGameStop(row) || row.kind === 'browser-error' || row.kind === 'pageerror' || row.kind === 'audit-error'
    || row.kind === 'audio-underrun' || /\[AUDIO-UNDERRUN\]/.test(line)
    || (!row.kind && /^\s*(?:PAGEERROR|BROWSER ERROR)\b/i.test(line))
    || /\[WebGPU\]\s+(?:device (?:error|lost)|no (?:device|adapter)|not available|cannot start|download\b|fence\b)/i.test(line)
    || /\[SDLGPU\].*queued draws dropped/i.test(line)
    || /\[AUDIO\].*(?:could not start|processor failed|SDL_(?:InitSubSystem|OpenAudioDeviceStream).*failed)/i.test(line)
    || /\[APU-DSP\].*(?:did not idle|unsupported|invalid)/i.test(line)
    || /\[CRASH\]|\bRuntimeError\b|\bCompileError\b|\babort(?:ed)?\s*\(|unresolved guest (?:call|function|address)/i.test(line)
    || /GPUValidationError|Error while (?:parsing WGSL|validating)/i.test(line);
}

// Keep each reporting window intact. A mode change can happen partway
// through a window, and a five-second mean can hide a single long flip.
function frameWindows(rows) {
  const windows = [];
  const header = /\[SDLGPU\] 5s: frames (\d+) ([\d.]+) fps/;
  const intervals = /\| flip intervals (\d+) over-budget (\d+) over-50ms (\d+) over-100ms (\d+) worst ([\d.]+) ms/;
  let transitions = [];
  for (const {at, line} of rows) {
    if (!line) continue;
    if (line.includes('[MODE-FSM]')) transitions.push({at, line});
    if (!line.includes('flip intervals')) continue;
    const counts = intervals.exec(line);
    const sample = header.exec(line);
    if (!counts || !sample) continue;
    const phases = /worst [\d.]+ ms \(texture ([\d.]+) vertex ([\d.]+) submit ([\d.]+)\)/.exec(line);
    const renderer = /\| ms\/frame texture ([\d.]+) vertex ([\d.]+) submit ([\d.]+)/.exec(line);
    const texture = /\| hash ([\d.]+) MiB\/frame verify ([\d.]+) decode .*?\| texture-ms\/frame verify ([\d.]+) decode ([\d.]+)/.exec(line);
    const reuse = /\| texture reuse MiB\/frame same-frame match ([\d.]+) changed ([\d.]+) \((\d+) changes\)/.exec(line);
    windows.push({
      at, frames: Number(sample[1]), fps: Number(sample[2]),
      intervals: Number(counts[1]), overBudget: Number(counts[2]),
      over50ms: Number(counts[3]), over100ms: Number(counts[4]),
      worstMs: Number(counts[5]), transitions,
      ...(phases && {worstFrameMs: {
        texture: Number(phases[1]), vertex: Number(phases[2]), submit: Number(phases[3]),
      }}),
      ...(renderer && {rendererMsPerFrame: {
        texture: Number(renderer[1]), vertex: Number(renderer[2]), submit: Number(renderer[3]),
      }}),
      ...(texture && {texturePerFrame: {
        hashMiB: Number(texture[1]), verifyMiB: Number(texture[2]),
        verifyMs: Number(texture[3]), decodeMs: Number(texture[4]),
      }}),
      ...(reuse && {sameFrameTextureReuse: {
        matchMiBPerFrame: Number(reuse[1]), changedMiBPerFrame: Number(reuse[2]),
        changes: Number(reuse[3]),
      }}),
    });
    transitions = [];
  }
  return windows;
}

function caseDiagnostics(result, rows) {
  const failures = rows.filter(isAuditFailure);
  const windows = frameWindows(rows);
  return {
    ...(windows.length ? {frameWindows: windows} : {}),
    result: failures.length && (result === 'pass' || result === 'partial') ? 'fail' : result,
    diagnostics: rows.filter(row => isAuditFailure(row)
      || /\[UNRESOLVED\]|\[FLAGS\]|\[TODO\]|unresolved guest/i.test(row.line || '')),
    failures,
  };
}

module.exports = {isAuditFailure, isGameStop, caseDiagnostics};
