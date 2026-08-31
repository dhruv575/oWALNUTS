// Differential oracle generator for zero-density (failed-evaluation)
// semantics. Drives the unmodified upstream walnutpie::detail::macro_step on
// Neal's 10-D funnel with a hard wall: the target throws inside the wall and
// the upstream NoExceptLogpGrad wrapper (walnutpie/util.hpp) maps the failure
// to logp = -inf, grad = 0. Records the reference decision, endpoint state,
// adaptation statistic, total target calls, and the number of calls that
// landed inside the wall. Upstream commit
// f5bba36529697c34567a2944be36b68e305c546d (MIT).
// Build: g++ -std=c++20 -O2 -I<walnutpie>/include -I<eigen> generate_invalid_leaves.cpp
#include <cmath>
#include <cstdio>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include "walnutpie/walnuts.hpp"

namespace {

enum class Wall { NeckOmega, BodyX1 };

struct WallFunnel {
  mutable std::size_t calls = 0;
  int dim = 10;
  Wall wall = Wall::NeckOmega;
  double omega_wall = -7.0;
  double x1_wall = 0.8;
  bool inside(const Eigen::VectorXd& theta) const {
    return wall == Wall::NeckOmega ? theta[0] < omega_wall : theta[1] > x1_wall;
  }
  void operator()(const Eigen::VectorXd& theta, double& logp,
                  Eigen::VectorXd& grad) const {
    ++calls;
    if (inside(theta)) {
      throw std::runtime_error("outside support");
    }
    const double omega = theta[0];
    const double inv_var = std::exp(-omega);
    double sum_sq = 0.0;
    for (int i = 1; i < dim; ++i) sum_sq += theta[i] * theta[i];
    logp = -omega * omega / 18.0 - 0.5 * (dim - 1) * omega -
           0.5 * sum_sq * inv_var;
    grad.resize(dim);
    grad[0] = -omega / 9.0 - 0.5 * (dim - 1) + 0.5 * sum_sq * inv_var;
    for (int i = 1; i < dim; ++i) grad[i] = -theta[i] * inv_var;
  }
};

struct CountingHandler {
  std::size_t exceptions = 0;
  void on_logp_exception(const Eigen::VectorXd&, const std::exception&) noexcept {
    ++exceptions;
  }
};

struct RecordingAdapter {
  std::vector<double> values;
  void operator()(double v) { values.push_back(v); }
  double step_size() const { return 0.0; }
};

std::string vec_json(const Eigen::VectorXd& v) {
  std::string s = "[";
  char buf[64];
  for (int i = 0; i < v.size(); ++i) {
    std::snprintf(buf, sizeof buf, "%.17g", v[i]);
    s += buf;
    if (i + 1 < v.size()) s += ",";
  }
  return s + "]";
}

std::string num(double x) {
  char buf[64];
  std::snprintf(buf, sizeof buf, "%.17g", x);
  return buf;
}

}  // namespace

int main(int argc, char** argv) {
  const std::size_t n_cases = argc > 1 ? std::stoul(argv[1]) : 4000;
  const std::uint64_t seed = argc > 2 ? std::stoull(argv[2]) : 20260831ULL;
  std::mt19937_64 rng(seed);
  std::normal_distribution<double> normal(0.0, 1.0);
  std::bernoulli_distribution coin(0.5);
  WallFunnel funnel;
  CountingHandler handler;
  walnutpie::detail::NoExceptLogpGrad<WallFunnel, CountingHandler> wrapped(funnel, handler);
  const int dim = funnel.dim;
  Eigen::VectorXd inv_mass = Eigen::VectorXd::Ones(dim);

  std::printf("{\"schema\":\"walnutpie-invalid-macro-leaf-oracle-v1\",");
  std::printf("\"upstream_commit\":\"f5bba36529697c34567a2944be36b68e305c546d\",");
  std::printf("\"generator\":\"generate_invalid_leaves.cpp\",\"seed\":%llu,",
              (unsigned long long)seed);
  std::printf("\"target\":\"neal-funnel-10d with a hard wall; failed evaluations map to logp=-inf, grad=0 via NoExceptLogpGrad\",");
  std::printf("\"walls\":{\"neck_omega\":\"omega < -7\",\"body_x1\":\"x_1 > 0.8\"},");
  std::printf("\"cases\":[");
  for (std::size_t c = 0; c < n_cases; ++c) {
    // Alternate wall kinds so both boundary geometries are exercised.
    funnel.wall = (c % 2 == 0) ? Wall::NeckOmega : Wall::BodyX1;
    Eigen::VectorXd theta(dim), rho(dim), grad(dim);
    if (funnel.wall == Wall::NeckOmega) {
      std::uniform_real_distribution<double> omega_dist(-7.0, -3.0);
      theta[0] = omega_dist(rng);
      const double sd = std::exp(0.5 * theta[0]);
      for (int i = 1; i < dim; ++i) theta[i] = sd * normal(rng);
    } else {
      std::uniform_real_distribution<double> omega_dist(-2.0, 2.0);
      theta[0] = omega_dist(rng);
      const double sd = std::exp(0.5 * theta[0]);
      do {
        for (int i = 1; i < dim; ++i) theta[i] = sd * normal(rng);
      } while (funnel.inside(theta));
    }
    for (int i = 0; i < dim; ++i) rho[i] = normal(rng);
    // tuning families (same as the funnel oracle)
    double macro_step = 0.36, max_error = 0.21;
    std::size_t halvings = 10, min_micro = 1;
    const int family = static_cast<int>((c / 2) % 4);
    if (family == 1) { min_micro = 2; halvings = 8; max_error = 0.5; }
    if (family == 2) { macro_step = 0.6; max_error = 1.0; halvings = 6; }
    if (family == 3) { min_micro = 4; halvings = 5; max_error = 0.21; }
    const bool forward = coin(rng);
    double logp_pos;
    wrapped(theta, logp_pos, grad);
    const double logp_joint = logp_pos + walnutpie::detail::logp_momentum(rho, inv_mass);
    Eigen::VectorXd theta_copy = theta, rho_copy = rho, grad_copy = grad;
    auto span = walnutpie::detail::SpanW::from_initial_point(
        std::move(theta_copy), std::move(rho_copy), std::move(grad_copy), logp_pos, logp_joint);
    funnel.calls = 0;
    handler.exceptions = 0;
    RecordingAdapter adapter;
    Eigen::VectorXd theta_next, rho_next, grad_next;
    double logp_pos_next = -INFINITY, logp_next = -INFINITY;
    bool ok;
    if (forward) {
      ok = walnutpie::detail::macro_step<walnutpie::detail::Direction::Forward>(
          wrapped, inv_mass, macro_step, halvings, min_micro, max_error, span,
          theta_next, rho_next, grad_next, logp_pos_next, logp_next, adapter);
    } else {
      ok = walnutpie::detail::macro_step<walnutpie::detail::Direction::Backward>(
          wrapped, inv_mass, macro_step, halvings, min_micro, max_error, span,
          theta_next, rho_next, grad_next, logp_pos_next, logp_next, adapter);
    }
    if (c) std::printf(",");
    std::printf("{\"index\":%zu,\"direction\":\"%s\",\"wall\":\"%s\",", c,
                forward ? "forward" : "backward",
                funnel.wall == Wall::NeckOmega ? "neck_omega" : "body_x1");
    std::printf("\"input\":{\"theta\":%s,\"rho\":%s,\"macro_step\":%s,\"max_step_halvings\":%zu,\"min_micro_steps\":%zu,\"max_error\":%s},",
                vec_json(theta).c_str(), vec_json(rho).c_str(), num(macro_step).c_str(), halvings, min_micro, num(max_error).c_str());
    std::printf("\"accepted\":%s,\"target_evaluations\":%zu,\"zero_density_evaluations\":%zu,\"minimum_acceptance\":%s",
                ok ? "true" : "false", funnel.calls, handler.exceptions,
                adapter.values.empty() ? "null" : num(adapter.values[0]).c_str());
    if (ok) {
      std::printf(",\"theta\":%s,\"rho\":%s,\"gradient\":%s,\"logp_position\":%s,\"logp_joint\":%s",
                  vec_json(theta_next).c_str(), vec_json(rho_next).c_str(), vec_json(grad_next).c_str(),
                  num(logp_pos_next).c_str(), num(logp_next).c_str());
    }
    std::printf("}");
  }
  std::printf("]}\n");
  return 0;
}
