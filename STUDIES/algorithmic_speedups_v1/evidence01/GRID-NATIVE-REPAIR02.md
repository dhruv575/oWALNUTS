# Native wrapper constructor repair

The spatial environment has a newer nutpie constructor than the physics
environment and requires shared_var_keys. The repaired import reached that
constructor and failed before numerical evaluation. Supply an empty list for
this model with no shared variables. Preserve the prior log and wrapper;
no numerical code or inference setting changes.
