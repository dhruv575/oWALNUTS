#include "pendulum.cpp"
// Frozen, globally invertible triangular map; constant positive conditional scale.
static double coefficients[4]={0,0,0,0}, conditional_scale=1;
extern "C" {
void set_transport(const double*c,double s){std::copy(c,c+4,coefficients);conditional_scale=s;}
int transport_evaluate(uint64_t n,const double*t,double*g,double*v,void*p){
  double x=t[0],m=((coefficients[3]*x+coefficients[2])*x+coefficients[1])*x+coefficients[0];
  double dm=(3*coefficients[3]*x+2*coefficients[2])*x+coefficients[1];
  double u[2]={x,m+conditional_scale*t[1]},h[2];
  int status=evaluate(n,u,h,v,p);*v+=std::log(conditional_scale);
  g[0]=h[0]+dm*h[1];g[1]=conditional_scale*h[1];return status;
}
double transport_walnuts(uint64_t n,const double*x,double*g,void*p){double v;int s=transport_evaluate(n,x,g,&v,p);return s<0?NAN:v;}
int64_t transport_nuts(uint64_t n,const double*x,double*g,double*v,void*p){return transport_evaluate(n,x,g,v,*static_cast<void**>(p));}
double value_only(void*p,const double*x){
  auto*a=static_cast<Context*>(p);a->calls++;double q[2],s[2],v=0;
  const double lo[2]={-5,-2},width[2]={6,4},prior[2]={std::log(.2),std::log(2.)},sd[2]={.8,.5};
  for(int i=0;i<2;i++){
    s[i]=sigmoid(a->center[i]+a->A[2*i]*x[0]+a->A[2*i+1]*x[1]);
    if(s[i]<=0||s[i]>=1)return -INFINITY;
    q[i]=lo[i]+width[i]*s[i];
    v-=.5*std::pow((q[i]-prior[i])/sd[i],2);
    v+=std::log(width[i])+std::log(s[i])+std::log1p(-s[i]);
  }
  std::vector<double> prediction(a->n);
  if(predict(p,q,a->n,a->times.data(),prediction.data()))return -INFINITY;
  for(int i=0;i<a->n;i++)v-=.5*std::pow((a->observed[i]-prediction[i])/a->sigma,2);
  return std::isfinite(v)?v:-INFINITY;
}
}
