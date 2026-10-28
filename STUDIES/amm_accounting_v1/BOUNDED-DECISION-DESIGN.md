# Finite decision functionals: design requirements

Status: mathematical design preparation, not an admitted experiment or a
profitability result. The current scale prior obstructs unbounded return moments
even when the conditional Student-t model has finite first moments. Changing
the inferential target solely to obtain convenient economics is not justified.

A defensible candidate is the probability of a declared terminal wealth
shortfall, L=1{W_terminal < b*W_initial}, for a fixed horizon and a threshold b
chosen from a stated capital-preservation requirement before evaluation. This
loss lies in [0,1], so its posterior expectation exists whenever the predictive
law is proper. It does not estimate the magnitude of losses or expected profit.
Cash may minimize this loss; that outcome must remain an admissible result.

A second candidate is bounded relative performance against matched inventory:
U=tanh(log(W_policy/W_inventory)/c), with a positive, externally justified
scale c and strictly positive terminal wealth for both portfolios. Its
expectation lies in [-1,1]. The transformation is a preference specification,
not a numerical estimator for unbounded log utility. Its saturation can hide
catastrophic loss magnitude, which must be separately disclosed. No value of
b or c, horizon, or policy family is selected here from development outcomes.

Before either candidate is frozen:

- Specify feasible LP position sizes, entry/exit timing, gas and liquidation
  accounting, and how zero wealth or bankruptcy is represented. Do not silently
  discard failed executions or observations outside the utility domain.
- Supply a joint model for price, fee revenue and execution outcomes. A return
  forecast alone does not determine LP wealth with fees or protocol dilution.
- Include cash, matched initial token inventory and fixed LP controls with the
  same information, costs and feasible execution constraints.
- Separate the true model expectation from numerical approximation: posterior
  convergence, predictive integration error and policy selection error each
  require evidence. Boundedness does not make correlated draws independent.
- Freeze utility parameters and policy selection on development data; evaluate
  on untouched chronological observations, retaining serial dependence in
  uncertainty estimates and every declared failure in the denominator.
- Report realized quote-denominated net returns and downside separately from
  bounded decision value. A favorable utility contrast alone establishes
  neither positive expected dollar profit nor realized profitability.

The fee-free aligned constant-product LP remains pathwise dominated by matched
inventory under every increasing wealth utility, including this bounded
relative score. Any claimed practical benefit must therefore be explained by
identified fees, constraints or other modeled mechanisms and survive the
matched-inventory control. These design requirements do not admit a new
economic study until the accounting and identification gaps are resolved.
