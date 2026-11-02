# Native wrapper import repair

The first numerical preflight failed at import: Python selected grid_native.so
as an extension module instead of the same-name ctypes wrapper. No numerical
test or sampling ran. Rename the wrapper module to grid_backend.py and import
that explicit name. The C++ library and model are unchanged. Preserve the
original preflight log as grid-native-preflight-before-repair01.log.
