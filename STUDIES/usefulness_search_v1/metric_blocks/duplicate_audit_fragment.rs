#[derive(Default)]
struct Audit {
    values: std::collections::HashMap<Vec<u64>, (Vec<u64>, u64)>,
    observed: u64, duplicates: u64, mismatches: u64, dropped: u64,
    nonfinite: u64, errors: u64, lag_bins: [u64; 6],
}
impl Audit {
    fn observe(&mut self, q: &[f64], lp: f64, g: &[f64]) {
        self.observed += 1;
        if !lp.is_finite() || q.iter().chain(g).any(|v| !v.is_finite()) {
            self.nonfinite += 1; return;
        }
        let key: Vec<_> = q.iter().map(|v|v.to_bits()).collect();
        let value: Vec<_> = std::iter::once(lp.to_bits()).chain(g.iter().map(|v|v.to_bits())).collect();
        if let Some((prior, last)) = self.values.get_mut(&key) {
            self.duplicates += 1;
            if *prior != value { self.mismatches += 1; }
            let lag = self.observed-*last;
            let bin = [1,4,16,64,256].iter().position(|&v|lag<=v).unwrap_or(5);
            self.lag_bins[bin] += 1; *last=self.observed;
        } else if self.values.len()<32768 {
            self.values.insert(key,(value,self.observed));
        } else { self.dropped += 1; }
    }
    fn summary(&self) -> Value {
        json!({"observed_successful_calls":self.observed,"error_calls":self.errors,
            "duplicate_successful_calls":self.duplicates,"output_bit_mismatches":self.mismatches,
            "stored_unique_positions":self.values.len(),"capacity_dropped_calls":self.dropped,
            "nonfinite_calls":self.nonfinite,"reuse_lag_bins_1_4_16_64_256_larger":self.lag_bins,
            "scope":"Observation only; first32768 unique finite positions per chain. Duplicates are a lower bound when capacity drops occur."})
    }
}
#[cfg(test)]
mod audit_tests {
    use super::*;
    #[test]
    fn exact_keys_output_mismatch_and_signed_zero() {
        let mut a=Audit::default();a.observe(&[0.0],1.0,&[2.0]);a.observe(&[0.0],1.0,&[2.0]);
        a.observe(&[-0.0],1.0,&[2.0]);a.observe(&[0.0],1.0,&[3.0]);
        assert_eq!(a.duplicates,2);assert_eq!(a.mismatches,1);assert_eq!(a.values.len(),2);
    }
    #[test]
    fn capacity_and_nonfinite_are_reported() {
        let mut a=Audit::default();for i in 0..32769 {a.observe(&[i as f64],0.0,&[0.0]);}
        a.observe(&[f64::NAN],0.0,&[0.0]);a.observe(&[0.0],0.0,&[0.0]);
        assert_eq!(a.values.len(),32768);assert_eq!(a.dropped,1);assert_eq!(a.nonfinite,1);assert_eq!(a.duplicates,1);
    }
}
