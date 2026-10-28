# Rolling candidate-target admission contract

Static synthetic agreement does not validate the rolling state transport.
Before sampling a changed window, verify this transformation independently.
Coordinates are mu, log_sigma, beta, z[0:T], u[0:T], not the older single
latent-block target's layout. Never use generic drop-front on this vector.

For a fixed-length one-cell shift, preserve the three hyperparameters. The
old stationary AR construction is a0=z0/sqrt(1-rho^2),
ai=rho*a(i-1)+zi, hi=mu+sigma*ai. The new initial innovation that preserves
the old h1 is z'0=rho*z0+sqrt(1-rho^2)*z1. Interior innovations are
z'i=z(i+1), i=1,...,T-2. Append z'(T-1)=0 as a deterministic initialization,
not a posterior draw. This should reproduce the shifted old volatility path
exactly before its appended state. Merely copying z1 into z'0 is wrong.

If overlapping price cells are byte-identical and use the same coordinate
origin, u'i=u(i+1) preserves their latent prices. Append u'(T-1)=0 (cell
midpoint). Changed widths, endpoints or coordinate origins require an explicit
physical-price transform; a copied logistic coordinate is insufficient.

Preserve copied-coordinate diagonal masses. The mixed initial innovation has
no exact diagonal-metric transport in general: cross-coordinate covariance
is discarded. Declare a fixed positive initialization for that mass and for
new coordinates, and retain per-chain step sizes as a warm initialization.
This is a heuristic metric, not an exact transformation of posterior draws.

The new initial log price is an explicit conditioning datum. Setting it to a
previous observed-cell midpoint defines a different approximation than
integrating the boundary latent price. Never silently replace it with each
chain's previous latent value, which would create chain-specific targets.
A first implementation test can keep a declared fixed initial datum for both
warm and cold routes; it cannot establish validity of a market rolling model.

Admission tests: reconstructed overlapping h and X paths, correct block
indices, finite positive masses, no input mutation, target snapshot ownership
after caller-array changes, and equality of density/gradient to a fresh target
at the remapped point. Then compare fixed-budget warm refreshes to independent
cold fits, preserving every update, failure and computational cost. Choosing
historical boundary semantics remains a separate model decision.
