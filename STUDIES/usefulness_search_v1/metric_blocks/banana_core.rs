fn banana_physical(q:&[f64],latent:bool)->Vec<f64>{let mut x=q.to_vec();if latent{for j in (0..q.len()).step_by(2){x[j+1]+=5.*(q[j]*q[j]-1.);}}x}
fn banana_value(q:&[f64],g:&mut[f64],latent:bool)->f64{
 assert_eq!(q.len(),24);assert_eq!(g.len(),24);let mut lp=0.;
 for j in (0..24).step_by(2){let a=q[j];let b=if latent{q[j+1]}else{q[j+1]-5.*(a*a-1.)};lp-=0.5*(a*a+b*b);g[j]=if latent{-a}else{-a+10.*a*b};g[j+1]=-b;}lp
}
#[cfg(test)] mod banana_tests {
 use super::*;
 #[test] fn gradient_and_inverse(){for latent in [false,true]{for v in [-2.,0.3,2.]{let q:Vec<_>=(0..24).map(|i|v+i as f64/20.).collect();let mut g=vec![0.;24];banana_value(&q,&mut g,latent);for i in 0..24{let mut a=q.clone();let mut b=q.clone();a[i]+=1e-6;b[i]-=1e-6;let mut scratch=vec![0.;24];let fd=(banana_value(&a,&mut scratch,latent)-banana_value(&b,&mut scratch,latent))/2e-6;assert!((fd-g[i]).abs()<1e-5*(1.+g[i].abs()));}}}let z:Vec<_>=(0..24).map(|i|i as f64/20.).collect();let x=banana_physical(&z,true);let mut g=vec![0.;24];assert!((banana_value(&z,&mut g,true)-banana_value(&x,&mut g,false)).abs()<1e-12);}
 #[test] fn overflow_is_nonfinite(){let q=vec![1e200;24];let mut g=vec![0.;24];assert!(!banana_value(&q,&mut g,false).is_finite());}
}
