# /// script
# requires-python = ">=3.12"
# dependencies = ["uv"]
# ///

import datetime as dt
import hashlib
import re
import shutil
import string
import subprocess
import sys
from pathlib import Path
from typing import Final, final

NAME = "numpy-typing-compat"

PYPROJECT_TEMPLATE = """
[build-system]
requires = ["uv_build"]
build-backend = "uv_build"

[project]
name = "numpy-typing-compat"
version = "$version"
description = "NumPy version information that type-checkers understand"
authors = [{name = "Joren Hammudoglu", email = "jhammudoglu@gmail.com"}]
license = "BSD-3-Clause"
license-files = ["LICENSE"]
keywords = ["numpy", "typing", "compatibility"]
classifiers = [
  "Development Status :: 5 - Production/Stable",
  "Intended Audience :: Developers",
  "Operating System :: OS Independent",
  "Programming Language :: Python",
  "Programming Language :: Python :: 3",
$py_classifiers
  "Typing :: Typed",
]
requires-python = "$py_req"
dependencies = ["numpy $np_req"]

[project.urls]
Repository = "https://github.com/jorenham/numpy-typing-compat/"
Issues = "https://github.com/jorenham/numpy-typing-compat/issues"
Changelog = "https://github.com/jorenham/numpy-typing-compat/releases"
""".lstrip()

# TODO(jorenham): Dynamically generate from the `VERSION_SPEC`
INIT_TEMPLATE = """
from typing import Final, Literal

__all__ = (
    "NUMPY_GE_1_22",
    "NUMPY_GE_1_25",
    "NUMPY_GE_2_0",
    "NUMPY_GE_2_1",
    "NUMPY_GE_2_2",
    "NUMPY_GE_2_3",
)

def __dir__() -> tuple[str, ...]:
    return __all__


NUMPY_GE_1_22: Final[Literal[$ge122]] = $ge122  # numpy >= 1.22
NUMPY_GE_1_25: Final[Literal[$ge125]] = $ge125  # numpy >= 1.25
NUMPY_GE_2_0: Final[Literal[$ge20]] = $ge20  # numpy >= 2.0
NUMPY_GE_2_1: Final[Literal[$ge21]] = $ge21  # numpy >= 2.1
NUMPY_GE_2_2: Final[Literal[$ge22]] = $ge22  # numpy >= 2.2
NUMPY_GE_2_3: Final[Literal[$ge23]] = $ge23  # numpy >= 2.3
""".lstrip()

DIR_ROOT = Path(__file__).parent
DIR_DIST = DIR_ROOT / "dist"
DIR_PROJECTS = DIR_ROOT / "projects"

DEBUG = True

type Version = tuple[int, int]
type VersionRange = tuple[Version, Version]


def _format_version(version: Version, /, sep: str = ".") -> str:
    return f"{version[0]}{sep}{version[1]}"


def _get_build_number() -> int:
    """Get the build number as YYYYMMDD."""
    today = dt.date.today()
    return today.year * 10_000 + today.month * 100 + today.day


def _sha256(file: Path, /) -> str:
    """Calculate the SHA256 hash of a file."""
    if not file.exists():
        raise FileNotFoundError(str(file))
    if not file.is_file():
        raise NotImplementedError("only files are supported")

    sha256 = hashlib.sha256()
    sha256.update(file.read_bytes())
    return sha256.hexdigest()


@final
class Project:
    np_range: Final[VersionRange]
    py_range: Final[VersionRange]

    def __init__(self, /, np_range: VersionRange, py_range: VersionRange) -> None:
        self.np_range = np_range
        self.py_range = py_range

    @property
    def version(self, /) -> str:
        return f"{_format_version(self.np_range[0])}.{BUILD}"

    @property
    def distname(self, /) -> str:
        return f"{NAME.replace('-', '_')}-{self.version}"

    @property
    def path_project(self, /) -> Path:
        return DIR_PROJECTS / self.distname

    @property
    def path_wheel(self, /) -> Path:
        return DIR_DIST / f"{self.distname}-py3-none-any.whl"

    @property
    def path_sdist(self, /) -> Path:
        return DIR_DIST / f"{self.distname}.tar.gz"

    def __str__(self, /) -> str:
        return self.distname

    def __repr__(self, /) -> str:
        clsname = type(self).__name__
        return f"<{clsname} np_range={self.np_range} py_range={self.py_range}>"

    def __fspath__(self, /) -> str:
        return str(self.path_project)

    def __generate_py_classifiers(self, /) -> str:
        py_start, py_stop = self.py_range
        assert py_start[0] == py_stop[0] == 3
        assert 4 <= py_start[1] < py_stop[1]

        return "\n".join(
            f'  "Programming Language :: Python :: 3.{minor}",'
            for minor in range(py_start[1], py_stop[1])
        )

    def _generate_pyproject(self, /) -> str:
        np_start, np_stop = self.np_range
        return string.Template(PYPROJECT_TEMPLATE).substitute(
            version=f"{_format_version(np_start)}.{BUILD}",
            np_req=f">={_format_version(np_start)}, <{_format_version(np_stop)}",
            py_req=f">={_format_version(self.py_range[0])}",
            py_classifiers=self.__generate_py_classifiers(),
        )

    def _generate_init(self, /) -> str:
        context: dict[str, bool] = {}
        for other in PROJECTS:
            other_np_range = other.np_range[0]
            name = f"ge{other_np_range[0]}{other_np_range[1]}"
            context[name] = self.np_range[0] >= other_np_range

        return string.Template(INIT_TEMPLATE).substitute(**context)

    def _generate(self, /) -> Path:
        project_dir = self.path_project
        project_dir.mkdir(parents=True, exist_ok=True)

        for fname in ("LICENSE", "README.md"):
            shutil.copy2(str(DIR_ROOT / fname), str(project_dir / fname))

        # pyproject.toml
        pyproject_path = project_dir / "pyproject.toml"
        _ = pyproject_path.write_text(self._generate_pyproject())

        # src/numpy_typing_compat/
        module_dir = project_dir / "src" / NAME.replace("-", "_")
        module_dir.mkdir(parents=True, exist_ok=True)

        # src/numpy_typing_compat/__init__.py
        init_file = module_dir / "__init__.py"
        _ = init_file.write_text(self._generate_init())

        # src/numpy_typing_compat/py.typed
        py_typed_path = module_dir / "py.typed"
        _ = py_typed_path.write_text("")

        return project_dir

    def build(self, /) -> bool:
        """Build the sdist and wheel and return True if not already built."""
        self._generate()

        checksum_pre = _sha256(self.path_sdist) if self.path_sdist.exists() else None

        completed = subprocess.run(
            [
                "uv",
                "build",
                "--color=never",
                "--no-progress",
                f"--directory={self.path_project}",
                f"--out-dir={DIR_DIST}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        completed.check_returncode()

        if DEBUG:
            for line in completed.stderr.strip().splitlines():
                print("[uv]", line, file=sys.stderr)

        paths: list[Path] = []
        for match in re.finditer(r"Successfully built (/[\w\-\./]+)", completed.stderr):
            out_path = Path(match.group(1))
            assert out_path.is_file()
            paths.append(out_path)

        if not paths:
            exc = RuntimeError("No files were built, check the output of `uv build`.")
            for line in completed.stderr.splitlines():
                exc.add_note(line)
            raise exc

        assert len(paths) == 2, paths

        path_wheel, path_sdist = paths
        if path_wheel.suffix != ".whl":
            path_wheel, path_sdist = path_sdist, path_wheel

        assert path_wheel == self.path_wheel, (path_wheel, self.path_wheel)
        assert path_sdist == self.path_sdist, (path_sdist, self.path_sdist)

        checksum = _sha256(path_sdist)

        if checksum_pre and checksum != checksum_pre:
            raise RuntimeError(
                f"Checksum changed for {self.distname}:\n"
                f"Expected: {checksum_pre}\n"
                f"Got:      {checksum}\n"
            )

        return not checksum_pre

    @staticmethod
    def clean_generated() -> None:
        """Clean all projects sources."""
        if DIR_PROJECTS.exists():
            shutil.rmtree(str(DIR_PROJECTS))


# project build number (patch version) as YYYYMMDD
BUILD = _get_build_number()

PROJECTS = [
    Project(np_range=((1, 22), (1, 25)), py_range=((3, 8), (3, 12))),
    Project(np_range=((1, 25), (2, 0)), py_range=((3, 9), (3, 13))),
    Project(np_range=((2, 0), (2, 1)), py_range=((3, 9), (3, 13))),
    Project(np_range=((2, 1), (2, 2)), py_range=((3, 10), (3, 14))),
    Project(np_range=((2, 2), (2, 3)), py_range=((3, 10), (3, 14))),
    Project(np_range=((2, 3), (2, 4)), py_range=((3, 11), (3, 14))),
]


def main() -> int:
    Project.clean_generated()

    for project in PROJECTS:
        project.build()
        print(f"Built {project.distname}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
