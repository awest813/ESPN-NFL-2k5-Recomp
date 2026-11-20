"""Compare the production XXH64 helper with pinned upstream reference outputs."""
from pathlib import Path
import argparse
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--scalar', action='store_true')
    parser.add_argument('--build-dir', type=Path, default=root/'build-web-tests/texture-hash-algo')
    args = parser.parse_args()
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    source = build/'check.c'
    source.write_text(r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include "sg_xxhash64.h"
#include "xxh64_reference.h"
int main(void) {
    unsigned checks=0;
    for(unsigned row=0;row<sizeof xxh64_reference/sizeof *xxh64_reference;row++) {
        size_t n=xxh64_reference[row].bytes;
        for(unsigned offset=0;offset<32;offset++) {
            size_t capacity=n+offset;
            uint8_t *allocation=malloc(capacity?capacity:1);
            if(!allocation)return 2;
            uint8_t *p=allocation+offset;
            for(size_t i=0;i<n;i++)p[i]=(uint8_t)(i*37+(i>>4)*11+19);
            for(unsigned seed=0;seed<4;seed++) {
                uint64_t actual=sg_xxh64(p,n,xxh64_seeds[seed]);
                if(actual!=xxh64_reference[row].expected[seed]) {
                    fprintf(stderr,"XXH64 mismatch length %zu alignment %u seed %u: %016llX expected %016llX\n",
                            n,offset,seed,(unsigned long long)actual,
                            (unsigned long long)xxh64_reference[row].expected[seed]);
                    return 1;
                }
                checks++;
            }
            free(allocation);
        }
    }
    for(unsigned seed=0;seed<4;seed++)
        if(sg_xxh64(NULL,0,xxh64_seeds[seed])!=xxh64_reference[0].expected[seed])return 1;
    printf("PASS %u XXH64 reference checks: all short lengths, word/block tails, 32 alignments, four seeds, exact allocation ends and NULL/empty input\n",checks);
    return 0;
}
''', encoding='utf-8')
    includes = ['-I', str(root/'external/xboxrecomp/src/kernel/sdlgpu'),
                '-I', str(Path(__file__).parent/'fixtures')]
    if args.native:
        compiler = shutil.which('clang') or shutil.which('cc')
        if not compiler:
            parser.error('A native C compiler is required')
        output = build/'check'
        subprocess.run([compiler, str(source), *includes, '-O2', '-g',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-o', str(output)], check=True)
        subprocess.run([str(output)], check=True)
    else:
        compiler, node = shutil.which('emcc'), shutil.which('node')
        if not compiler or not node:
            parser.error('Emscripten and Node are required')
        output = build/'check.js'
        subprocess.run([compiler, str(source), *includes, '-O3',
                        *([] if args.scalar else ['-msimd128']),
                        '-sENVIRONMENT=node', '-sALLOW_MEMORY_GROWTH=1',
                        '-o', str(output)], check=True)
        subprocess.run([node, str(output)], check=True)


if __name__ == '__main__':
    main()
