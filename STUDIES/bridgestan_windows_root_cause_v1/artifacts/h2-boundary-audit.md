# H2 — FFI allocator-boundary audit (static)

Audited `integrations/bridgestan/src/lib.rs` at the WP50 base commit. Every
pointer that crosses the BridgeStan DLL boundary, who allocates it, and who
frees it:

| call | pointer | allocated by | freed by | verdict |
|---|---|---|---|---|
| `bs_model_construct(data, seed, &mut err)` | `data` (`*const c_char`) | Rust (`CString data_c`) | Rust (drops after call) | read-only into DLL; never freed by DLL — OK |
| same | `err` out-param | DLL CRT (on error) | `bs_free_error_msg(err)` = DLL CRT `free` (`take_error`) | alloc and free both in DLL — OK |
| `bs_model_info(ptr)` | return `*const c_char` | DLL (model-owned static) | nobody (copied via `to_string_lossy`) | header: "should not be freed" — OK |
| `bs_param_unc_names` / `bs_param_names(ptr,..)` | return `*const c_char` | DLL (model-owned) | nobody (copied, split) | model-owned — OK |
| `bs_param_unc_num` / `bs_param_num` | returns `int` | — | — | no pointer |
| `bs_log_density_gradient(ptr,.., pos, &mut value, grad, &mut err)` | `pos` | Rust | Rust | read-only into DLL — OK |
| same | `value`, `grad` | Rust (caller buffers) | Rust | DLL writes into caller buffers, never frees — OK |
| same | `err` | DLL CRT (on exception) | `bs_free_error_msg` = DLL CRT `free` | OK |
| `bs_param_constrain(ptr,.., pos, constrained, null_rng, &mut err)` | `constrained` | Rust | Rust | DLL writes into caller buffer — OK |
| same | `rng` | passed `null` (`include_gq=false`) | — | OK |
| same | `err` | DLL CRT | `bs_free_error_msg` | OK |
| `bs_model_destruct(ptr)` | `ptr` | DLL (`bs_model_construct`) | DLL (`bs_model_destruct`) | alloc and free both in DLL — OK |

`bs_free_error_msg` in `bridgestan.cpp` is literally `free(error_msg)`, i.e.
the DLL's own CRT `free`; the error string was allocated inside the DLL
(`strdup`/`new`), so this is same-allocator alloc+free. The Rust side never
calls its own allocator on any DLL-produced pointer, and the DLL never frees a
Rust-produced pointer (all Rust buffers are caller-owned read or write
scratch). `take_error` copies the C string into an owned Rust `String` before
calling the DLL's free, so there is no double-free and no cross-allocator free.

**Verdict: H2 NOT SUPPORTED.** There is no allocator mismatch across the
boundary. Every DLL-allocated object (error strings, the model) is released by
the DLL's own deallocator; every Rust-allocated buffer is released by Rust.
This cannot be the source of `STATUS_HEAP_CORRUPTION`.
