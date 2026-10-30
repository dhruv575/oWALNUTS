#include <cstdint>
#include <cmath>
#include <vector>
#include <string>
#include <stdexcept>
#include <dlfcn.h>
#include <algorithm>
#include <mutex>
static std::mutex stan_mutex;
struct Ctx {
  void *lib=nullptr,*model=nullptr,*rng=nullptr;
  using Construct=void*(*)(const char*,unsigned,char**);
  using Destroy=void(*)(void*);
  using Grad=int(*)(const void*,bool,bool,const double*,double*,double*,char**);
  using Constrain=int(*)(const void*,bool,bool,const double*,double*,void*,char**);
  using Rng=void*(*)(unsigned,char**);
  using Free=void(*)(char*);
  Destroy destroy=nullptr,rdestroy=nullptr; Grad grad=nullptr; Constrain constrain=nullptr; Free release=nullptr;
  int dim=0,np=0; uint64_t calls=0,errors=0; std::string error;
  std::vector<double> center,A,q,g,expanded;
  ~Ctx(){if(rng&&rdestroy)rdestroy(rng);if(model&&destroy)destroy(model);if(lib)dlclose(lib);}
};
template<class T> T sym(void*lib,const char*name){auto p=dlsym(lib,name);if(!p)throw std::runtime_error(name);return reinterpret_cast<T>(p);}
extern "C" {
void* create(const char*path,const char*data,int dim,int np,const double*center,const double*A){
  Ctx*c=new Ctx();
  try {
    c->lib=dlopen(path,RTLD_NOW|RTLD_LOCAL);if(!c->lib)throw std::runtime_error(dlerror());
    c->destroy=sym<Ctx::Destroy>(c->lib,"bs_model_destruct");c->rdestroy=sym<Ctx::Destroy>(c->lib,"bs_rng_destruct");
    c->release=sym<Ctx::Free>(c->lib,"bs_free_error_msg");c->grad=sym<Ctx::Grad>(c->lib,"bs_log_density_gradient");
    c->constrain=sym<Ctx::Constrain>(c->lib,"bs_param_constrain");
    char*error=nullptr;c->model=sym<Ctx::Construct>(c->lib,"bs_model_construct")(data,1,&error);
    if(error){c->error=error;c->release(error);error=nullptr;}if(!c->model)throw std::runtime_error(c->error);
    c->rng=sym<Ctx::Rng>(c->lib,"bs_rng_construct")(1,&error);
    if(error){c->error=error;c->release(error);}if(!c->rng)throw std::runtime_error(c->error);
    int actual=sym<int(*)(const void*)>(c->lib,"bs_param_unc_num")(c->model);if(actual!=dim)throw std::runtime_error("Dimension mismatch");
    c->dim=dim;c->np=np;c->center.assign(center,center+dim);c->A.assign(A,A+dim*dim);c->q.resize(dim);c->g.resize(dim);c->expanded.resize(dim+np);
    return c;
  }catch(...){delete c;return nullptr;}
}
void destroy(void*p){delete static_cast<Ctx*>(p);}
const char* last_error(void*p){return static_cast<Ctx*>(p)->error.c_str();}
void counters(void*p,uint64_t*out){auto*c=static_cast<Ctx*>(p);out[0]=c->calls;out[1]=c->errors;}
void reset(void*p){auto*c=static_cast<Ctx*>(p);c->calls=c->errors=0;}
int evaluate(uint64_t dim,const double*x,double*g,double*lp,void*p){
  std::lock_guard<std::mutex> lock(stan_mutex);
  auto*c=static_cast<Ctx*>(p);if(!c||int(dim)!=c->dim)return -1;c->calls++;
  for(int i=0;i<c->dim;i++){c->q[i]=c->center[i];for(int j=0;j<c->dim;j++)c->q[i]+=c->A[i*c->dim+j]*x[j];}
  char*error=nullptr;int status=c->grad(c->model,true,true,c->q.data(),lp,c->g.data(),&error);
  if(error){c->error=error;c->release(error);}
  bool finite=status==0&&std::isfinite(*lp);
  for(int j=0;j<c->dim;j++){g[j]=0;for(int i=0;i<c->dim;i++)g[j]+=c->A[i*c->dim+j]*c->g[i];finite=finite&&std::isfinite(g[j]);}
  if(!finite){c->errors++;std::fill(g,g+dim,0.);*lp=-INFINITY;return 1;}return 0;
}
double walnuts(uint64_t dim,const double*x,double*g,void*p){double lp;int s=evaluate(dim,x,g,&lp,p);return s<0?NAN:lp;}
int64_t nuts(uint64_t dim,const double*x,double*g,double*lp,void*p){return evaluate(dim,x,g,lp,*static_cast<void**>(p));}
int64_t expand(uint64_t dim,uint64_t n,const double*q,double*out,void*){if(dim!=n)return -1;std::copy(q,q+dim,out);return 0;}
int predict(void*p,const double*q,double*out){
  std::lock_guard<std::mutex> lock(stan_mutex);
  auto*c=static_cast<Ctx*>(p);char*error=nullptr;
  int s=c->constrain(c->model,false,true,q,c->expanded.data(),c->rng,&error);
  if(error){c->error=error;c->release(error);}if(s!=0)return s;
  std::copy(c->expanded.begin()+c->dim,c->expanded.end(),out);return 0;
}
}
