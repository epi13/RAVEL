/*
 * RAVEL execution capsule 0.1
 * Recursive Adaptive Vector Execution Lattice
 *
 * Human-maintained surface: contract, constants, exact fallback, evidence gates.
 * Machine-owned surface: generated expert store and routing lattice in memory.
 */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#define E 256u
#define D 8u
#define K 24u
#define B 256u
#define LO (-64)
#define HI 63

typedef struct { int8_t x[D]; } Q;
typedef struct { int32_t y; uint32_t d; uint16_t e, n; uint8_t cert; } R;
typedef struct { uint64_t q, bad, cert, eval, ns_c, ns_r, sum; } M;

static int8_t C[E][D], W[E][D];
static int16_t Z[E];
static uint16_t T[B][K];
static uint32_t L[B];
static uint64_t S = UINT64_C(0x524156454c9e3779);

static uint32_t u32(void) {
    S ^= S >> 12; S ^= S << 25; S ^= S >> 27;
    return (uint32_t)((S * UINT64_C(2685821657736338717)) >> 32);
}
static uint64_t ns(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static int8_t sat(int v) { return (int8_t)(v < LO ? LO : v > HI ? HI : v); }
static uint32_t sd(const Q *q, uint16_t e) {
    uint32_t z=0; for (uint32_t i=0;i<D;i++){int32_t v=(int32_t)q->x[i]-C[e][i];z+=(uint32_t)(v*v);} return z;
}
static int32_t ex(const Q *q, uint16_t e) {
    int32_t z=Z[e]; for(uint32_t i=0;i<D;i++) z+=(int32_t)q->x[i]*W[e][i]; return z;
}
static int bt(uint32_t d,uint16_t e,uint32_t bd,uint16_t be){return d<bd||(d==bd&&e<be);}
static uint16_t bk(const Q *q,int *ok){uint16_t b=0;*ok=1;for(uint32_t i=0;i<D;i++)if(q->x[i]<LO||q->x[i]>HI)*ok=0;for(uint32_t i=0;i<4;i++){int v=((int)q->x[i]-LO)/32;if(v<0)v=0;if(v>3)v=3;b=(uint16_t)((b<<2)|(uint16_t)v);}return b;}
static uint32_t lb1(int c,int lo,int hi){return c<lo?(uint32_t)((lo-c)*(lo-c)):c>hi?(uint32_t)((c-hi)*(c-hi)):0u;}

static void gen(void) {
    for(uint32_t e=0;e<E;e++){for(uint32_t i=0;i<D;i++)C[e][i]=(int8_t)((int)(u32()%128u)-64);for(uint32_t i=0;i<D;i++)W[e][i]=(int8_t)((int)(u32()%63u)-31);Z[e]=(int16_t)((int)(u32()%4096u)-2048);}
    for(uint32_t b=0;b<B;b++){
        uint32_t d[E]; uint16_t id[E];
        for(uint32_t e=0;e<E;e++){uint32_t z=0;for(uint32_t i=0;i<4;i++){uint32_t s=2u*(3u-i),v=(b>>s)&3u,lo=(uint32_t)(LO+32*(int)v),hi=lo+31u;z+=lb1(C[e][i],(int)lo,(int)hi);}d[e]=z;id[e]=(uint16_t)e;}
        for(uint32_t i=0;i<K+1u;i++){uint32_t m=i;for(uint32_t j=i+1;j<E;j++)if(d[j]<d[m]||(d[j]==d[m]&&id[j]<id[m]))m=j;uint32_t td=d[i];d[i]=d[m];d[m]=td;uint16_t ti=id[i];id[i]=id[m];id[m]=ti;}
        for(uint32_t i=0;i<K;i++){T[b][i]=id[i];}
        L[b]=d[K];
    }
}
static R ref(const Q *q){R r={0,UINT_MAX,UINT16_MAX,E,1};for(uint16_t e=0;e<E;e++){uint32_t d=sd(q,e);if(bt(d,e,r.d,r.e)){r.d=d;r.e=e;}}r.y=ex(q,r.e);return r;}
static R run(const Q *q){int ok=0;uint16_t b=bk(q,&ok);uint8_t v[E];memset(v,0,sizeof v);R r={0,UINT_MAX,UINT16_MAX,K,0};for(uint32_t i=0;i<K;i++){uint16_t e=T[b][i];v[e]=1;uint32_t d=sd(q,e);if(bt(d,e,r.d,r.e)){r.d=d;r.e=e;}}r.cert=(uint8_t)(ok&&r.d<L[b]);if(!r.cert){r.n=K;for(uint16_t e=0;e<E;e++)if(!v[e]){r.n++;uint32_t d=sd(q,e);if(bt(d,e,r.d,r.e)){r.d=d;r.e=e;}}}r.y=ex(q,r.e);return r;}
static void one(const Q *q,M *m){uint64_t t=ns();R a=run(q);m->ns_c+=ns()-t;t=ns();R b=ref(q);m->ns_r+=ns()-t;m->q++;m->cert+=a.cert;m->eval+=a.n;m->sum^=((uint64_t)(uint32_t)a.y<<32)^((uint64_t)a.e<<16)^a.d;if(a.e!=b.e||a.d!=b.d||a.y!=b.y)m->bad++;assert(a.n<=E);}
static M familiar(uint32_t n){M m={0};for(uint32_t j=0;j<n;j++){uint16_t e=(uint16_t)(u32()%E);Q q;for(uint32_t i=0;i<D;i++)q.x[i]=sat((int)C[e][i]+(int)(u32()%11u)-5);one(&q,&m);}return m;}
static M uniform(uint32_t n){M m={0};for(uint32_t j=0;j<n;j++){Q q;for(uint32_t i=0;i<D;i++)q.x[i]=(int8_t)((int)(u32()%128u)-64);one(&q,&m);}return m;}
static void pm(const char*n,const M*m,int c){double cr=(double)m->cert/m->q,me=(double)m->eval/m->q,red=1.0-me/E;printf("    \"%s\":{\"queries\":%"PRIu64",\"mismatches\":%"PRIu64",\"certified_rate\":%.9f,\"mean_experts\":%.6f,\"reduction\":%.9f,\"candidate_ns\":%"PRIu64",\"reference_ns\":%"PRIu64",\"checksum\":\"%016"PRIx64"\"}%s\n",n,m->q,m->bad,cr,me,red,m->ns_c,m->ns_r,m->sum,c?",":"");}
int main(void){gen();Q z={{0}};R a=run(&z),b=ref(&z);assert(a.e==b.e&&a.d==b.d&&a.y==b.y);M f=familiar(100000u),u=uniform(25000u);double cr=(double)f.cert/f.q,me=(double)f.eval/f.q;int pass=!f.bad&&!u.bad&&cr>=.95&&me<=32.0;printf("{\n  \"schema\":\"ravel-capsule-evidence/0.1\",\n  \"experts\":256,\"route_width\":24,\n  \"workloads\":{\n");pm("familiar",&f,1);pm("uniform",&u,0);printf("  },\n  \"development_result\":\"%s\",\n  \"formal_mncs_status\":\"UNKNOWN\",\n  \"formal_mncds_status\":\"UNKNOWN\"\n}\n",pass?"PASS":"FAIL");return pass?0:1;}
