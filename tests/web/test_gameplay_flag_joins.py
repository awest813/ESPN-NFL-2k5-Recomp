"""Execute the generated flag-join blocks reached by the retail mode audit.

No disc is needed. Expected results come from the original DEC/TEST/CMP
and x87 status-byte branch semantics, including both sides of each join.
"""
from pathlib import Path
import importlib.util
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'build-web-tests/gameplay-flag-joins'
out.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('mode_patches', root / 'tools/apply-gen-patches.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)
ids = {'JOIN_1AE8D5_ZERO', 'JOIN_2F7CA4_TEST', 'JOIN_2F7CA4_CMP', 'JOIN_2F7CA4_COMPLETE',
       'JOIN_A2822_TEST', 'JOIN_A2822_CMP'}
patcher.PATCHES = [p for p in patcher.PATCHES if p[0] in ids]
assert len(patcher.PATCHES) == len(ids)
patcher.GEN = str(out / 'generated')
Path(patcher.GEN).mkdir(exist_ok=True)
fixture = Path(patcher.GEN) / 'recomp_0000.c'
fixture.write_text(''.join(
    'void ' + fn + '(void)\n{\n' + '\n'.join(p[2] for p in patcher.PATCHES if p[1] == fn) + '\n}\n'
    for fn in sorted({p[1] for p in patcher.PATCHES})), encoding='utf-8')
assert patcher.main() == 0
first = fixture.read_bytes()
assert patcher.main() == 0 and first == fixture.read_bytes()
for name in ids:
    assert first.count(('NFL2K5-GENPATCH:' + name).encode()) == 1

a = (root / 'src/recomp/gen/recomp_0013.c').read_text(encoding='utf-8')
b = (root / 'src/recomp/gen/recomp_0021.c').read_text(encoding='utf-8')
c = (root / 'src/recomp/gen/recomp_0004.c').read_text(encoding='utf-8')
def block(source, start, end):
    begin = source.index(start + ': ;')
    return source[begin:source.index(end + ': ;', begin)]
zero = block(a, 'loc_001AE8B3', 'loc_001AE8B6') + block(a, 'loc_001AE8C7', 'loc_001AE8D7')
status = block(b, 'loc_002F7C97', 'loc_002F7CA6')
transition = block(c, 'loc_000A281B', 'loc_000A2824')
assert 'NFL2K5-GENPATCH:JOIN_1AE8D5_ZERO' in zero
assert 'NFL2K5-GENPATCH:JOIN_2F7CA4_COMPLETE' in status
harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
static unsigned gaps;
#define RECOMP_FLAGS_FALLBACK(a, f) (++gaps, (f))
#define SET_LO8(r, v) ((r) = ((r) & 0xffffff00u) | ((v) & 255u))
#define HI8(r) (((r) >> 8) & 255u)
#define CMP_NE(a, b) ((a) != (b))
#define CMP_EQ(a, b) ((a) == (b))
#define TEST_Z(a, b) (((a) & (b)) == 0)
#define TEST_NZ(a, b) (((a) & (b)) != 0)
#define RECOMP_PARITY8(v) (!__builtin_parity((v) & 255u))
#define MEM32(va) memory_value
static int zero_join(unsigned path, uint32_t input) {
    uint32_t eax=input, edx=0, esp=0, _fa=0, _fb=0, memory_value=input;
    int32_t _fas=0, _fbs=0; int _flags=0;
    if (path) goto loc_001AE8C7;
    /* ZERO */
loc_001AE8D7: return 1; /* update */
loc_001AE92C: return 0; /* skip update */
}
static int status_join(unsigned path, unsigned status, uint32_t memory_value) {
    uint32_t eax=status << 8, ecx=0, _fa=0, _fb=0;
    int32_t _fas=0, _fbs=0; int _flags=0;
    if (path) goto loc_002F7C9C;
    /* STATUS */
loc_002F7CA6: return 1;
loc_002F7CE3: return 0;
}
static int transition_join(unsigned path, uint32_t eax) {
    uint32_t _fa=0, _fb=0; int32_t _fas=0, _fbs=0; int _flags=0;
    if (path) goto loc_000A281F;
    /* TRANSITION */
loc_000A2824: return 1;
loc_000A2834: return 0;
}
int main(void) {
    const uint32_t edge[]={0,1,2,19,20,0x7fffffffu,0x80000000u,0xffffffffu};
    for (unsigned i=0;i<sizeof edge/sizeof *edge;i++) {
        assert(zero_join(0,edge[i]) == (edge[i] != 1));
        assert(zero_join(1,edge[i]) == (edge[i] != 1));
        assert(transition_join(0,edge[i]) == (edge[i] == 0));
        assert(transition_join(1,edge[i]) == (edge[i] == 20));
    }
    for (unsigned i=0;i<10000;i++) {
        assert(zero_join(0,i) == (i != 1));
        assert(zero_join(1,i) == (i != 1));
        assert(transition_join(0,i) == (i == 0));
        assert(transition_join(1,i) == (i == 20));
    }
    for (unsigned s=0;s<256;s++) for (unsigned i=0;i<sizeof edge/sizeof *edge;i++) {
        assert(status_join(0,s,edge[i]) == ((s & 0x41) != 0));
        unsigned parity=((s & 1) != 0) + ((s & 4) != 0);
        assert(status_join(1,s,edge[i]) == (!(parity & 1) && edge[i] != 0));
    }
    assert(gaps == 0);
    puts("PASS gameplay flag joins: DEC/TEST zero, transition TEST/CMP, x87 status, null/non-null CMP, regeneration and no obsolete fallback");
}
'''.replace('/* ZERO */', zero).replace('/* STATUS */', status).replace('/* TRANSITION */', transition)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2', '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True, timeout=30)
