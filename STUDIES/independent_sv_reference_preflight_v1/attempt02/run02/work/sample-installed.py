def sample(
    compiled_model: CompiledModel,
    *,
    draws: int | None = None,
    tune: int | None = None,
    chains: int | None = None,
    cores: int | None = None,
    seed: int | None = None,
    save_warmup: bool = True,
    progress_bar: bool = True,
    low_rank_modified_mass_matrix: bool = False,
    transform_adapt: bool = False,
    init_mean: np.ndarray | None = None,
    return_raw_trace: bool = False,
    blocking: bool = True,
    progress_template: str | None = None,
    progress_style: str | None = None,
    progress_rate: int = 100,
    zarr_store: _ZarrStoreType | None = None,
    **kwargs,
) -> arviz.InferenceData | _BackgroundSampler:
    """Sample the posterior distribution for a compiled model.

    Parameters
    ----------
    draws: int | None
        The number of draws after tuning in each chain.
    tune: int | None
        The number of tuning (warmup) draws in each chain.
    chains: int
        The number of chains to sample.
    cores: int
        The number of chains that should run in parallel.
    seed: int
        Seed for the randomness in sampling.
    num_try_init: int
        The number if initial positions for each chain to try.
        Fail if we can't find a valid initializion point after
        this many tries.
    save_warmup: bool
        Wether to save the tuning (warmup) statistics and
        posterior draws in the output dataset.
    store_divergences: bool
        If true, store the exact locations where diverging
        transitions happend in the sampler stats. This is currently
        experimental, as the implementation is very wastefull
        with memory, and a better interface will need breaking
        changes.
    progress_bar: bool
        If true, display the progress bar (default)
    init_mean: ndarray
        Initialize the chains using jittered values around this
        point on the transformed parameter space. Defaults to
        zeros.
    store_unconstrained: bool
        If True, store each draw in the unconstrained (transformed)
        space in the sample stats.
    store_gradient: bool
        If True, store the logp gradient of each draw in the unconstrained
        space in the sample stats.
    store_mass_matrix: bool
        If True, store the current mass matrix at each draw in
        the sample stats.
    target_accept: float between 0 and 1, default 0.8
        Adapt the step size of the integrator so that the average
        acceptance probability of the draws is `target_accept`.
        Larger values will decrease the step size of the integrator,
        which can help when sampling models with bad geometry.
    maxdepth: int, default=10
        The maximum depth of the tree for each draw. The maximum
        number of gradient evaluations for each draw will
        be 2 ^ maxdepth.
    return_raw_trace: bool, default=False
        Return the raw trace object (an apache arrow structure)
        instead of converting to arviz.
    use_grad_based_mass_matrix: bool, default=True
        Use a mass matrix estimate that is based on draw and gradient
        variance. Set to `False` to get mass matrix adaptation more
        similar to PyMC and Stan.
    progress_template: str
        This is only exposed for experimentation. upon template
        for the html progress representation.
    progress_style: str
        This is only exposed for experimentation. Common HTML
        for the progress bar (eg CSS).
    progress_rate: int, default=500
        Rate in ms at which the progress should be updated.
    low_rank_modified_mass_matrix: bool, default=False
        Allow adaptation to some posterior correlations using
        a low-rank updated mass matrix. This is *experimental*
        and details about this will probably change in the next
        release.
    mass_matrix_eigval_cutoff: float > 1, defaul=100
        Ignore eigenvalues between cutoff and 1/cutoff in the
        low-rank modified mass matrix estimate. Higher values
        lead to worse correclation fitting, but increase
        the performance of leapfrog steps.
    mass_matrix_gamma: float > 0, default=1e-5
        Regularisation parameter for the eigenvalues. Only
        applicable with low_rank_modified_mass_matrix=True.
    transform_adapt: bool, default=False
        Use the experimental transform adaptation algorithm
        during tuning.
    zarr_store: nutpie.zarr_store.*
        A store created using nutpie.zarr_store to store the samples
        in. If None (default), the samples will be stored in
        memory using an arrow table. This can be used to write
        the trace directly into a zarr store, for instance
        on disk or to S3 or GCS.
    **kwargs
        Pass additional arguments to nutpie._lib.PySamplerArgs

    Returns
    -------
    trace : arviz.InferenceData
        An ArviZ ``InferenceData`` object that contains the samples.
    """

    if low_rank_modified_mass_matrix and transform_adapt:
        raise ValueError(
            "Specify only one of `low_rank_modified_mass_matrix` and `transform_adapt`"
        )

    if low_rank_modified_mass_matrix:
        settings = _lib.PyNutsSettings.LowRank(seed)
    elif transform_adapt:
        settings = _lib.PyNutsSettings.Transform(seed)
    else:
        settings = _lib.PyNutsSettings.Diag(seed)

    if tune is not None:
        settings.num_tune = tune
    if draws is not None:
        settings.num_draws = draws
    if chains is not None:
        settings.num_chains = chains

    for name, val in kwargs.items():
        setattr(settings, name, val)

    if cores is None:
        try:
            # Only available in python>=3.13
            available = os.process_cpu_count()  # type: ignore
        except AttributeError:
            available = os.cpu_count()
        if chains is None:
            cores = available
        else:
            cores = min(chains, cast(int, available))

    if init_mean is None:
        init_mean = np.zeros(compiled_model.n_dim)

    sampler = _BackgroundSampler(
        compiled_model,
        settings,
        init_mean,
        cores,
        progress_bar=progress_bar,
        save_warmup=save_warmup,
        return_raw_trace=return_raw_trace,
        progress_template=progress_template,
        progress_style=progress_style,
        progress_rate=progress_rate,
        store=zarr_store,
    )

    if not blocking:
        return sampler

    try:
        result = sampler.wait()
    except KeyboardInterrupt:
        result = sampler.abort()
    except:
        sampler.cancel()
        raise

    return result
