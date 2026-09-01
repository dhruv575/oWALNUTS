# oWALNUTS benchmark box image: pinned toolchains for reproducible wall-time
# measurements on a dedicated machine (see bench/README.md).
FROM rust:1.88-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev python3-pip \
        g++ make git util-linux ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Exact Python stack used by the v1/v2 flagship studies.
RUN python3.11 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
        "numpy<2.3" "arviz==0.23.4" "pymc==5.28.5" "nutpie==0.16.8" \
        "numpyro==0.21.0" "numba" "maturin>=1.7,<2" \
        "pytest"
ENV PATH="/opt/venv/bin:${PATH}" VIRTUAL_ENV=/opt/venv

WORKDIR /work
COPY run_bench.sh /usr/local/bin/run_bench.sh
RUN chmod +x /usr/local/bin/run_bench.sh
ENTRYPOINT ["/usr/local/bin/run_bench.sh"]
