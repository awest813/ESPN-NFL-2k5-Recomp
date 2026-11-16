"""Dead table bytes must not change flags on an executable guest path."""
import ast
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

root = Path(__file__).resolve().parents[2]
source = root / 'external/xboxrecomp/tools/recomp/translator.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_flag_predecessors')
scope = {}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), scope)
preds = scope['_flag_predecessors']


def block(start, mnemonic, end, target=None, address=None):
    return SimpleNamespace(start=start, instructions=[SimpleNamespace(
        mnemonic=mnemonic, jump_target=target, end_address=end,
        address=start if address is None else address, is_ret=mnemonic == 'ret')])


# A dead loop into a real CMP consumer must not create a flag join.
cfg = [block(0, 'jmp', 5, 20), block(5, 'jmp', 10, 20),
       block(20, 'jne', 22, 40), block(22, 'ret', 23), block(40, 'ret', 41)]
assert preds(cfg, 0, {})[20] == {0}
# A real alternate path still contributes, even when its flag setter differs.
cfg[0] = block(0, 'jne', 5, 20)
assert preds(cfg, 0, {})[20] == {0, 5}
# Known switch cases are reachable; their flag state must not be discarded.
cfg = [block(0, 'jmp', 2), block(5, 'jmp', 10, 20),
       block(10, 'jmp', 15, 20), block(20, 'ret', 21)]
assert preds(cfg, 0, {0: [5, 10]})[20] == {5, 10}
# An unresolved reachable jump preserves conservative joins.
assert preds(cfg, 0, {})[20] == {5, 10}
# An unresolved dead jump cannot prevent a proof on the actual entry path.
cfg[0] = block(0, 'jmp', 2, 20)
cfg.insert(1, block(2, 'jmp', 4))
assert preds(cfg, 0, {})[20] == {0}
# Back edges reachable from entry remain, as do both sides of a conditional.
cfg = [block(0, 'cmp', 2), block(2, 'je', 4, 10),
       block(4, 'jmp', 8, 2), block(10, 'ret', 11)]
assert preds(cfg, 0, {})[2] == {0, 4}
# A missing instruction is not an implicit jump across a gap in the decode.
assert preds([block(0, 'mov', 2), block(8, 'ret', 9)], 0, {})[8] == set()
print('PASS flag CFG: dead predecessors, real alternatives, switch edges, unknown jumps, loops and decode gaps')

text = (root / 'src/recomp/gen/recomp_0008.c').read_text(encoding='utf-8')
function = text[text.index('void sub_0010CFB0(void)'):text.index('void sub_0010D00E(void)')]
begin = function.index('loc_0010D01C: ;')
body = function[begin:function.index('    /* nop */', begin)]
harness = r'''
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
static uint32_t ecx,esp,loaded_value,selected,tail_arg,g_seh_ebp;
static unsigned events,tails,gaps;
#define CMP_NE(a,b) ((a)!=(b))
#define TEST_Z(a,b) (((a)&(b))==0)
#define LO8(r) ((r)&255u)
#define SET_LO8(r,v) ((r)=((r)&0xFFFFFF00u)|((v)&255u))
#define MEM32(va) loaded_value
#define PUSH32(sp,value) ((sp)-=4)
#define RECOMP_FLAGS_FALLBACK(addr,f) (++gaps,(f))
#define RECOMP_ABI_CALL(addr,fn) fn()
static void sub_0005A480(void) {selected=ecx;events++;esp+=4;}
static void sub_00059010(void) {tail_arg=ecx;tails++;esp+=4;}
static void translated_event(uint32_t selector,uint32_t loaded) {
    uint32_t _fa=0,_fb=0,ebp=0,esi=0xC0FFEEu;
    int32_t _fas=0,_fbs=0;int _cf=0,_flags=0;
    ecx=selector;loaded_value=loaded;esp=1024;
    events=tails=0;
    /* RETAIL_BLOCK */
}
static void check(uint32_t selector,uint32_t loaded) {
    translated_event(selector,loaded);
    /* Original: CMP ECX,1; MOV ECX,[state]; JNE; TEST/SETE CL; ADD CL,base. */
    uint32_t base=selector==1?0x74u:0x87u;
    uint32_t expected=(loaded&0xFFFFFF00u)| (base+(loaded==0));
    assert(selected==expected && events==1 && tails==1);
    assert(tail_arg==0xC0FFEEu && esp==1028);
}
int main(void) {
    const uint32_t values[]={0,1,2,19,255,256,0x7FFFFFFFu,0x80000000u,0xFFFFFFFFu};
    for(unsigned i=0;i<9;i++)for(unsigned j=0;j<9;j++)check(values[i],values[j]);
    uint32_t seed=0x10D025u;
    for(unsigned i=0;i<10000;i++) {
        seed=seed*1664525u+1013904223u;uint32_t selector=seed;
        seed=seed*1664525u+1013904223u;check(selector,seed);
        check(1,seed);
    }
    assert(gaps==0);
    puts("PASS retail CMP/MOV/JNE event selection: 20081 cases, both paths, overwritten register, call/stack behavior and no fallback");
}
'''.replace('/* RETAIL_BLOCK */', body)
out = root / 'build-web-tests/flag-cfg-reachability'
out.mkdir(parents=True, exist_ok=True)
(out / 'test.c').write_text(harness, encoding='utf-8')
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2', '-sENVIRONMENT=node',
                '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True, timeout=30)
