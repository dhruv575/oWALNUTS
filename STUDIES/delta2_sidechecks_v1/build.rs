use std::env;

fn main() {
    println!("cargo:rerun-if-env-changed=WP37A_HARNESS_COMMIT");
    println!("cargo:rerun-if-env-changed=WP37A_HARNESS_TREE");
    let commit = env::var("WP37A_HARNESS_COMMIT").unwrap_or_else(|_| "UNBOUND".into());
    let tree = env::var("WP37A_HARNESS_TREE").unwrap_or_else(|_| "UNBOUND".into());
    println!("cargo:rustc-env=WP37A_HARNESS_COMMIT={commit}");
    println!("cargo:rustc-env=WP37A_HARNESS_TREE={tree}");
}
