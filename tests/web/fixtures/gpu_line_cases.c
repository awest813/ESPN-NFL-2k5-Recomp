#include <math.h>
#include <float.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#define VP_PROG_LEN 136
#define VP_CONSTS 192
#define VP_VPSCL 58
#define VP_VPOFF 59
#define NV_VERTEX_ATTRS 16
typedef unsigned DWORD;
static DWORD GetTickCount(void){return 0;}
static struct {unsigned start;uint32_t prog[136][4];float c[192][4];unsigned depth_test,zminmax,specular_enable,light_control,control0;uint64_t verts;}s_vp;
static uint8_t s_const_written[192];static unsigned s_vp_cgen;
static void const_unwritten_note(int c,int a){(void)c;(void)a;}
static uint32_t vp_field(const uint32_t*t,int word,int bit,int len){return(t[word]>>bit)&((1u<<len)-1u);}
typedef struct{uint32_t offset,type,size,stride;}VertexAttr;
typedef struct{uint32_t color,width,height;}Texture;
static struct{VertexAttr attr[16];uint16_t idx[512];uint32_t idx_count,shade_mode,prim,provoking_vertex,format;int inline_active;unsigned inline_count;void*inline_buf;Texture tex;}s_gpu;
static Texture s_stage[4];static float s_attr_inline[16][4];
static struct{unsigned enable,mode;float p[3];}s_fog;
static _Alignas(16) uint8_t memory[131072];
static void*xbox_GetMemoryOffset(void){return memory;}
static bool xbox_guest_memory_direct(uintptr_t base,uint64_t address,size_t bytes,bool writable){(void)base;(void)writable;return address>=16&&address<sizeof memory&&bytes<=sizeof memory-address;}
static bool xbox_guest_memory_read(uintptr_t base,uint64_t address,void*out,size_t bytes){if(!xbox_guest_memory_direct(base,address,bytes,false))return false;memcpy(out,(void*)(base+address),bytes);return true;}
static int tex_size_from_format(uint32_t color){(void)color;return 0;}
#include "nv2a_line.h"
#include "line_width_reference.h"
typedef unsigned Uint32;
typedef struct{unsigned location,buffer_slot,format,offset;}SDL_GPUVertexAttribute;
enum{SDL_GPU_VERTEXELEMENTFORMAT_FLOAT4};
/* LIVE_CPU */
/* LIVE_SHADER */
static void save(const char*name,const void*data,size_t bytes){FILE*f=fopen(name,"wb");if(!f||fwrite(data,1,bytes,f)!=bytes)abort();fclose(f);}
static FILE*json;
static unsigned baseline_count;
static void endpoint(FILE*f,const XfVert*v){
    float values[8][4]={{v->x,v->y,v->z,v->w}};
    int affine=0;(void)affine;
    memcpy(values[1],v->col,16);memcpy(values[2],v->spec,16);memcpy(values[3],v->tc,64);values[7][0]=v->fog;
    for(unsigned k=0;k<32;k++)fprintf(f,"%s%.9g",k?",":"",((float*)values)[k]);
}
static void baseline(void*unused,const XfVert*first,const XfVert*second){
    (void)unused;XfVert a=*first,b=*second;
    if(!a.ok||!b.ok)return;
    if(!s_vp.depth_test&&a.w>=-1&&a.w<=.001f&&b.w>=-1&&b.w<=.001f)a.w=b.w=1;
    float xy[4][2];if(!line_cover_quad_width(&a.x,&b.x,s_vp.c[191][0],xy))return;
    fprintf(json,"%s{\"endpoints\":[",baseline_count++?",":"");endpoint(json,&a);fprintf(json,",");endpoint(json,&b);
    fprintf(json,"],\"quad\":[");const unsigned corners[]={0,1,2,0,2,3};
    for(unsigned k=0;k<6;k++)fprintf(json,"%s%.9g,%.9g,0",k?",":"",xy[corners[k]][0],xy[corners[k]][1]);fprintf(json,"]}");
}
static void baseline_index(void*unused,uint32_t a,uint32_t b,uint32_t provoking) {
    raster_line_clip(vp_vertex(a),vp_vertex(b),s_gpu.shade_mode==0x1d00?vp_vertex(provoking):NULL,baseline,unused);
}
static void set_vertex(unsigned index,float x,float y,float z,float w,unsigned color){
    float(*v)[4]=(float(*)[4])(memory+16+index*256);memset(v,0,256);
    v[0][0]=x;v[0][1]=y;v[0][2]=z;v[0][3]=w;
    v[3][0]=((color>>16)&255)/255.0f;v[3][1]=((color>>8)&255)/255.0f;v[3][2]=(color&255)/255.0f;v[3][3]=(color>>24)/255.0f;
    v[4][0]=.2f;v[4][1]=.3f;v[4][2]=.4f;v[4][3]=.5f;
    v[5][0]=.25f;
    for(unsigned a=9;a<=12;a++){v[a][0]=(index&1)?1.25f:.25f;v[a][1]=.5f;v[a][2]=.75f;v[a][3]=1;}
}
int main(void){
    const unsigned attrs[]={0,3,4,5,9,10,11,12};
    for(unsigned i=0;i<8;i++){
        uint32_t*t=s_vp.prog[i];t[1]=(1u<<21)|(attrs[i]<<9)|0x1bu;t[2]=2u<<26;
        t[3]=(15u<<12)|(1u<<11)|(attrs[i]<<3)|(i==7);
    }
    for(unsigned a=0;a<16;a++)s_gpu.attr[a]=(VertexAttr){16+a*16,2,4,256};
    uint32_t mask=vp_input_mask(0);char*source=sg_vp_translate_line_wgsl(0,mask);if(!source)return 1;
    save("line.wgsl",source,strlen(source));free(source);
    save("line.frag.wgsl",k_sg_xf_linevp_frag_wgsl,strlen(k_sg_xf_linevp_frag_wgsl));
    save("baseline.vert.wgsl",k_sg_lines_vert_wgsl,strlen(k_sg_lines_vert_wgsl));
    save("baseline.frag.wgsl",k_sg_xf_line_frag_wgsl,strlen(k_sg_xf_line_frag_wgsl));
    save("golden.rgb.bin",line_reference_rgb,sizeof line_reference_rgb);
    SDL_GPUVertexAttribute attributes[16];unsigned attribute_count=sg_linevp_attributes(mask,attributes);
    FILE*layout=fopen("layout.json","wb");fprintf(layout,"{\"stride\":%u,\"attributes\":[",2*sg_vp_input_stride(mask));
    for(unsigned a=0;a<attribute_count;a++)fprintf(layout,"%s{\"shaderLocation\":%u,\"offset\":%u,\"format\":\"float32x4\"}",a?",":"",attributes[a].location,attributes[a].offset);
    fprintf(layout,"]}");fclose(layout);
    s_linevp.stride=sg_vp_input_stride(mask);s_linevp.data=calloc(512,2*s_linevp.stride);
    FILE*manifest=fopen("cases.json","wb");fprintf(manifest,"[");
    unsigned golden=sizeof line_width_references/sizeof*line_width_references;
    for(unsigned test=0;test<golden+44;test++){
        if(test==golden+40) {
            s_vp.prog[7][3]&=~1u;
            uint32_t*t=s_vp.prog[8];t[1]=(13u<<21)|(9u<<9);t[2]=2u<<26;t[3]=0;
            t=s_vp.prog[9];t[1]=(7u<<21)|0x1bu;t[2]=(2u<<26)|(3u<<11)|(1u<<21)|(2u<<19)|(3u<<17);t[3]=(8u<<24)|(2u<<20)|2u;
            t=s_vp.prog[10];t[1]=(4u<<21)|(3u<<13)|0x1bu;t[2]=(2u<<26)|(3u<<11)|(1u<<21)|(2u<<19)|(3u<<17);t[3]=(2u<<30)|(1u<<28)|(12u<<12)|(1u<<11)|1u;
            memcpy(s_vp.c[0],(float[]){1,0,0,0},16);memcpy(s_vp.c[1],(float[]){0,1,0,0},16);memcpy(s_vp.c[3],(float[]){.5f,.5f,1,1},16);
            char*matrix=sg_vp_translate_line_wgsl(0,mask);if(!matrix)abort();save("matrix-line.wgsl",matrix,strlen(matrix));free(matrix);
        }
        unsigned local=test-golden;float width=test<golden?line_width_references[test].expected_width/8.0f:1.0f;
        s_gpu.prim=NV_PRIM_LINES;s_gpu.provoking_vertex=0;s_gpu.shade_mode=0x1d01;s_vp.depth_test=1;s_vp.zminmax=0;s_vp.specular_enable=1;s_vp.light_control=1u<<17;s_fog.enable=0;
        unsigned lines=test<golden?16:1,flat=0,provoking=0,blend=0,texture=0;
        set_vertex(0,16.03f,20.52f,.25f,1,0xffff0000u);set_vertex(1,56.48f,36.04f,.75f,2,0xff0000ffu);
        if(test<golden) {
            s_vp.depth_test=0;
            for(unsigned segment=0;segment<16;segment++)for(unsigned side=0;side<2;side++) {
                unsigned k=(segment+side)%16;uint32_t c=line_reference_palette[k%8];
                c=(c&0xff00ff00u)|((c>>16)&255u)|((c&255u)<<16);
                set_vertex(segment*2+side,160+line_reference_xy[k][0],48+line_reference_xy[k][1],1,1,c);
            }
        }
        else if(local<12){float w[]={-2,-1,-.5f,0,.0005f,.001f,2};((float*)(memory+16))[3]=w[local%7];((float*)(memory+16+256))[3]=w[(local+3)%7];if(local>=7)s_vp.depth_test=0;}
        else if(local<16){((float*)(memory+16))[2]=local&1?-.25f:.25f;((float*)(memory+16+256))[2]=-.75f;if(local>=14)s_vp.zminmax=0x10;}
        else if(local<20){flat=1;provoking=local&1;s_gpu.shade_mode=0x1d00;((float*)(memory+16))[3]=local>=18?-.5f:1;}
        else if(local==20){lines=65;s_vp.depth_test=0;blend=1;width=3;for(unsigned i=0;i<130;i++)set_vertex(i,8+(i&1)*48,20,.25f,1,(i/2)&1?0x8000ff00u:0x80ff0000u);}
        else if(local==21){texture=1;}
        else if(local==22){s_fog.enable=1;s_fog.mode=0x2601;s_fog.p[0]=1.25f;s_fog.p[1]=-.5f;}
        else if(local==23){width=511.0f/8;}
        else if(local>=24&&local<=27){((float*)(memory+16))[local-24]=NAN;}
        else if(local==28){((float*)(memory+16))[3]=INFINITY;}
        else if(local==29){((float*)(memory+16+256))[0]=((float*)(memory+16))[0];((float*)(memory+16+256))[1]=((float*)(memory+16))[1];}
        else if(local==30){width=0;}
        else if(local==31){set_vertex(0,8.5f,20.5f,.25f,1,0xffff0000u);set_vertex(1,56.5f,20.5f,.25f,1,0xff0000ffu);}
        unsigned vertices=lines*2;
        if(test>=golden && local>=32 && local<36) {
            vertices=4;s_gpu.prim=local&1?NV_PRIM_LINE_LOOP:NV_PRIM_LINE_STRIP;
            flat=1;provoking=(local>>1)&1;s_gpu.shade_mode=0x1d00;
            set_vertex(0,8.5f,8.5f,.25f,1,0xffff0000u);set_vertex(1,56.5f,8.5f,.25f,1,0xff00ff00u);
            set_vertex(2,56.5f,56.5f,.25f,1,0xff0000ffu);set_vertex(3,8.5f,56.5f,.25f,1,0xffffffffu);
        }
        if(test>=golden && local==36){lines=3;vertices=6;for(unsigned i=0;i<6;i++)set_vertex(i,8.5f+(i&1)*48,20.5f,i<2?.25f:i<4?.75f:.125f,1,i<2?0xffff0000u:i<4?0xff0000ffu:0xff00ff00u);}
        if(test>=golden && local==37){s_fog.enable=1;s_fog.mode=0x800;s_fog.p[0]=1;s_fog.p[1]=-.05f;((float*)(memory+16+256))[5*4]=1.5f;}
        if(test>=golden && local==38){flat=1;provoking=0;s_gpu.shade_mode=0x1d00;float *spec=(float*)(memory+16+256+4*16);spec[0]=.7f;spec[1]=.6f;spec[2]=.1f;spec[3]=.9f;}
        if(test>=golden && local==39){((float*)(memory+16))[3*4+3]=.25f;((float*)(memory+16+256))[3*4+3]=.75f;}
        if(test>=golden && local==41)((float*)(memory+16))[3]=-.5f;
        if(test>=golden && local==42){flat=1;provoking=1;s_gpu.shade_mode=0x1d00;}
        if(test>=golden && local==43)((float*)(memory+16))[3]=-INFINITY;
        s_gpu.provoking_vertex=provoking;s_gpu.idx_count=vertices;for(unsigned i=0;i<vertices;i++)s_gpu.idx[i]=i;
        vertex_inputs_prepare(&s_linevp.inputs,mask,vertices-1);s_linevp.count=0;batch_lines(sg_pack_line_vp,NULL);lines=s_linevp.count;
        float uniforms[788]={0};memcpy(uniforms,s_vp.c,sizeof s_vp.c);
        uniforms[768]=640;uniforms[769]=480;uniforms[770]=1;
        uniforms[776]=s_fog.enable;memcpy(uniforms+777,&s_fog.mode,4);uniforms[778]=s_fog.p[0];uniforms[779]=s_fog.p[1];
        uniforms[780]=s_vp.specular_enable;uniforms[781]=(s_vp.light_control>>17)&1;uniforms[782]=((s_vp.zminmax>>4)&15)!=0;
        uniforms[784]=width;uniforms[785]=s_vp.depth_test;uniforms[786]=flat;uniforms[787]=provoking;
        char name[96];snprintf(name,sizeof name,"case-%03u.uniforms.bin",test);save(name,uniforms,sizeof uniforms);
        snprintf(name,sizeof name,"case-%03u.inputs.bin",test);save(name,s_linevp.data,lines*2*s_linevp.stride);
        SgXfShade shade={0};shade.depth[1]=shade.depth[3]=0x3f800000u;
        if(texture){shade.misc[2]=1;shade.mode[0]=1;shade.tex[0][0]=shade.tex[0][1]=2;shade.misc[3]=1u<<16;}
        if(s_fog.enable){shade.fog[0]=0x4080c0;shade.prog[0]=1;shade.color_icw[0]=0xd3200000u;shade.alpha_icw[0]=0x20200000u;shade.color_ocw[0]=shade.alpha_ocw[0]=0xc0;}
        if(test>=golden && local==37){shade.prog[0]=1;shade.prog[1]=4u<<15;shade.mode[3]=4;shade.color_icw[0]=0xcb200000u;shade.alpha_icw[0]=0xd3200000u;shade.color_ocw[0]=shade.alpha_ocw[0]=0xc0;}
        if(test>=golden && local==38){shade.prog[0]=1;shade.color_icw[0]=0xc5200000u;shade.alpha_icw[0]=0xd5200000u;shade.color_ocw[0]=shade.alpha_ocw[0]=0xc0;}
        if(test>=golden && local==39){shade.alpha[0]=1;shade.alpha[1]=0x204;shade.alpha[2]=128;}
        snprintf(name,sizeof name,"case-%03u.shade.bin",test);save(name,&shade,sizeof shade);
        fprintf(manifest,"%s{\"id\":%u,\"width\":%.9g,\"instances\":%u,\"blend\":%u,\"depth\":%u,\"golden\":%s,\"matrix\":%s}",test?",":"",test,width,lines,blend,s_vp.depth_test,test<golden?"true":"false",test>=golden+40?"true":"false");
        snprintf(name,sizeof name,"case-%03u.baseline.json",test);json=fopen(name,"wb");fprintf(json,"[");baseline_count=0;
        s_vp.c[191][0]=width;vp_begin_batch();
        batch_lines(baseline_index,NULL);
        fprintf(json,"]");fclose(json);
        if(test<golden) {
            const LineWidthReference*r=&line_width_references[test];
            snprintf(name,sizeof name,"case-%03u.golden.mask.bin",test);save(name,r->mask,((size_t)r->w*r->h+7)/8);
            snprintf(name,sizeof name,"case-%03u.golden.json",test);FILE*f=fopen(name,"wb");
            fprintf(f,"{\"x\":%u,\"y\":%u,\"w\":%u,\"h\":%u,\"width\":%u,\"probes\":[",r->x,r->y,r->w,r->h,r->expected_width);
            for(unsigned k=0;k<r->count;k++){const LineReferenceProbe*p=&r->probes[k];fprintf(f,"%s[%u,%u,%u,%u,%u]",k?",":"",p->x,p->y,p->r,p->g,p->b);}
            fprintf(f,"]}");fclose(f);
        }
    }
    fprintf(manifest,"]");fclose(manifest);
    if(sg_vp_translate_line_wgsl(VP_PROG_LEN,mask) || sg_vp_translate_line_wgsl(0,mask^1u))abort();
    s_vp.prog[7][3]&=~1u;s_vp.prog[8][1]=(1u<<21)|(13u<<9)|0x1bu;s_vp.prog[8][2]=2u<<26;
    s_vp.prog[8][3]=(15u<<12)|(1u<<11)|(6u<<3)|1u;
    if(sg_vp_translate_line_wgsl(0,vp_input_mask(0)))abort();
    s_vp.prog[0][3]=(15u<<12)|1u;if(sg_vp_translate_line_wgsl(0,vp_input_mask(0)))abort();
    free(s_linevp.data);
    puts("Generated GPU line shaders and actual CPU VP/clipping baselines");
    return 0;
}
