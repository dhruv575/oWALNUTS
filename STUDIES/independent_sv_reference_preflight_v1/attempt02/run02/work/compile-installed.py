def compile_stan_model(
    *,
    code: Optional[str] = None,
    filename: Optional[str] = None,
    extra_compile_args: Optional[list[str]] = None,
    extra_stanc_args: Optional[list[str]] = None,
    dims: Optional[dict[str, int]] = None,
    coords: Optional[dict[str, Any]] = None,
    model_name: Optional[str] = None,
    cleanup: bool = True,
) -> CompiledStanModel:
    if find_spec("bridgestan") is None:
        raise ImportError(
            "BridgeStan is not installed in the current environment. "
            "Please install it with something like "
            "'pip install bridgestan' or 'pip install nutpie[stan]'."
        )

    import bridgestan

    if dims is None:
        dims = {}
    if coords is None:
        coords = {}

    if code is not None and filename is not None:
        raise ValueError("Specify exactly one of `code` and `filename`")
    if code is None:
        if filename is None:
            raise ValueError("Either code or filename have to be specified")
        with Path(filename).open() as file:
            code = file.read()

    if model_name is None:
        model_name = "model"

    basedir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        model_path = (
            Path(basedir.name)
            .joinpath("name")
            .with_name(model_name)  # This verifies that it is a valid filename
            .with_suffix(".stan")
        )
        model_path.write_text(code)
        make_args = ["STAN_THREADS=true"]
        if extra_compile_args:
            make_args.extend(extra_compile_args)
        stanc_args = []
        if extra_stanc_args:
            stanc_args.extend(extra_stanc_args)
        so_path = bridgestan.compile_model(
            model_path, make_args=make_args, stanc_args=stanc_args
        )
        # Set necessary library loading paths
        bridgestan.compile.windows_dll_path_setup()
        library = _lib.StanLibrary(so_path)
    finally:
        try:
            if cleanup:
                basedir.cleanup()
        except Exception:  # noqa: BLE001
            pass

    return CompiledStanModel(
        code=code,
        library=library,
        dims=dims,
        _coords=coords,
        model_name=model_name,
        model=None,
        data=None,
    )
