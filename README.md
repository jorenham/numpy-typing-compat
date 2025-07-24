# numpy-typing-compat

*NumPy version information that type-checkers understand*

[![release](https://img.shields.io/github/v/release/jorenham/numpy-typing-compat?style=flat-square&color=333)](https://github.com/jorenham/numpy-typing-compat/releases)
![typed](https://img.shields.io/pypi/types/numpy-typing-compat?style=flat-square&color=333)
![license](https://img.shields.io/github/license/jorenham/numpy-typing-compat?style=flat-square&color=333)
[![NumPy](https://img.shields.io/badge/NumPy-013243?logo=NumPy&style=flat-square&logoColor=4D77CF&color=333)](https://github.com/numpy/numpy)

## Overview

This package provides version-specific boolean constants that allow library authors to write
NumPy-version-dependent static type annotations. Similar to how you might use
`if sys.version_info >= (3, 12):` for Python version checks, `numpy-typing-compat` enables static
type-checkers to understand which NumPy version is being used and apply appropriate type annotations.

## Use Case

This package is particularly useful for libraries that need to support multiple NumPy versions, for
example because they follow [SPEC 0](https://scientific-python.org/specs/spec-0000/). However,
there may have been changes in NumPy that affect type annotations. For instance, the
`numpy.exceptions` module was introduced in NumPy 1.25, and contains the exceptions that were
previously in the global `numpy` namespace. In NumPy 2.0, these exceptions were removed from the
global namespace. So if you support `<1.25` and also `>=2.0`, you will need to conditionally import
these exceptions to ensure compatibility across versions.

```python
from numpy_typing_compat import NUMPY_GE_1_25

if NUMPY_GE_1_25:
    from numpy.exceptions import AxisError
else:
    from numpy import AxisError
```

Type checkers like mypy, pyright, and basedpyright understand these patterns and will apply the correct
type annotations based on the installed NumPy version.

## Installation

```bash
pip install numpy-typing-compat
```

The package automatically selects the appropriate version constants based on your installed NumPy
version. It does so by requiring a specific version of NumPy in its `pyproject.toml` file, so that
your package manager will install the correct version of `numpy-typing-compat` that matches the
NumPy version you have installed.

For example, if you have `numpy==2.1.3` pinned in your `pyproject.toml`, and you run
`uv add numpy-typing-compat`, it will install `numpy-typing-compat==2.1.*`. That specific version
has `NUMPY_GE_2_1 = True`, and `NUMPY_GE_2_2 = False` set.

Note that `numpy-typing-compat` does not import `numpy`, and instead relies on the package manager
to install the correct version of `numpy-typing-compat` that matches the installed NumPy version.

## Reference

The following boolean constants are available:

| Constant        | `True` when     |
| --------------- | --------------- |
| `NUMPY_GE_1_22` | `numpy >= 1.22` |
| `NUMPY_GE_1_25` | `numpy >= 1.25` |
| `NUMPY_GE_2_0`  | `numpy >= 2.0`  |
| `NUMPY_GE_2_1`  | `numpy >= 2.1`  |
| `NUMPY_GE_2_2`  | `numpy >= 2.2`  |
| `NUMPY_GE_2_3`  | `numpy >= 2.3`  |

Each constant is typed as `Literal[True]` or `Literal[False]` depending on your NumPy version,
allowing type checkers to perform accurate type narrowing.

## Examples

### `numpy.exceptions`

The `numpy.exceptions` module was introduced in NumPy 1.25, and since 2.0 the exceptions
were removed from the global `numpy` namespace. If you support both `<1.25` and `>=2.0`, you can
conditionally import exceptions like this:

```python
from numpy_typing_compat import NUMPY_GE_1_25

if NUMPY_GE_1_25:
    from numpy.exceptions import AxisError
else:
    from numpy import AxisError
```

### `numpy.long`

The `numpy.long` scalar type was introduced in NumPy 2.0. Before 2.0, it was named `numpy.int_`.

```python
import numpy as np
from numpy_typing_compat import NUMPY_GE_2_0

if NUMPY_GE_2_0:
    type Long = np.long
else:
    type Long = np.int_
```
