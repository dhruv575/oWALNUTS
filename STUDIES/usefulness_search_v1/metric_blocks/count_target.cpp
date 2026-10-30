#include "bridgestan.h"
#include "original_path.h"
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <dlfcn.h>

static std::atomic<std::uint64_t> calls[4]{};
template<class F> static F original(const char* name) {
    static void* handle = dlopen(ORIGINAL_LIBRARY, RTLD_NOW | RTLD_LOCAL);
    if (!handle) std::abort();
    void* address = dlsym(handle, name);
    if (!address) std::abort();
    return reinterpret_cast<F>(address);
}
extern "C" std::uint64_t ow_target_calls(unsigned int kind) {
    if (kind >= 4) std::abort();
    return calls[kind].load(std::memory_order_relaxed);
}
extern "C" void ow_reset_target_calls() {
    for (auto& count : calls) count.store(0, std::memory_order_relaxed);
}
extern "C" int bs_log_density(const bs_model* m, bool p, bool j, const double* x,
                               double* value, char** error) {
    static auto fn = original<decltype(&bs_log_density)>("bs_log_density");
    calls[0].fetch_add(1, std::memory_order_relaxed);
    return fn(m,p,j,x,value,error);
}
extern "C" int bs_log_density_gradient(const bs_model* m, bool p, bool j,
                                        const double* x, double* value,
                                        double* gradient, char** error) {
    static auto fn = original<decltype(&bs_log_density_gradient)>("bs_log_density_gradient");
    calls[1].fetch_add(1, std::memory_order_relaxed);
    return fn(m,p,j,x,value,gradient,error);
}
extern "C" int bs_log_density_hessian(const bs_model* m, bool p, bool j,
                                       const double* x, double* value,
                                       double* gradient, double* hessian, char** error) {
    static auto fn = original<decltype(&bs_log_density_hessian)>("bs_log_density_hessian");
    calls[2].fetch_add(1, std::memory_order_relaxed);
    return fn(m,p,j,x,value,gradient,hessian,error);
}
extern "C" int bs_log_density_hessian_vector_product(const bs_model* m, bool p,
    bool j, const double* x, const double* vector, double* value, double* hvp,
    char** error) {
    static auto fn = original<decltype(&bs_log_density_hessian_vector_product)>("bs_log_density_hessian_vector_product");
    calls[3].fetch_add(1, std::memory_order_relaxed);
    return fn(m,p,j,x,vector,value,hvp,error);
}
