    def with_data(self, *, seed=None, **updates):
        if self.data is None:
            data = {}
        else:
            data = self.data.copy()

        data.update(updates)

        if data is not None:
            if find_spec("stanio") is None:
                raise ImportError(
                    "stanio is not installed in the current environment. "
                    "Please install it with something like "
                    "'pip install stanio' or 'pip install nutpie[stan]'."
                )

            import stanio

            data_json = stanio.dump_stan_json(data)
        else:
            data_json = None

        outer_kwargs = self._transform_adapt_args
        if outer_kwargs is None:
            outer_kwargs = {}

        def make_adapter(*args, **kwargs):
            from nutpie.transform_adapter import make_transform_adapter

            return make_transform_adapter(**outer_kwargs)(*args, **kwargs, logp_fn=None)

        coords = self._coords
        if coords is None:
            coords = {}
        coords = coords.copy()

        dims = self.dims
        if dims is None:
            dims = {}
        dims = dims.copy()
        dim_sizes = {name: len(dim) for name, dim in coords.items()}

        model = _lib.StanModel(
            self.library, dim_sizes, dims, coords, seed, data_json, make_adapter
        )
        coords = self._coords
        if coords is None:
            coords = {}
        else:
            coords = coords.copy()

        return CompiledStanModel(
            _coords=coords,
            data=data,
            code=self.code,
            library=self.library,
            dims=self.dims,
            model=model,
        )
