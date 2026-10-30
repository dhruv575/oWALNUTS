#include <algorithm>
#include <cmath>
#include <cstdint>
#include <dlfcn.h>
#include <mutex>
#include <vector>

namespace {
constexpr int D=43,S=12,K=3;
using Eval=int(*)(uint64_t,const double*,double*,double*,void*);
struct Population {
 void* lib; Eval eval; void* subjects[S];
 double weight[S],dose[S],c0[S],times[96],logy[96],center[D],A[D*D];
 uint64_t calls=0,errors=0; std::mutex mutex;
 ~Population(){if(lib)dlclose(lib);}
};
const double prior_mu[K]={0.,std::log(.1),std::log(.5)};
const double prior_sd[K]={1.2,1.2,.7};
void transform(Population*p,const double*x,double*q){
 for(int i=0;i<D;i++){q[i]=p->center[i];for(int j=0;j<D;j++)q[i]+=p->A[i*D+j]*x[j];}
}
double prior(const double*q,double*g){
 double lp=0.;std::fill(g,g+D,0.);
 for(int j=0;j<K;j++){
  double z=(q[j]-prior_mu[j])/prior_sd[j],tau=std::exp(q[K+j]);
  lp-=.5*z*z;g[j]=-z/prior_sd[j];
  lp+=q[K+j]-.5*tau*tau/.25;g[K+j]=1.-tau*tau/.25;
 }
 for(int i=2*K;i<D-1;i++){lp-=.5*q[i]*q[i];g[i]=-q[i];}
 double z=(q[D-1]-std::log(.2))/.7;lp-=.5*z*z;g[D-1]=-z/.7;return lp;
}
double logadd(double a,double b){double m=std::max(a,b);return m+std::log(std::exp(a-m)+std::exp(b-m));}
// Stable Bateman curve and derivatives with respect to log(ka), log(ke), log(V).
// The expansion is in the dimensionless rate separation times time.
double logcurve_grad(double ka,double ke,double vol,double dose,double c0,double t,double* grad){
 double r=std::abs(ka-ke),d=r*t,logphi,h;
 if(d<1e-4){
  double d2=d*d;
  logphi=-d/2+d2/24-d2*d2/2880+d2*d2*d2/181440;
  h=t*(-.5+d/12-d*d2/720+d*d2*d2/30240);
 }else{
  logphi=std::log(-std::expm1(-d))-std::log(d);
  h=t*((d>700?0.:1./std::expm1(d))-1./d);
 }
 double lb=std::log(dose)-vol+std::log(ka)+std::log(t)-std::min(ka,ke)*t+logphi;
 double la=c0>0?std::log(c0)-ke*t:-INFINITY;
 double lc=logadd(la,lb),wb=std::exp(lb-lc),wa=c0>0?std::exp(la-lc):0.;
 if(grad){
  double ga=ka>=ke?1.+ka*h:1.-ka*(t+h);
  double ge=ka>=ke?-ke*(t+h):ke*h;
  grad[0]=wb*ga;grad[1]=wb*ge-wa*ke*t;grad[2]=-wb;
 }
 return lc;
}
double logcurve(double ka,double ke,double vol,double dose,double c0,double t){return logcurve_grad(ka,ke,vol,dose,c0,t,nullptr);}

}
extern "C" {
void* population_create(const char*path,void**subjects,const double*weight,const double*dose,const double*c0,const double*times,const double*logy,const double*center,const double*A){
 auto*p=new Population();p->lib=dlopen(path,RTLD_NOW|RTLD_LOCAL);
 if(!p->lib){delete p;return nullptr;}p->eval=reinterpret_cast<Eval>(dlsym(p->lib,"evaluate"));
 if(!p->eval){delete p;return nullptr;}
 std::copy(subjects,subjects+S,p->subjects);std::copy(weight,weight+S,p->weight);std::copy(dose,dose+S,p->dose);std::copy(c0,c0+S,p->c0);
 std::copy(times,times+96,p->times);std::copy(logy,logy+96,p->logy);std::copy(center,center+D,p->center);std::copy(A,A+D*D,p->A);return p;
}
void population_destroy(void*ptr){delete static_cast<Population*>(ptr);}
int population_evaluate(uint64_t dim,const double*x,double*outg,double*outlp,void*ptr){
 auto*p=static_cast<Population*>(ptr);if(!p||dim!=D)return -1;std::lock_guard<std::mutex> lock(p->mutex);p->calls++;
 double q[D],g[D];transform(p,x,q);double lp=prior(q,g);
 for(int s=0;s<S;s++){
  double v[4],vg[4],value;
  for(int j=0;j<K;j++)v[j]=q[j]+std::exp(q[K+j])*q[2*K+s*K+j];
  v[2]+=std::log(p->weight[s]);v[3]=q[D-1];
  value=0.;std::fill(vg,vg+4,0.);
  double sigma=std::exp(v[3]),ka=std::exp(v[0]),ke=std::exp(v[1]);
  for(int i=0;i<8;i++){
   int n=8*s+i;double cg[3];
   double mu=logcurve_grad(ka,ke,v[2],p->dose[s],p->c0[s],p->times[n],cg);
   double z=(p->logy[n]-mu)/sigma;
   value-=v[3]+.5*z*z;
   for(int j=0;j<3;j++)vg[j]+=z/sigma*cg[j];
   vg[3]+=z*z-1.;
  }
  lp+=value;
  for(int j=0;j<K;j++){double tau=std::exp(q[K+j]);g[j]+=vg[j];g[K+j]+=vg[j]*tau*q[2*K+s*K+j];g[2*K+s*K+j]+=vg[j]*tau;}
  g[D-1]+=vg[3];
 }
 bool valid=std::isfinite(lp);
 for(int j=0;j<D;j++){outg[j]=0.;for(int i=0;i<D;i++)outg[j]+=p->A[i*D+j]*g[i];valid=valid&&std::isfinite(outg[j]);}
 if(!valid){p->errors++;*outlp=-INFINITY;std::fill(outg,outg+D,0.);return 1;}*outlp=lp;return 0;
}
double population_walnuts(uint64_t d,const double*x,double*g,void*p){double lp;int s=population_evaluate(d,x,g,&lp,p);return s<0?NAN:lp;}
int64_t population_nuts(uint64_t d,const double*x,double*g,double*lp,void*p){return population_evaluate(d,x,g,lp,*static_cast<void**>(p));}
int64_t population_expand(uint64_t d,uint64_t n,const double*x,double*out,void*){if(d!=n)return -1;std::copy(x,x+d,out);return 0;}
double population_value(const double*x,void*ptr){
 auto*p=static_cast<Population*>(ptr);std::lock_guard<std::mutex> lock(p->mutex);p->calls++;
 double q[D],g[D];transform(p,x,q);double lp=prior(q,g),sigma=std::exp(q[D-1]);
 for(int s=0;s<S;s++){
  double v[K];for(int j=0;j<K;j++)v[j]=q[j]+std::exp(q[K+j])*q[2*K+s*K+j];v[2]+=std::log(p->weight[s]);
  for(int i=0;i<8;i++){int n=8*s+i;double mu=logcurve(std::exp(v[0]),std::exp(v[1]),v[2],p->dose[s],p->c0[s],p->times[n]);double z=(p->logy[n]-mu)/sigma;lp-=q[D-1]+.5*z*z;}
 }
 if(!std::isfinite(lp)){p->errors++;return -INFINITY;}return lp;
}
void population_counters(void*ptr,uint64_t*out){auto*p=static_cast<Population*>(ptr);out[0]=p->calls;out[1]=p->errors;}
void population_reset(void*ptr){auto*p=static_cast<Population*>(ptr);p->calls=p->errors=0;}
}
