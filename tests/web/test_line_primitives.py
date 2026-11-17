"""Compile production line assembly, clipping and D3D11 colour selection to Wasm."""
from pathlib import Path
import re
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
kernel = root / 'external/xboxrecomp/src/kernel'
source = (kernel / 'nv2a_pb_exec.c').read_text(encoding='utf-8')
d3d = (kernel / 'nv2a_gpu_d3d11.inc.c').read_text(encoding='utf-8')


def function(signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]


end = source.index('} XfVert;') + len('} XfVert;')
vertex = source[source.rfind('typedef struct {', 0, end):end]
constants = '\n'.join(re.findall(r'^#define NV_PRIM_\w+\s+\d+.*$', source, re.M))
macro = d3d[d3d.index('#define GPU_LINE('):d3d.index('    lines =', d3d.index('#define GPU_LINE('))]
prefix = r'''
#include <assert.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static struct {unsigned prim,idx_count,provoking_vertex,shade_mode;uint16_t idx[16];} s_gpu;
static struct {unsigned depth_test,zminmax,rej_bad;} s_vp;
typedef void (*BatchLineFn)(void *,uint32_t,uint32_t,uint32_t);
'''
harness = r'''
typedef void (*XfLineFn)(void *,const XfVert *,const XfVert *);
typedef struct {float d0[4],d1[4],pos[4];} GpuVertex;
#define GPU_MAX_VERTS 64
static struct {GpuVertex verts[GPU_MAX_VERTS];} s_gpu11;
static XfVert inputs[16],clipped[2];
static const XfVert *get(unsigned index) {assert(index<16);return &inputs[index];}
static void gpu_vertex(GpuVertex *out,const XfVert *in,unsigned w,unsigned h) {
    memcpy(out->d0,in->col,16);memcpy(out->d1,in->spec,16);memcpy(out->pos,in,16);
}
/* D3D_MACRO */
static unsigned emitted,checks;
static void check_edge(void *ctx,unsigned a,unsigned b,unsigned provoking) {
    unsigned first=s_gpu.prim==NV_PRIM_LINES?emitted*2:emitted;
    unsigned last=(first+1)%s_gpu.idx_count;
    assert(a==s_gpu.idx[first] && b==s_gpu.idx[last]);
    assert(provoking==s_gpu.idx[s_gpu.provoking_vertex?first:last]);emitted++;checks++;
    for(unsigned flat=0;flat<2;flat++) {
        s_gpu.shade_mode=flat?0x1D00:0x1D01;
        unsigned nv=0,rw=64,rh=64;uint16_t ix[]={a,b};
        GPU_LINE(0,1);assert(nv==2);
        for(unsigned k=0;k<2;k++) {
            const XfVert *colour=&inputs[flat?provoking:ix[k]];
            assert(!memcmp(s_gpu11.verts[k].d0,colour->col,16));
            assert(!memcmp(s_gpu11.verts[k].d1,colour->spec,16));
            assert(!memcmp(s_gpu11.verts[k].pos,&inputs[ix[k]],16));checks++;
        }
        unsigned rejected=s_vp.rej_bad;nv=GPU_MAX_VERTS-1;
        GPU_LINE(0,1);assert(nv==GPU_MAX_VERTS-1 && s_vp.rej_bad==rejected+1);
    }
}
static void capture(void *ctx,const XfVert *a,const XfVert *b) {clipped[0]=*a;clipped[1]=*b;emitted++;}
static void close_to(float a,float b) {assert(fabsf(a-b)<0.0001f);checks++;}
int main(void) {
    for(unsigned angle=0;angle<360;angle+=15) {
        float theta=angle*.0174532925199433f,dx=40*cosf(theta),dy=40*sinf(theta);
        float a[]={32,32},b[]={32+dx,32+dy},quad[4][2];
        assert(line_quad(a,b,quad));
        float nx=quad[3][0]-quad[0][0],ny=quad[3][1]-quad[0][1];
        close_to(hypotf(nx,ny),1);close_to(nx*dx+ny*dy,0);
        close_to(quad[1][0]-quad[0][0],dx);close_to(quad[1][1]-quad[0][1],dy);
    }
    {float a[]={0,0},b[]={0,0},q[4][2];assert(!line_quad(a,b,q));
     b[0]=INFINITY;assert(!line_quad(a,b,q));b[0]=NAN;assert(!line_quad(a,b,q));
     b[0]=1000001;assert(!line_quad(a,b,q));}
    for(unsigned k=0;k<16;k++) {
        inputs[k].ok=1;inputs[k].x=k;inputs[k].y=k+1;inputs[k].w=1;
        for(unsigned c=0;c<4;c++) {inputs[k].col[c]=k+c*.125f;inputs[k].spec[c]=k+c*.25f;}
    }
    unsigned seed=29;
    for(unsigned shuffle=0;shuffle<64;shuffle++) {
        for(unsigned k=0;k<16;k++)s_gpu.idx[k]=k;
        for(unsigned k=15;k;k--) {
            seed=seed*1664525u+1013904223u;unsigned p=seed%(k+1);
            uint16_t tmp=s_gpu.idx[k];s_gpu.idx[k]=s_gpu.idx[p];s_gpu.idx[p]=tmp;
        }
        for(unsigned prim=0;prim<=10;prim++)for(unsigned n=0;n<=16;n++)for(unsigned first=0;first<2;first++) {
            s_gpu.prim=prim;s_gpu.idx_count=n;s_gpu.provoking_vertex=first;emitted=0;
            batch_lines(check_edge,NULL);
            unsigned expected=prim==2?n/2:prim==3 && n>=2?n:prim==4 && n>=2?n-1:0;
            assert(emitted==expected);checks++;
        }
    }
    XfVert a=inputs[1],b=inputs[2],original[2];
    a.x=8;a.y=10;a.z=-1;a.w=1;a.tc[0][0]=0;a.fog=0;
    b.x=24;b.y=20;b.z=1;b.w=1;b.tc[0][0]=8;b.fog=1;
    original[0]=a;original[1]=b;s_vp.depth_test=1;s_vp.zminmax=0;
    for(unsigned flat=0;flat<2;flat++)for(unsigned first=0;first<2;first++) {
        s_gpu.shade_mode=flat?0x1D00:0x1D01;emitted=0;
        const XfVert *provoking=first?&a:&b;
        raster_line_clip(&a,&b,flat?provoking:NULL,capture,NULL);assert(emitted==1);
        close_to(clipped[0].x,16);close_to(clipped[0].y,15);close_to(clipped[0].z,0);
        close_to(clipped[0].tc[0][0],4);close_to(clipped[0].fog,.5f);
        for(unsigned c=0;c<4;c++) {
            close_to(clipped[0].col[c],flat?provoking->col[c]:(a.col[c]+b.col[c])*.5f);
            close_to(clipped[0].spec[c],flat?provoking->spec[c]:(a.spec[c]+b.spec[c])*.5f);
        }
        assert(!memcmp(&a,&original[0],sizeof a) && !memcmp(&b,&original[1],sizeof b));
    }
    s_gpu.shade_mode=0x1D01;a.z=b.z=-1;emitted=0;
    raster_line_clip(&a,&b,NULL,capture,NULL);assert(!emitted);
    a.x=.0625f;b.x=1.0625f;a.w=b.w=1;a.z=-1;b.z=2;emitted=0;
    raster_line_clip(&a,&b,NULL,capture,NULL);assert(emitted==1);
    close_to(clipped[0].x,.0625f+1.0f/3.0f); /* Never resnap clip intersections. */
    a.z=b.z=1;a.w=-.5f;b.w=1;emitted=0;
    raster_line_clip(&a,&b,NULL,capture,NULL);assert(emitted==1);close_to(clipped[0].w,.001f);
    a.x=NAN;emitted=0;raster_line_clip(&a,&b,NULL,capture,NULL);assert(!emitted);
    printf("PASS %u line assembly/colour/clipping checks\n",checks);
}
'''.replace('/* D3D_MACRO */', macro)
out = root / 'build-web-tests/line-primitives'
out.mkdir(parents=True, exist_ok=True)
body = (prefix + constants + '\n' + vertex + '\n' + function('static int primitive_is_lines(')
        + function('static void batch_lines(') + (kernel / 'nv2a_line.h').read_text(encoding='utf-8') + function('static void xf_lerp(')
        + 'typedef void (*XfLineFn)(void *,const XfVert *,const XfVert *);\n'
        + function('static void raster_line_clip(') + harness.replace(
            'typedef void (*XfLineFn)(void *,const XfVert *,const XfVert *);', ''))
(out / 'test.c').write_bytes(body.encode('utf-8'))
subprocess.run([shutil.which('emcc') or 'emcc', str(out / 'test.c'), '-O2',
                '-sENVIRONMENT=node', '-o', str(out / 'test.js')], check=True)
subprocess.run([shutil.which('node') or 'node', str(out / 'test.js')], check=True, timeout=30)
