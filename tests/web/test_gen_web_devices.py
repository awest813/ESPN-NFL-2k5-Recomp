#!/usr/bin/env python3
"""tools/gen-web-devices.py: what it selects and how it rewrites.

    python3 tests/web/test_gen_web_devices.py
"""
import importlib.util
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOL = os.path.join(ROOT, 'tools', 'gen-web-devices.py')
spec = importlib.util.spec_from_file_location('gwd', TOOL)
gwd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gwd)

failures = 0


def check(cond, what):
    global failures
    if not cond:
        failures += 1
        print('FAIL:', what)


def rw(line):
    stats = {'reads': 0, 'writes': 0}
    return gwd.rewrite_line(line, stats), stats


# Rewrites
out, st = rw('    MEM32(0xFE820010u) = eax; /* mov MEM32(x), eax */\n')
check(out == '    RECOMP_DEV_W_MEM32(0xFE820010u, eax); /* mov MEM32(x), eax */\n', out)
check(st == {'reads': 0, 'writes': 1}, st)
out, _ = rw('    MEM32(ebp + 8) = MEM32(ebp + 8) + 4;\n')
check(out == '    RECOMP_DEV_W_MEM32(ebp + 8, RECOMP_DEV_R_MEM32(ebp + 8) + 4);\n', out)
out, _ = rw('    eax = MEM32(MEM32(esi) * 4 + 0x468C78);\n')
check(out == '    eax = RECOMP_DEV_R_MEM32(RECOMP_DEV_R_MEM32(esi) * 4 + 0x468C78);\n', out)
out, _ = rw('    if (MEM8(eax) == 2) goto L; x = MEM16(a) != b;\n')
check('RECOMP_DEV_R_MEM8(eax) == 2' in out and 'RECOMP_DEV_R_MEM16(a) != b' in out, out)
out, _ = rw('    MEMF(esp + 4) = (float)fp_top(); fp_pop();\n')
check(out == '    RECOMP_DEV_W_MEMF(esp + 4, (float)fp_top()); fp_pop();\n', out)
out, _ = rw('    fp_push(MEMF(eax + 0x28)); SET_LO8(edx, MEM8(eax + -20971253));\n')
check('fp_push(RECOMP_DEV_R_MEMF(eax + 0x28))' in out and
      'SET_LO8(edx, RECOMP_DEV_R_MEM8(eax + -20971253))' in out, out)
out, _ = rw('    f((MEM32(a) = b), MEM32(c));\n')
check(out == '    f((RECOMP_DEV_W_MEM32(a, b)), RECOMP_DEV_R_MEM32(c));\n', out)
out, _ = rw('    #define fp_top() g_fp_stack[g_fp_top]\n')
check(out == '    #define fp_top() g_fp_stack[g_fp_top]\n', 'preprocessor line changed')
out, _ = rw('    s = "MEM32(x) = 1"; y = SMEM16(p);\n')
check('"MEM32(x) = 1"' in out and 'RECOMP_DEV_R_SMEM16(p)' in out, out)
for line in ['    MEM32(ebp + 8) = MEM32(ebp + 8) + 4;\n', '    f((MEM32(a) = b), MEM32(c));\n']:
    new, _ = rw(line)
    check(gwd.squash(gwd.unrewrite(new)) == gwd.squash(line), 'round trip: ' + line)

# APU constants, including the lifter's negative displacements
check(gwd.names_apu('MEM32(0xFE80200Cu)'), 'hex APU address')
check(gwd.names_apu('ebx = MEM32(-25157620);'), 'negative decimal APU address')
check(not gwd.names_apu('MEM8(eax + -20971253) = 2;'), 'AC97 is not the APU window')
check(not gwd.names_apu('eax = 0xFE880000u;'), 'end of the window is outside')

# Selection and output on a small generated tree
FILE = '''/* chunk */
#include "recomp_funcs.h"
void sub_00440000(void)
{
    eax = MEM32(0x1000);
}
void sub_00443000(void)
{
    MEM32(0xFE820010u) = eax;
}
void sub_00443100(void)
{
    MEM32(ebx) = edx;
}
void sub_00443200(void)
{
    eax = MEM32(-25157620);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    gen, out_dir = os.path.join(tmp, 'gen'), os.path.join(tmp, 'out')
    os.makedirs(gen)
    with open(os.path.join(gen, 'recomp_0000.c'), 'w') as f:
        f.write(FILE)
    with open(os.path.join(gen, 'recomp_0001.c'), 'w') as f:
        f.write('#include "recomp_funcs.h"\nvoid sub_00010000(void)\n{\n    eax = MEM32(4);\n}\n')
    r = subprocess.run([sys.executable, '-I', TOOL, gen, out_dir],
                       capture_output=True, text=True)
    check(r.returncode == 0, r.stderr)
    with open(os.path.join(out_dir, 'replaced.txt')) as f:
        check(f.read() == 'recomp_0000.c\n', 'only the file with APU functions is replaced')
    with open(os.path.join(out_dir, 'recomp_0000.c')) as f:
        text = f.read()
    check('#include "recomp_web_dev.h"' in text, 'accessor header included')
    check('    eax = MEM32(0x1000);' in text, 'function before the cluster untouched')
    check('RECOMP_DEV_W_MEM32(0xFE820010u, eax)' in text, 'APU function rewritten')
    check('RECOMP_DEV_W_MEM32(ebx, edx)' in text, 'helper inside the cluster rewritten')
    check('RECOMP_DEV_R_MEM32(-25157620)' in text, 'negative-displacement function rewritten')

print('%s (%d failure%s)' % ('FAILED' if failures else 'gen-web-devices: all checks passed',
                             failures, '' if failures == 1 else 's'))
sys.exit(1 if failures else 0)
