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
       'JOIN_A2822_TEST', 'JOIN_A2822_CMP', 'JOIN_221ABB_CMP', 'JOIN_221ABB_TEST', 'JOIN_221ABB_COMPLETE',
       'JOIN_167707_TEST', 'JOIN_167707_CMP', 'JOIN_167707_COMPLETE',
       'JOIN_2FAD42_TEST', 'JOIN_2FAD42_CMP', 'JOIN_2FAD42_COMPLETE',
       'JOIN_3D4CFB_TEST', 'JOIN_3D4CFB_NE',
       'JOIN_3D4CFB_OVERLAP_TEST', 'JOIN_3D4CFB_OVERLAP_CMP'}
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
d = (root / 'src/recomp/gen/recomp_0015.c').read_text(encoding='utf-8')
e = (root / 'src/recomp/gen/recomp_0011.c').read_text(encoding='utf-8')
frontend_source = (root / 'src/recomp/gen/recomp_0026.c').read_text(encoding='utf-8')
def block(source, start, end):
    begin = source.index(start + ': ;')
    return source[begin:source.index(end + ': ;', begin)]
zero = block(a, 'loc_001AE8B3', 'loc_001AE8B6') + block(a, 'loc_001AE8C7', 'loc_001AE8D7')
status = block(b, 'loc_002F7C97', 'loc_002F7CA6')
transition = block(c, 'loc_000A281B', 'loc_000A2824')
kickoff = block(d, 'loc_00221AA6', 'loc_00221ABD')
# Execute the actual TEST predecessor and CMP join, with their flags already
# established. The original disc has JNE at 167707 and JE at 2FAD42; the
# respective false successors are 16770D and 2FAD44.
def test_predecessor(source, marker, end):
    begin = source.index('/* NFL2K5-GENPATCH:' + marker + ' */')
    return source[begin:source.index(end + ': ;', begin)]
queue = block(e, 'loc_00167707', 'loc_0016770D')
queue_test = test_predecessor(e, 'JOIN_167707_TEST', 'loc_00167822')
selection = block(b, 'loc_002FAD42', 'loc_002FAD44')
selection_test = test_predecessor(b, 'JOIN_2FAD42_TEST', 'loc_002FAD13')
frontend_template = r'''
static int NAME(unsigned test, uint32_t eax, uint32_t edi, int8_t memory_count) {
    uint32_t esi=0,esp=0,_fa=0,_fb=0;int32_t _fas=0,_fbs=0;int _flags=0;
    if(!test)goto loc_003D4CF5;
    /* FRONTEND_TEST */
    /* FRONTEND_CMP */
loc_003D4CFD:return 1; /* write state 3 */
loc_003D4D01:return 0; /* preserve state */
}
'''
def frontend_body(function_name, test_name):
    begin = frontend_source.index('void ' + function_name + '(void)')
    body = frontend_source[begin:frontend_source.index('\n}\n', begin)]
    return frontend_template.replace('NAME', test_name).replace(
        '/* FRONTEND_TEST */', block(body, 'loc_003D4CAF', 'loc_003D4CBB')).replace(
        '/* FRONTEND_CMP */', block(body, 'loc_003D4CF5', 'loc_003D4CFD'))
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
#define SMEM8(va) memory_count
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
static int kickoff_join(unsigned cmp, uint32_t memory_value) {
    uint32_t edx=0,eax=0,_fa=0,_fb=0;int32_t _fas=0,_fbs=0;int _flags=0;
    if(!cmp)goto loc_00221AB4;
    /* KICKOFF */
loc_00221ABD:return 0;
loc_00221ACD:return 1;
}
static int queue_join(unsigned test, uint32_t _fa, uint32_t _fb) {
    int _flags=0;
    if(!test)goto loc_00167707;
    /* QUEUE_TEST */
    /* QUEUE */
loc_0016770D:return 0;
loc_00167673:return 1;
}
static int selection_join(unsigned test, uint32_t _fa, uint32_t _fb) {
    int _flags=0;
    if(!test)goto loc_002FAD42;
    /* SELECTION_TEST */
    /* SELECTION */
loc_002FAD44:return 0;
loc_002FAD46:return 1;
}
/* FRONTEND_STANDALONE */
/* FRONTEND_OVERLAP */
int main(void) {
    unsigned frontend_failures[4]={0};
    const uint32_t frontend_values[]={0,1,2,3,4,5,6,0x7fffffffu,0x80000000u,0xffffffffu};
    for(unsigned i=0;i<sizeof frontend_values/sizeof *frontend_values;i++) {
        uint32_t value=frontend_values[i];
        frontend_failures[0]+=frontend_standalone(1,value,0,0)!=(value==0||value==5);
        frontend_failures[1]+=frontend_overlap(1,value,0,0)!=(value==0||value==5);
        for(int count=-128;count<=127;count++) {
            unsigned same=value==(uint32_t)(int32_t)count;
            frontend_failures[2]+=frontend_standalone(0,0,value,count)!=same;
            frontend_failures[3]+=frontend_overlap(0,0,value,count)!=same;
        }
    }
    for(int count=-128;count<=127;count++) {
        uint32_t same=(uint32_t)(int32_t)count;
        frontend_failures[2]+=frontend_standalone(0,0,same,count)!=1;
        frontend_failures[3]+=frontend_overlap(0,0,same,count)!=1;
        frontend_failures[2]+=frontend_standalone(0,0,same+1,count)!=0;
        frontend_failures[3]+=frontend_overlap(0,0,same+1,count)!=0;
    }
    printf("frontend mismatches: standalone TEST=%u overlap TEST=%u standalone CMP=%u overlap CMP=%u\n",
           frontend_failures[0],frontend_failures[1],frontend_failures[2],frontend_failures[3]);
    for(unsigned i=0;i<4;i++)assert(frontend_failures[i]==0);
    for(unsigned i=0;i<1024;i++) {
        assert(kickoff_join(0,i)==((i&0x1C0)==0));
        assert(kickoff_join(1,i)==((i&0x1C0)==0x40));
    }
    const uint32_t edge[]={0,1,2,19,20,0x7fffffffu,0x80000000u,0xffffffffu};
    for(unsigned a=0;a<sizeof edge/sizeof *edge;a++)
    for(unsigned b=0;b<sizeof edge/sizeof *edge;b++) {
        assert(queue_join(0,edge[a],edge[b])==(edge[a]!=edge[b]));
        assert(queue_join(1,edge[a],edge[b])==((edge[a]&edge[b])!=0));
        assert(selection_join(0,edge[a],edge[b])==(edge[a]==edge[b]));
        assert(selection_join(1,edge[a],edge[b])==((edge[a]&edge[b])==0));
    }
    for(unsigned a=0;a<32;a++)for(unsigned b=0;b<32;b++) {
        uint32_t left=1u<<a,right=1u<<b;
        assert(queue_join(0,left,right)==(a!=b));
        assert(queue_join(1,left,right)==(a==b));
        assert(selection_join(0,left,right)==(a==b));
        assert(selection_join(1,left,right)==(a!=b));
    }
    for (unsigned i=0;i<sizeof edge/sizeof *edge;i++) {
        assert(kickoff_join(0,edge[i])==((edge[i]&0x1C0)==0));
        assert(kickoff_join(1,edge[i])==((edge[i]&0x1C0)==0x40));
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
    puts("PASS gameplay flag joins: DEC/TEST zero, transition TEST/CMP, x87 status, null/non-null CMP, kickoff TEST/CMP, queue JNE and selection JE, overlapping frontend TEST/CMP, regeneration and no obsolete fallback");
}
'''
for placeholder, production in {
    'ZERO': zero, 'STATUS': status, 'TRANSITION': transition, 'KICKOFF': kickoff,
    'QUEUE_TEST': queue_test, 'QUEUE': queue,
    'SELECTION_TEST': selection_test, 'SELECTION': selection,
    'FRONTEND_STANDALONE': frontend_body('sub_003D4C02', 'frontend_standalone'),
    'FRONTEND_OVERLAP': frontend_body('sub_003D4940', 'frontend_overlap'),
}.items():
    harness = harness.replace('/* ' + placeholder + ' */', production)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2', '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True, timeout=30)
