#include <array>
#include <atomic>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
using State=std::array<double,6>;
struct Context {
  double theta,sigma,step; bool linear; int n;
  std::vector<double> times,observed;
  double center[2],A[4];
  std::atomic<uint64_t> calls{0},errors{0};
};
static double sigmoid(double x) {return x>=0?1/(1+std::exp(-x)):std::exp(x)/(1+std::exp(x));}
static State rhs(const State &s,double c,double k,bool linear) {
  double a=linear?s[0]:std::sin(s[0]),b=linear?1:std::cos(s[0]);
  return {s[1],-c*s[1]-k*a,s[3],-c*s[3]-k*b*s[2]-c*s[1],
          s[5],-c*s[5]-k*b*s[4]-k*a};
}
static void advance(State &s,double h,double c,double k,bool linear) {
  auto a=rhs(s,c,k,linear);State v;
  for(int j=0;j<6;j++)v[j]=s[j]+h*.5*a[j];auto b=rhs(v,c,k,linear);
  for(int j=0;j<6;j++)v[j]=s[j]+h*.5*b[j];auto d=rhs(v,c,k,linear);
  for(int j=0;j<6;j++)v[j]=s[j]+h*d[j];auto e=rhs(v,c,k,linear);
  for(int j=0;j<6;j++)s[j]+=h*(a[j]+2*b[j]+2*d[j]+e[j])/6;
}
extern "C" {
void* create(double theta,double sigma,double step,int linear,int n,const double*t,const double*y,const double*center,const double*A) {
  auto*p=new Context();p->theta=theta;p->sigma=sigma;p->step=step;p->linear=linear;p->n=n;
  p->times.assign(t,t+n);p->observed.assign(y,y+n);std::copy(center,center+2,p->center);std::copy(A,A+4,p->A);return p;
}
void destroy(void*p){delete static_cast<Context*>(p);}
void reset(void*p){auto*c=static_cast<Context*>(p);c->calls=0;c->errors=0;}
void counters(void*p,uint64_t*out){auto*c=static_cast<Context*>(p);out[0]=c->calls;out[1]=c->errors;}
int evaluate(uint64_t dim,const double*x,double*g,double*lp,void*p) {
  auto*a=static_cast<Context*>(p);if(dim!=2)return -1;a->calls++;
  double z[2],s[2],q[2],dq[2],prior[2]={std::log(.2),std::log(2.)},sd[2]={.8,.5},lo[2]={-5,-2},width[2]={6,4};
  for(int i=0;i<2;i++){
    z[i]=a->center[i]+a->A[i*2]*x[0]+a->A[i*2+1]*x[1];s[i]=sigmoid(z[i]);q[i]=lo[i]+width[i]*s[i];dq[i]=width[i]*s[i]*(1-s[i]);
  }
  if(s[0]<=0||s[0]>=1||s[1]<=0||s[1]>=1){a->errors++;*lp=-INFINITY;g[0]=g[1]=0;return 1;}
  double c=std::exp(q[0]),k=std::exp(q[1]),v=0,grad[2]={0,0};
  State state={a->theta,0,0,0,0,0};double now=0;
  for(int i=0;i<a->n;i++){
    int steps=std::max(1,int(std::ceil((a->times[i]-now)/a->step)));double h=(a->times[i]-now)/steps;
    for(int j=0;j<steps;j++)advance(state,h,c,k,a->linear);
    now=a->times[i];double r=(a->observed[i]-state[0])/(a->sigma*a->sigma);
    v-=.5*(a->observed[i]-state[0])*r;grad[0]+=r*state[2];grad[1]+=r*state[4];
  }
  for(int i=0;i<2;i++){
    v-=.5*std::pow((q[i]-prior[i])/sd[i],2);
    v+=std::log(width[i])+std::log(s[i])+std::log1p(-s[i]);
    grad[i]=(grad[i]-(q[i]-prior[i])/(sd[i]*sd[i]))*dq[i]+1-2*s[i];
  }
  *lp=v;for(int j=0;j<2;j++)g[j]=a->A[j]*grad[0]+a->A[2+j]*grad[1];
  if(!std::isfinite(v)||!std::isfinite(g[0])||!std::isfinite(g[1])){a->errors++;*lp=-INFINITY;g[0]=g[1]=0;return 1;}return 0;
}
double walnuts(uint64_t n,const double*x,double*g,void*p){double v;int s=evaluate(n,x,g,&v,p);return s<0?NAN:v;}
int64_t nuts(uint64_t n,const double*x,double*g,double*v,void*p){return evaluate(n,x,g,v,*static_cast<void**>(p));}
int64_t expand(uint64_t n,uint64_t m,const double*q,double*out,void*){if(n!=m)return -1;std::copy(q,q+n,out);return 0;}
int predict(void*p,const double*q,int n,const double*t,double*out){
  auto*a=static_cast<Context*>(p);double c=std::exp(q[0]),k=std::exp(q[1]),now=0;
  State s={a->theta,0,0,0,0,0};
  for(int i=0;i<n;i++){
    int steps=std::max(1,int(std::ceil((t[i]-now)/a->step)));double h=(t[i]-now)/steps;
    for(int j=0;j<steps;j++)advance(s,h,c,k,a->linear);now=t[i];out[i]=s[0];
    if(!std::isfinite(out[i]))return 1;
  }return 0;
}
}
