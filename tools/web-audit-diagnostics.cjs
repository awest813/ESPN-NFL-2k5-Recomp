'use strict';

// File-not-found probes, queue occupancy and known guest TODO sites are
// evidence rather than failures. Actual missing audio frames are failures.
function isAuditFailure(row) {
  const line = String(row.line || '');
  return row.kind === 'browser-error' || row.kind === 'pageerror' || row.kind === 'audit-error'
    || row.kind === 'audio-underrun' || /\[AUDIO-UNDERRUN\]/.test(line)
    || (!row.kind && /^\s*(?:PAGEERROR|BROWSER ERROR)\b/i.test(line))
    || /\[WebGPU\]\s+(?:device (?:error|lost)|no (?:device|adapter)|not available|cannot start|download\b|fence\b)/i.test(line)
    || /\[SDLGPU\].*queued draws dropped/i.test(line)
    || /\[AUDIO\].*(?:could not start|processor failed|SDL_(?:InitSubSystem|OpenAudioDeviceStream).*failed)/i.test(line)
    || /\[APU-DSP\].*(?:did not idle|unsupported|invalid)/i.test(line)
    || /\[CRASH\]|\bRuntimeError\b|\bCompileError\b|\babort(?:ed)?\s*\(|unresolved guest (?:call|function|address)/i.test(line)
    || /GPUValidationError|Error while (?:parsing WGSL|validating)/i.test(line);
}

function caseDiagnostics(result, rows) {
  const failures = rows.filter(isAuditFailure);
  return {
    result: failures.length && (result === 'pass' || result === 'partial') ? 'fail' : result,
    diagnostics: rows.filter(row => isAuditFailure(row)
      || /\[UNRESOLVED\]|\[FLAGS\]|\[TODO\]|unresolved guest/i.test(row.line || '')),
    failures,
  };
}

module.exports = {isAuditFailure, caseDiagnostics};
