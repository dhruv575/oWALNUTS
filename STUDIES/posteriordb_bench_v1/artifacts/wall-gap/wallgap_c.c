/* Raw C timing of bs_log_density_gradient: no Rust, no wrapper.
   Build: gcc -O2 wallgap_c.c -o wallgap_c.exe
   Run:   wallgap_c.exe model.so data.json [calls]   (tbb.dll must be loadable) */
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <windows.h>
typedef struct bs_model bs_model;
typedef bs_model* (*construct_t)(const char*, unsigned int, char**);
typedef int (*unc_num_t)(const bs_model*);
typedef int (*ldg_t)(const bs_model*, bool, bool, const double*, double*, double*, char**);
static char* slurp(const char* p) {
    FILE* f = fopen(p, "rb");
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    char* b = (char*)malloc(n + 1);
    fread(b, 1, n, f);
    b[n] = 0;
    fclose(f);
    return b;
}
int main(int argc, char** argv) {
    if (argc < 3) { fprintf(stderr, "usage: wallgap_c model.so data.json [calls]\n"); return 2; }
    int calls = argc > 3 ? atoi(argv[3]) : 2000;
    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) { fprintf(stderr, "LoadLibrary failed %lu\n", GetLastError()); return 1; }
    construct_t construct = (construct_t)GetProcAddress(h, "bs_model_construct");
    unc_num_t unc_num = (unc_num_t)GetProcAddress(h, "bs_param_unc_num");
    ldg_t ldg = (ldg_t)GetProcAddress(h, "bs_log_density_gradient");
    char* err = NULL;
    char* data = slurp(argv[2]);
    bs_model* m = construct(data, 1, &err);
    if (!m) { fprintf(stderr, "construct failed: %s\n", err ? err : ""); return 1; }
    int d = unc_num(m);
    double* q = (double*)malloc(d * sizeof(double));
    double* g = (double*)malloc(d * sizeof(double));
    unsigned s = 7;
    for (int i = 0; i < d; i++) { s = s * 1103515245u + 12345u; q[i] = ((s >> 8) % 1000) / 1000.0 - 0.5; }
    double v;
    for (int i = 0; i < 200; i++) ldg(m, false, true, q, &v, g, &err);
    LARGE_INTEGER f, t0, t1;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&t0);
    for (int i = 0; i < calls; i++)
        if (ldg(m, false, true, q, &v, g, &err) != 0) { fprintf(stderr, "rc!=0\n"); return 1; }
    QueryPerformanceCounter(&t1);
    printf("{\"model\":\"%s\",\"dimension\":%d,\"calls\":%d,\"raw_c_us\":%.3f}\n", argv[1], d, calls,
           (double)(t1.QuadPart - t0.QuadPart) / f.QuadPart * 1e6 / calls);
    return 0;
}
