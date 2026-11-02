#include <Eigen/Dense>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <algorithm>
using Eigen::MatrixXd;using Eigen::VectorXd;
using RowMatrix=Eigen::Matrix<double,Eigen::Dynamic,Eigen::Dynamic,Eigen::RowMajor>;
struct GridContext {MatrixXd dx,dy,design;VectorXd counts;double exposure;int nx,ny,n;std::atomic<uint64_t>calls{0},errors{0};};
extern "C" {
void* grid_create(int nx,int ny,const double*x,const double*y,const double*d,const double*counts,double exposure){
 auto*c=new GridContext();c->nx=nx;c->ny=ny;c->n=nx*ny;c->exposure=exposure;
 c->dx.resize(nx,nx);c->dy.resize(ny,ny);
 for(int i=0;i<nx;i++)for(int j=0;j<nx;j++)c->dx(i,j)=(x[i]-x[j])*(x[i]-x[j]);
 for(int i=0;i<ny;i++)for(int j=0;j<ny;j++)c->dy(i,j)=(y[i]-y[j])*(y[i]-y[j]);
 c->design=Eigen::Map<const RowMatrix>(d,c->n,3);c->counts=Eigen::Map<const VectorXd>(counts,c->n);return c;
}
void grid_destroy(void*p){delete static_cast<GridContext*>(p);}
void grid_counts(void*p,uint64_t*out){auto*c=static_cast<GridContext*>(p);out[0]=c->calls;out[1]=c->errors;}
int grid_evaluate(uint64_t n,const double*q,double*g,double*lp,void*p){
 auto*c=static_cast<GridContext*>(p);c->calls++;
 auto fail=[&](){c->errors++;*lp=-INFINITY;std::fill(g,g+n,0.);return 1;};
 if(n!=static_cast<uint64_t>(c->n+5))return -1;
 double rho=std::exp(q[0]),alpha=std::exp(q[1]),rr=rho*rho,aa=alpha*alpha;
 if(!std::isfinite(rr+aa)||rr==0||aa==0)return fail();
 MatrixXd kx=(-.5*c->dx.array()/rr).exp(),ky=(-.5*c->dy.array()/rr).exp();
 Eigen::SelfAdjointEigenSolver<MatrixXd> ex(kx),ey(ky);
 if(ex.info()!=Eigen::Success||ey.info()!=Eigen::Success)return fail();
 const auto&ux=ex.eigenvectors();const auto&uy=ey.eigenvectors();const auto&lx=ex.eigenvalues();const auto&ly=ey.eigenvalues();
 MatrixXd product=aa*lx*ly.transpose(),lambda=product.array()+1e-10;
 if(lambda.minCoeff()<=0)return fail();
 MatrixXd root=lambda.array().sqrt();
 Eigen::Map<const RowMatrix> U(q+5,c->nx,c->ny);
 MatrixXd z=ux.transpose()*U*uy;
 RowMatrix field=ux*(root.array()*z.array()).matrix()*uy.transpose();
 VectorXd f=c->design*Eigen::Map<const VectorXd>(q+2,3)+Eigen::Map<const VectorXd>(field.data(),c->n);
 if(!f.allFinite()||f.maxCoeff()>700)return fail();
 VectorXd rates=c->exposure*f.array().exp(),a=c->counts-rates;
 Eigen::Map<const RowMatrix> A(a.data(),c->nx,c->ny);
 MatrixXd v=ux.transpose()*A*uy;
 RowMatrix latent=ux*(root.array()*v.array()).matrix()*uy.transpose();
 VectorXd beta=c->design.transpose()*a-Eigen::Map<const VectorXd>(q+2,3);
 for(int j=0;j<3;j++)g[j+2]=beta[j];
 for(int j=0;j<c->n;j++)g[j+5]=latent.data()[j]-q[j+5];
 MatrixXd bx=ux.transpose()*(kx.array()*c->dx.array()/rr).matrix()*ux;
 MatrixXd by=uy.transpose()*(ky.array()*c->dy.array()/rr).matrix()*uy;
 double gr=0,ga=0;
 for(int i=0;i<c->nx;i++)for(int j=0;j<c->ny;j++){
   double dz=0;
   for(int k=0;k<c->nx;k++)dz+=aa*bx(i,k)*ly[j]*z(k,j)/(root(i,j)+root(k,j));
   for(int k=0;k<c->ny;k++)dz+=aa*lx[i]*by(j,k)*z(i,k)/(root(i,j)+root(i,k));
   gr+=v(i,j)*dz;ga+=v(i,j)*product(i,j)/root(i,j)*z(i,j);
 }
 g[0]=gr+2-rho;g[1]=ga+1-aa/4;
 *lp=c->counts.dot(f.array().matrix())+c->counts.sum()*std::log(c->exposure)-rates.sum()+2*q[0]-rho+q[1]-aa/8-.5*Eigen::Map<const VectorXd>(q+2,c->n+3).squaredNorm();
 if(!std::isfinite(*lp)||!Eigen::Map<VectorXd>(g,n).allFinite())return fail();return 0;
}
int64_t grid_nuts(uint64_t n,const double*q,double*g,double*lp,void*p){return grid_evaluate(n,q,g,lp,*static_cast<void**>(p));}
int64_t grid_expand(uint64_t n,uint64_t m,const double*q,double*out,void*){if(n!=m)return -1;std::copy(q,q+n,out);return 0;}
}
