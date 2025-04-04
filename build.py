# pyright: reportAny=false, reportExplicitAny=false

import string
from pathlib import Path

BUILD = 0

PROJECT_NAME = "numpy-typing-compat"
PROJECTS_DIR = Path(__file__).parent / "generated"

NUMPY_VERSIONS = {
    (1, 23): (3, 9),  # ignore 3.8
    (1, 24): (3, 9),  # ignore 3.8
    (1, 25): (3, 9),
    (1, 26): (3, 9),
    (2, 0): (3, 9),
    (2, 1): (3, 10),
    (2, 2): (3, 10),
    (2, 3): (3, 11),
}
NUMPY_NEXT = 2, 3  # unreleased version

PYPROJECT_TEMPLATE = string.Template(
    """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "numpy-typing-compat"
version = "$version"
description = "NumPy version information that type-checkers understand"
authors = [{name = "Joren Hammudoglu", email = "jhammudoglu@gmail.com"}]
license = "BSD-3-Clause"
keywords = ["numpy", "typing"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: BSD License",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Typing :: Typed",
]
requires-python = ">=$py_req"
dependencies = []

[project.urls]
Repository = "https://github.com/jorenham/numpy-typing-compat/"
Issues = "https://github.com/jorenham/numpy-typing-compat/issues"
Changelog = "https://github.com/jorenham/numpy-typing-compat/releases"

[project.optional-dependencies]
$np_dep""".lstrip()
)

INIT_TEMPLATE = string.Template(
    """
from typing import Final, Literal as L

__all__ = ["NP", "NP_1_25", "NP_2", "NP_2_1", "NP_2_2", "NP_2_3"]

# numpy available
NP: Final[L[$np]] = $np

# numpy >= 1.25
NP_1_25: Final[L[$np125]] = $np125

# numpy >= 2
NP_2: Final[L[$np2]] = $np2

# numpy >= 2.1
NP_2_1: Final[L[$np21]] = $np21

# numpy >= 2.2
NP_2_2: Final[L[$np22]] = $np22

# numpy >= 2.3
NP_2_3: Final[L[$np23]] = $np23
""".lstrip()
)


def _v(version: tuple[int, int], sep: str = ".") -> str:
    return f"{version[0]}{sep}{version[1]}"


def _generate_pyproject(
    np_start: tuple[int, int],
    np_stop: tuple[int, int],
    py_start: int,
) -> str:
    # TODO: python version classifiers
    if np_start == np_stop:
        np_dep = ""
    else:
        np_dep = f'numpy = ["numpy>={_v(np_start)},<={_v(np_stop)}"]\n'
    return PYPROJECT_TEMPLATE.substitute(
        version=f"{_v(np_start)}.{BUILD}",
        py_req=_v((3, py_start)),
        np_dep=np_dep,
    )


def _generate_init(
    np_start: tuple[int, int],
) -> str:
    return INIT_TEMPLATE.substitute(
        np=np_start > (0, 0),
        np125=np_start >= (1, 25),
        np2=np_start >= (2, 0),
        np21=np_start >= (2, 1),
        np22=np_start >= (2, 2),
        np23=np_start >= (2, 3),
    )


def _create_project(
    np_start: tuple[int, int],
    np_stop: tuple[int, int],
    py_start: int,
) -> None:
    # project directory
    project_key = "default" if np_start == np_stop else f"np{_v(np_start, '')}"
    project_dir = PROJECTS_DIR / project_key
    project_dir.mkdir(parents=True, exist_ok=True)

    # pyproject.toml
    pyproject_path = project_dir / "pyproject.toml"
    _ = pyproject_path.write_text(_generate_pyproject(np_start, np_stop, py_start))

    # package directory
    package_dir = project_dir / PROJECT_NAME.replace("-", "_")
    package_dir.mkdir(parents=True, exist_ok=True)

    # __init__.py
    init_file = package_dir / "__init__.py"
    _ = init_file.write_text(_generate_init(np_start))

    # py.typed
    py_typed_path = package_dir / "py.typed"
    _ = py_typed_path.write_text("")


def main() -> None:
    _create_project((0, 0), (0, 0), 9)
    _create_project((1, 22), (1, 25), 9)
    _create_project((1, 25), (2, 0), 9)
    _create_project((2, 0), (2, 1), 9)
    _create_project((2, 1), (2, 2), 10)
    _create_project((2, 2), (2, 3), 10)
    # _create_project((2, 3), (2, 4), (3, 11), True)


if __name__ == "__main__":
    main()
