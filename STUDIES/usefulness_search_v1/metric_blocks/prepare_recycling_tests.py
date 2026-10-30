from pathlib import Path
study=Path(__file__).resolve().parent;p=study/'recycling_runner/src/main.rs'
source=p.read_text()
source+='''
#[cfg(test)]
mod recycling_tests {
    use owalnuts::recycling::merge;
    #[test]
    fn enumerated_selection_tree() {
        let old=merge(&[1.],&[3.],0.75_f64.ln());
        let new=merge(&[10.],&[20.],(1.0_f64/3.0).ln());
        for p in [0.75_f64,3.0/7.0,0.0,1.0] {
            let got=merge(&old,&new,p.ln())[0];let mut exact=0.;let mut total=0.;
            for mask in 0..8 {
                let bits=[mask&1!=0,mask&2!=0,mask&4!=0];let probs=[0.75,1.0/3.0,p];
                let probability=(0..3).map(|i|if bits[i]{probs[i]}else{1.-probs[i]}).product::<f64>();
                let selected=if bits[2]{if bits[1]{20.}else{10.}}else{if bits[0]{3.}else{1.}};
                total+=probability;exact+=probability*selected;
            }
            assert!((total-1.).abs()<1e-14);assert!((got-exact).abs()<1e-13);
        }
        assert!((merge(&old,&new,0.75_f64.ln())[0]-merge(&old,&new,(3.0_f64/7.0).ln())[0]).abs()>1.0);
        assert_eq!(merge(&[],&[],f64::NAN),Vec::<f64>::new());
        assert_eq!(merge(&[1.],&[2.],f64::NEG_INFINITY),vec![1.]);
        assert_eq!(merge(&[1.],&[2.],10.0),vec![2.]);
    }
}
'''
p.write_text(source)
