#include <vector>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <algorithm>
struct Context{int J;std::vector<double>n,y;std::vector<int>center;std::atomic<uint64_t>calls{0},errors{0};};
static double sigmoid(double x){return x>=0?1/(1+std::exp(-x)):std::exp(x)/(1+std::exp(x));}
extern "C" {
void* create(int J,const double*n,const double*y,int space){auto*c=new Context();c->J=J;c->n.assign(n,n+J);c->y.assign(y,y+J);for(int j=0;j<J;j++)c->center.push_back(space==0||(space==2&&n[j]>=1000));return c;}
void destroy(void*p){delete static_cast<Context*>(p);}
void counters(void*p,uint64_t*out){auto*c=static_cast<Context*>(p);out[0]=c->calls;out[1]=c->errors;}
int evaluate(uint64_t dim,const double*q,double*g,double*lp,void*p){
 auto*c=static_cast<Context*>(p);c->calls++;if(dim!=static_cast<uint64_t>(c->J+2))return -1;
 double mu=q[0],h=q[1],tau=std::exp(h),t2=tau*tau;
 auto fail=[&](){c->errors++;*lp=-INFINITY;std::fill(g,g+dim,0.);return 1;};
 if(!std::isfinite(t2)||t2==0)return fail();
 double v=-mu*mu/8+h-t2/2;g[0]=-mu/4;g[1]=1-t2;
 for(int j=0;j<c->J;j++){
  double theta=c->center[j]?q[j+2]:mu+tau*q[j+2],z=(theta-mu)/tau;
  double a=c->y[j]-c->n[j]*sigmoid(theta);
  v+=c->y[j]*theta-c->n[j]*(std::max(theta,0.)+std::log1p(std::exp(-std::abs(theta))));
  if(c->center[j]){v-=.5*z*z+h;g[j+2]=a-z/tau;g[0]+=z/tau;g[1]+=z*z-1;}
  else{v-=.5*q[j+2]*q[j+2];g[j+2]=tau*a-q[j+2];g[0]+=a;g[1]+=a*tau*q[j+2];}
 }
 *lp=v;if(!std::isfinite(v))return fail();for(uint64_t j=0;j<dim;j++)if(!std::isfinite(g[j]))return fail();return 0;
}
double walnuts(uint64_t n,const double*q,double*g,void*p){double lp;int s=evaluate(n,q,g,&lp,p);return s<0?NAN:lp;}
int64_t nuts(uint64_t n,const double*q,double*g,double*lp,void*p){return evaluate(n,q,g,lp,*static_cast<void**>(p));}
int64_t expand(uint64_t n,uint64_t m,const double*q,double*out,void*){if(n!=m)return -1;std::copy(q,q+n,out);return 0;}
}
