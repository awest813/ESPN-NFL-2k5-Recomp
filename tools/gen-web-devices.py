#!/usr/bin/env python3
"""Route the APU's registers to the emulated APU in a WebAssembly build.

Native builds make the APU register window (0xFE800000..0xFE87FFFF) fault
and replay each faulting instruction into the emulated APU (xboxrecomp
apu/apu_mmio_hook.c). WebAssembly cannot fault, so the web build rewrites the
guest's DirectSound code instead: every guest memory access in those
functions becomes a device accessor (src/platform/web/recomp_web_dev.h) that
sends APU-window addresses to the APU and everything else to memory, as the
fault handler would.

Which functions: every function that names an APU register address (as hex,
or as the negative decimal displacement the lifter writes for addresses
above 2 GB), plus every function between the first and last of the largest
cluster of them -- the statically linked DirectSound library, whose helpers
also receive register pointers (a loop storing through `MEM32(ebx)` with ebx
walking 0xFE820400..0xFE82043C, say). Any APU access this misses is reported
at run time (wasm_unrouted_check in xboxrecomp kernel/xbox_memory_layout.c).

    gen-web-devices.py <gen dir> <out dir>

Writes a rewritten copy of each generated file that contains a selected
function into <out dir> (rewritten only when its content changes) and lists
those file names in <out dir>/replaced.txt; the build compiles the copies in
place of the originals. Each rewrite is checked by undoing it and comparing
with the original function, so a parse it does not understand fails the
build instead of miscompiling.
"""
import os
import re
import sys

APU_LO, APU_HI = 0xFE800000, 0xFE880000
CLUSTER_GAP = 0x10000          # code bytes between functions of one library

FUNC_RE = re.compile(r'^void sub_([0-9A-F]{8})\(void\)$')
NUM_RE = re.compile(r'(?<![\w.])(-?(?:0x[0-9A-Fa-f]+|\d+))[uUlL]*\b')
MEM_RE = re.compile(r'\b(SMEM8|SMEM16|SMEM32|SMEM64|MEM8|MEM16|MEM32|MEM64|MEMF|MEMD)\(')
DEV_RE = re.compile(r'\bRECOMP_DEV_([RW])_(SMEM8|SMEM16|SMEM32|SMEM64|MEM8|MEM16|MEM32|MEM64|MEMF|MEMD)\(')
INCLUDE_ANCHOR = '#include "recomp_funcs.h"\n'


def names_apu(code):
    for m in NUM_RE.finditer(code):
        text = m.group(1)
        neg = text.startswith('-')
        body = text[1:] if neg else text
        value = int(body, 16) if body.lower().startswith('0x') else int(body)
        if neg:
            value = -value
        if APU_LO <= (value & 0xFFFFFFFF) < APU_HI:
            return True
    return False


def split_code_comments(line):
    """[(is_code, text)] -- comments and string literals are left alone."""
    parts, i, start, n = [], 0, 0, len(line)
    while i < n:
        if line.startswith('/*', i):
            j = line.find('*/', i + 2)
            j = n if j < 0 else j + 2
            parts.append((True, line[start:i]))
            parts.append((False, line[i:j]))
            i = start = j
        elif line.startswith('//', i):
            parts.append((True, line[start:i]))
            parts.append((False, line[i:]))
            i = start = n
        elif line[i] in '"\'':
            q, j = line[i], i + 1
            while j < n and line[j] != q:
                j += 2 if line[j] == '\\' else 1
            parts.append((True, line[start:i]))
            parts.append((False, line[i:j + 1]))
            i = start = j + 1
        else:
            i += 1
    parts.append((True, line[start:]))
    return [p for p in parts if p[1]]


def match_paren(text, open_idx):
    depth = 0
    for k in range(open_idx, len(text)):
        c = text[k]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
            if depth == 0:
                return k
    raise ValueError('unbalanced parentheses: ' + text)


def expr_end(text, start):
    """End of the expression starting at `start`: the first top-level ';' or
    ',' or the ')' that closes an enclosing group."""
    depth = 0
    for k in range(start, len(text)):
        c = text[k]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            if depth == 0:
                return k
            depth -= 1
        elif depth == 0 and c in ';,':
            return k
    return len(text)


def rewrite(code, stats):
    out, i = [], 0
    while True:
        m = MEM_RE.search(code, i)
        if not m:
            out.append(code[i:])
            return ''.join(out)
        out.append(code[i:m.start()])
        macro = m.group(1)
        close = match_paren(code, m.end() - 1)
        addr = rewrite(code[m.end():close], stats)
        after = close + 1
        eq = re.match(r'\s*=(?!=)', code[after:])
        if eq:
            rhs_start = after + eq.end()
            rhs_end = expr_end(code, rhs_start)
            rhs = rewrite(code[rhs_start:rhs_end], stats).strip()
            out.append('RECOMP_DEV_W_%s(%s, %s)' % (macro, addr, rhs))
            stats['writes'] += 1
            i = rhs_end
        else:
            out.append('RECOMP_DEV_R_%s(%s)' % (macro, addr))
            stats['reads'] += 1
            i = after


def unrewrite(code):
    out, i = [], 0
    while True:
        m = DEV_RE.search(code, i)
        if not m:
            out.append(code[i:])
            return ''.join(out)
        out.append(code[i:m.start()])
        kind, macro = m.group(1), m.group(2)
        close = match_paren(code, m.end() - 1)
        inner = code[m.end():close]
        if kind == 'R':
            out.append('%s(%s)' % (macro, unrewrite(inner)))
        else:
            comma = expr_end(inner, 0)
            out.append('%s(%s) = %s' % (macro, unrewrite(inner[:comma]),
                                        unrewrite(inner[comma + 1:])))
        i = close + 1


def rewrite_line(line, stats):
    if line.lstrip().startswith('#'):
        return line
    return ''.join(rewrite(t, stats) if is_code else t
                   for is_code, t in split_code_comments(line))


def squash(text):
    return re.sub(r'\s+', '', text)


def parse(path):
    """[(va or None, [lines])]: function bodies and the text between them."""
    blocks, cur, va = [], [], None
    with open(path, encoding='utf-8', errors='surrogateescape') as f:
        for line in f:
            m = FUNC_RE.match(line.rstrip('\n'))
            if m and va is None:
                if cur:
                    blocks.append((None, cur))
                cur, va = [line], int(m.group(1), 16)
                continue
            cur.append(line)
            if va is not None and line.startswith('}'):
                blocks.append((va, cur))
                cur, va = [], None
    if cur:
        blocks.append((va, cur))
    return blocks


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    gen_dir, out_dir = sys.argv[1], sys.argv[2]
    files = sorted(f for f in os.listdir(gen_dir)
                   if re.match(r'recomp_\d+\.c$', f))
    parsed = {f: parse(os.path.join(gen_dir, f)) for f in files}

    naming = sorted(va for f in files for va, lines in parsed[f]
                    if va is not None and names_apu(''.join(lines)))
    if not naming:
        sys.exit('gen-web-devices: no function names an APU register; '
                 'nothing to route (wrong generated code?)')
    groups, group = [], [naming[0]]
    for va in naming[1:]:
        if va - group[-1] > CLUSTER_GAP:
            groups.append(group)
            group = []
        group.append(va)
    groups.append(group)
    cluster = max(groups, key=len)
    lo, hi = cluster[0], cluster[-1]
    selected = set(naming)

    os.makedirs(out_dir, exist_ok=True)
    stats = {'reads': 0, 'writes': 0}
    replaced, nfuncs = [], 0
    for f in files:
        changed, blocks = False, []
        for va, lines in parsed[f]:
            if va is not None and (va in selected or lo <= va <= hi):
                new = [lines[0]] + [rewrite_line(l, stats) for l in lines[1:]]
                if squash(unrewrite(''.join(new))) != squash(''.join(lines)):
                    sys.exit('gen-web-devices: rewrite of sub_%08X in %s does '
                             'not round-trip; refusing to build it' % (va, f))
                nfuncs += 1
                changed = changed or new != lines
                lines = new
            blocks.append(''.join(lines))
        if not changed:
            continue
        text = ''.join(blocks)
        if INCLUDE_ANCHOR not in text:
            sys.exit('gen-web-devices: %s has no %r' % (f, INCLUDE_ANCHOR.strip()))
        text = text.replace(INCLUDE_ANCHOR, INCLUDE_ANCHOR +
                            '#include "recomp_web_dev.h"   /* tools/gen-web-devices.py */\n', 1)
        dest = os.path.join(out_dir, f)
        old = None
        if os.path.exists(dest):
            with open(dest, encoding='utf-8', errors='surrogateescape') as fh:
                old = fh.read()
        if old != text:
            with open(dest, 'w', encoding='utf-8', errors='surrogateescape') as fh:
                fh.write(text)
        replaced.append(f)

    with open(os.path.join(out_dir, 'replaced.txt'), 'w') as fh:
        fh.write(''.join(r + '\n' for r in replaced))
    print('gen-web-devices: %d functions (%d name APU registers; cluster '
          '0x%08X-0x%08X), %d reads and %d writes routed, files: %s'
          % (nfuncs, len(naming), lo, hi, stats['reads'], stats['writes'],
             ' '.join(replaced)))


if __name__ == '__main__':
    main()
