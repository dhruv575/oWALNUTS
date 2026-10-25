"""Stdlib provenance tests; no compiler or sampler execution."""
import importlib.util
import sys

import pytest

if sys.version_info < (3, 11):
    pytest.skip("attest_release.py needs tomllib (Python 3.11+)", allow_module_level=True)
from pathlib import Path

spec=importlib.util.spec_from_file_location('attest_release',Path(__file__).parents[1]/'attest_release.py')
attest=importlib.util.module_from_spec(spec);spec.loader.exec_module(attest)


def test_local_dependencies_optional_sources_and_adapter_are_bound(tmp_path):
    adapter=tmp_path/'integrations/python'; dependency=tmp_path/'optional'
    for directory in [adapter,dependency]:
        (directory/'src').mkdir(parents=True)
        (directory/'src/lib.rs').write_text('initial')
    (adapter/'Cargo.toml').write_text('[dependencies]\noptional={path="../../optional",optional=true}\n')
    (dependency/'Cargo.toml').write_text('[package]\nname="optional"\n')
    (adapter/'python').mkdir();(adapter/'python/adapter.py').write_text('initial')
    original=attest.snapshot(tmp_path)
    assert str(dependency/'src/lib.rs') in original
    assert str(adapter/'python/adapter.py') in original
    (dependency/'src/lib.rs').write_text('tampered')
    assert attest.snapshot(tmp_path)!=original


def test_new_source_file_is_detected(tmp_path):
    crate=tmp_path/'integrations/python';(crate/'src').mkdir(parents=True)
    (crate/'Cargo.toml').write_text('[package]\nname="adapter"\n')
    original=attest.snapshot(tmp_path)
    (crate/'src/new.rs').write_text('new')
    assert attest.snapshot(tmp_path)!=original
