"""Compile comparison programs emitted by the production D3D11 translator."""

from pathlib import Path
import sys


def function(source, name):
    first = source.index(f"static uint32_t {name}(")
    return source[first:source.index("\n}", first) + 2]


kernel = Path(__file__).resolve().parents[2] / "external/xboxrecomp/src/kernel"
executor = (kernel / "nv2a_pb_exec.c").read_text(encoding="utf-8")
translator = (kernel / "nv2a_gpu_vp.inc.c").read_text(encoding="utf-8")
emitter = translator[translator.index("static const char *k_vp_prelude ="):
                     translator.index("static uint32_t gpu_vp_hash(")]
source = r'''
#define COBJMACROS
#include <d3dcompiler.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Production translator reads the program words and the input mode only. */
/* LIMITS */
static struct { uint32_t prog[VP_PROG_LEN][4]; } s_vp;
static int raw_inputs;
static int gpu_vp_raw_on(void) { return raw_inputs; }
static uint32_t gpu_vp_input_mask(uint32_t start);
/* PRODUCTION */

int main(void)
{
    int failed = 0;
    for (raw_inputs = 0; raw_inputs <= 1; raw_inputs++) {
        for (unsigned op = 9; op <= 12; op++) {
            /* Write MIN, MAX, SLT or SGE of vertex input and constant to oPos.
             * The low bits select XYZW and terminate the one-slot program. */
            s_vp.prog[0][1] = (op << 21) | 0x1bu;
            s_vp.prog[0][2] = (2u << 26) | (3u << 11) | (0x1bu << 17);
            s_vp.prog[0][3] = (15u << 12) | (1u << 11) | 1u;
            uint32_t slots = 0;
            char *shader = gpu_vp_translate(0, &slots);
            if (!shader || slots != 1) return 2;
            ID3DBlob *bytecode = NULL, *errors = NULL;
            HRESULT result = D3DCompile(shader, strlen(shader), "vp_check", NULL, NULL,
                                        "vs_main", "vs_5_0", 0, 0, &bytecode, &errors);
            if (FAILED(result) || !bytecode) {
                fprintf(stderr, "Raw inputs %d, opcode %u failed: %s\n", raw_inputs, op,
                        errors ? (const char *)ID3D10Blob_GetBufferPointer(errors) : "no diagnostic");
                failed = 1;
            }
            if (errors) ID3D10Blob_Release(errors);
            if (bytecode) ID3D10Blob_Release(bytecode);
            free(shader);
        }
    }
    if (!failed) puts("PASS D3D11 MIN, MAX, SLT and SGE with raw and classic inputs");
    return failed;
}
'''
limits = "\n".join(line for line in executor.splitlines()
                   if line.startswith(("#define VP_PROG_LEN ", "#define VP_CONSTS ")))
production = "\n".join((function(executor, "vp_field"),
                         function(executor, "vp_fog_write_mask"), emitter))
Path(sys.argv[1]).write_bytes(source.replace("/* LIMITS */", limits)
                             .replace("/* PRODUCTION */", production).encode("utf-8"))
