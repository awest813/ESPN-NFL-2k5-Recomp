/* Diagnostic only: measure host wait precision; no timing pass/fail threshold.
 * The CS branch links the production Win32 compatibility implementation.
 * Run through tools/benchmark-web-waits.py. All reported times are milliseconds.
 */

#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <emscripten/emscripten.h>
#include <emscripten/threading.h>
#include "platform/xbox_winnt.h"
#include "platform/win32_compat.h"
#define N 200
static double elapsed[N];
static double now(void){return emscripten_get_now();}
static int cmp(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
static void report(const char *kind,int ms){
 double sum=0;for(int i=0;i<N;i++)sum+=elapsed[i];qsort(elapsed,N,sizeof(double),cmp);
 printf("WAITBENCH kind=%s request=%d count=%d min=%.4f median=%.4f p95=%.4f p99=%.4f max=%.4f mean=%.4f\n",kind,ms,N,elapsed[0],elapsed[N/2],elapsed[N*95/100],elapsed[N*99/100],elapsed[N-1],sum/N);
}
static CRITICAL_SECTION cs;
static CONDITION_VARIABLE cv;
static int ready,done;
static double signaled;
static void *signal_worker(void *unused){
 (void)unused;for(int i=0;i<N;i++){
  EnterCriticalSection(&cs);while(!ready)SleepConditionVariableCS(&cv,&cs,INFINITE);ready=0;LeaveCriticalSection(&cs);
  emscripten_thread_sleep(1);
  EnterCriticalSection(&cs);signaled=now();done=1;WakeAllConditionVariable(&cv);LeaveCriticalSection(&cs);
 }return NULL;
}
int main(void){
 InitializeCriticalSection(&cs);InitializeConditionVariable(&cv);
 pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
 pthread_cond_t real,mono;pthread_cond_init(&real,NULL);
 pthread_condattr_t attr;assert(!pthread_condattr_init(&attr));assert(!pthread_condattr_setclock(&attr,CLOCK_MONOTONIC));assert(!pthread_cond_init(&mono,&attr));pthread_condattr_destroy(&attr);
 for(int ms=1;ms<=5;ms+=(ms==1?1:3))for(int kind=0;kind<3;kind++){
  for(int i=0;i<N;i++){
   double begin;
   if(!kind){EnterCriticalSection(&cs);begin=now();assert(!SleepConditionVariableCS(&cv,&cs,ms));assert(GetLastError()==ERROR_TIMEOUT);elapsed[i]=now()-begin;LeaveCriticalSection(&cs);}
   else{pthread_mutex_lock(&mutex);struct timespec t;clock_gettime(kind==1?CLOCK_REALTIME:CLOCK_MONOTONIC,&t);t.tv_nsec+=ms*1000000;if(t.tv_nsec>=1000000000){t.tv_sec++;t.tv_nsec-=1000000000;}begin=now();assert(pthread_cond_timedwait(kind==1?&real:&mono,&mutex,&t)==ETIMEDOUT);elapsed[i]=now()-begin;pthread_mutex_unlock(&mutex);}
  }report(kind==0?"production-cs":kind==1?"raw-realtime":"raw-monotonic",ms);
 }
 pthread_t worker;assert(!pthread_create(&worker,NULL,signal_worker,NULL));
 for(int i=0;i<N;i++){
  EnterCriticalSection(&cs);ready=1;done=0;WakeAllConditionVariable(&cv);
  while(!done)assert(SleepConditionVariableCS(&cv,&cs,1000));
  elapsed[i]=now()-signaled;LeaveCriticalSection(&cs);
 }
 assert(!pthread_join(worker,NULL));report("production-signal-to-return",0);puts("WAITBENCH DONE");return 0;
}
