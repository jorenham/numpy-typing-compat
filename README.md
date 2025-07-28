# `numpy-typing-compat`

*NumPy version information that type-checkers understand*

[![release](https://img.shields.io/github/v/release/jorenham/numpy-typing-compat?style=flat-square&color=333)][RELEASES]
![typed](https://img.shields.io/pypi/types/numpy-typing-compat?style=flat-square&color=333)
![license](https://img.shields.io/github/license/jorenham/numpy-typing-compat?style=flat-square&color=333)
[![NumPy](https://img.shields.io/badge/NumPy-013243?logo=NumPy&style=flat-square&logoColor=4D77CF&color=333)][NP]

## Overview

This package provides version-specific boolean constants that allow library authors to
write NumPy-version-dependent static type annotations. Similar to how you might use
`if sys.version_info >= (3, 12):` for Python version checks, `numpy-typing-compat`
enables static type-checkers to understand which NumPy version is being used and apply
appropriate type annotations.

> [!TIP]
> `numpy-typing-compat` is intended as a helper package for the [`optype`][OP] library,
> which provides high-level typing utilities for annotating NumPy operations.
> In most situations, it is recommended to use `optype` instead of
> `numpy-typing-compat`. See the [`optype.numpy` documentation][ONP] for more details.

## Installation

Modern package managers such as [`uv`](https://github.com/astral-sh/uv) will
automatically install the appropriate version of `numpy-typing-compat` that matches your
installed NumPy version, in order to satisfy the `numpy` dependency restrictions of
`numpy-typing-compat`.

For example, the `numpy-typing-compat==2.1.*` distribution specifies `numpy>=2.1,<2.2`
as a required dependency. Modern package managers will ensure that these dependency
restrictions are satisfied. That way, if you upgrade `numpy` from `2.1` to `2.3`, e.g.
by running `uv sync --upgrade`, then `uv` will also automatically look for a version of
`numpy-typing-compat` that satisfies the new `numpy` version, which in this case
would be `numpy-typing-compat==2.3.*`.

> [!WARNING]
> Legacy package managers such as `pip` don't respect dependency restrictions.
> Running `pip install --upgrade numpy` will *not* automatically upgrade
> `numpy-typing-compat` to the correct version. If for some reason you need to use `pip`,
> then be sure to manually install the correct version of `numpy-typing-compat` that
> matches your installed NumPy version. Running `pip check` will tell you whether the
> installed `numpy-typing-compat` and `numpy` versions are compatible.

## Reference

### `array_api`

Additionally, the package provides a `numpy_typing_compat.array_api` namespace that's a
re-export of the `numpy.array_api` module on `numpy < 2.0`, or the main `numpy` module
on `numpy >= 2.0`. Note that the `numpy.array_api` module was introduced in
`numpy >= 1.23`, so it isn't available in `numpy-typing-compat==1.22.*`.

### `long` and `ulong`

NumPy 2.0 introduced the new `long` and `ulong` scalar types, which are not available in
`numpy < 2.0`, and instead went by the names `int_` and `uint` (which in `numpy >= 2.0`
are aliases for `intp` and `uintp`).
If you need to support both NumPy versions, you can use the `long` and `ulong` types
from `numpy_typing_compat`, which on `numpy < 2.0` are aliases for `np.int_` and
`np.uint`, and on `numpy >= 2.0` are re-exports of `np.long` and `np.ulong`.

### `StringDType`

In NumPy 2.0, the `numpy.dtypes.StringDType` was introduced, but it wasn't until
NumPy 2.1 that it was also available in the `numpy` stubs. The
`numpy_typing_compat.StringDType` is a re-export of `numpy.dtypes.StringDType` on
`numpy >= 2.1`, and an alias of `np.dtype[Never]` on `numpy < 2.1`. This allows type
checkers to also accept `StringDType` as a valid type on `numpy == 2.0.*`.

### `ABCPolyBase`

In NumPy 2.1, the `numpy.polynomial._polybase.ABCPolyBase` was made into a generic type,
and in NumPy 2.2 the type parameter was made optional. This can be problematic on
`numpy==2.1.*` if you also require support for `numpy < 2.1`.
To work around this, the `numpy_typing_compat.ABCPolyBase` is a type alias for
`numpy.polynomial._polybase.ABCPolyBase[LiteralString | None]` on `numpy==2.1.*`, and
a direct re-export of `numpy.polynomial._polybase.ABCPolyBase` otherwise. This way,
type checkers (when configured in strict mode) won't report an error on `numpy==2.1.*`
when using `ABCPolyBase`. Note that `numpy_typing_compat.ABCPolyBase` does not accept a
type parameter, even on `numpy >= 2.1`, for the sake of consistency.

### `LiteralTrue` and `LiteralFalse`

In NumPy 2.2, the `np.bool` scalar type became a generic type that accepts a type
parameter of either `True` or `False`. For compatibility with `numpy < 2.2`, the
`numpy_typing_compat.LiteralTrue` and `numpy_typing_compat.LiteralFalse` types are
provided. These are type aliases for `Literal[True]` and `Literal[False]` on
`numpy < 2.2`, and `Literal[True] | np.bool[Literal[True]]` and
`Literal[False] | np.bool[Literal[False]]` on `numpy >= 2.2`, respectively.

### Version constants

The following low-level boolean version constants are available:

| Constant        | `True` when     |
| --------------- | --------------- |
| `NUMPY_GE_1_22` | `numpy >= 1.22` |
| `NUMPY_GE_1_23` | `numpy >= 1.23` |
| `NUMPY_GE_1_25` | `numpy >= 1.25` |
| `NUMPY_GE_2_0`  | `numpy >= 2.0`  |
| `NUMPY_GE_2_1`  | `numpy >= 2.1`  |
| `NUMPY_GE_2_2`  | `numpy >= 2.2`  |
| `NUMPY_GE_2_3`  | `numpy >= 2.3`  |

Each constant is typed as `Literal[True]` or `Literal[False]` depending on your NumPy
version, so that static type-checkers are able to understand the NumPy version being
used.

> [!WARNING]
> At the moment, mypy and pyright only have limited support for `Literal` type conditions,
> and will not treat `if NUMPY_GE_2_0: ...` in the same way as
> `if sys.version_info >= (3, 12): ...` or `if sys.platform == "win32": ...`.

[RELEASES]: https://github.com/jorenham/numpy-typing-compat/releases
[NP]: https://github.com/numpy/numpy
[OP]: https://github.com/jorenham/optype
[ONP]: https://github.com/jorenham/optype#optypenumpy
