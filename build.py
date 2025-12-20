# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "jinja2 >=3.1.6",
#     "uv >=0.9.16",
# ]
# ///

# pyright: reportAny=false

import dataclasses
import datetime as dt
import operator
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Container
from pathlib import Path
from typing import Final, NamedTuple, Self, final, override

import jinja2

NAME = "numpy_typing_compat"
REPO = "https://github.com/jorenham/numpy-typing-compat"

# build number (patch version) as YYYYMMDD
_TODAY = dt.datetime.now(tz=dt.UTC).date()
BUILD = _TODAY.year * 10_000 + _TODAY.month * 100 + _TODAY.day

DIR_ROOT = Path(__file__).parent
DIR_DIST = DIR_ROOT / "dist"
DIR_BUILD = DIR_ROOT / "build"
DIR_TEMPLATES = DIR_ROOT / "templates"

JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(DIR_TEMPLATES),
    keep_trailing_newline=True,
)


@dataclasses.dataclass(slots=True)
class Flags:
    """Flags for the build script."""

    keep: bool = False
    quiet: bool = False
    silent: bool = False

    def __post_init__(self, /) -> None:
        if self.silent:
            self.quiet = True

    @classmethod
    def from_args(cls, args: Container[str] = sys.argv[1:], /) -> Self:
        return cls(**{
            k: f"--{k}" in args
            for k in map(operator.attrgetter("name"), dataclasses.fields(cls))
        })


class Version(NamedTuple):
    """A version tuple with a custom string representation."""

    major: int
    minor: int
    pre: str = ""

    @property
    def stable(self) -> Self:
        return type(self)(self.major, self.minor) if self.pre else self

    @override
    def __str__(self, /) -> str:
        return f"{self.major}.{self.minor}{self.pre}"

    @override
    def __repr__(self, /) -> str:
        return f"<{type(self).__name__} {self}>"


type VersionRange = tuple[Version, Version]


class DistInfo[T](NamedTuple):
    sdist: T
    wheel: T


def _get_template(fname: str, /) -> jinja2.Template:
    return JINJA_ENV.get_template(
        f"{fname}.jinja",
        globals={
            "NAME": NAME,
            "REPO": REPO,
            "BUILD": BUILD,
            "PROJECTS": PROJECTS,
        },
    )


def _run_command(
    *cmd: str,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    flags = Flags.from_args()

    if not flags.quiet:
        print(">>>", " ".join(cmd), file=sys.stderr)

    completed = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)

    if not flags.quiet:
        _ = sys.stdout.write(completed.stdout)
        _ = sys.stderr.write(completed.stderr)

    try:
        completed.check_returncode()
    except subprocess.CalledProcessError:
        if flags.quiet:
            _ = sys.stderr.write(completed.stderr)
        raise

    return completed


@final
class Project:
    np_range: Final[VersionRange]
    py_range: Final[VersionRange]

    def __init__(self, /, np_range: VersionRange, py_range: VersionRange) -> None:
        self.np_range = np_range
        self.py_range = py_range

    @property
    def version(self, /) -> str:
        return f"{BUILD}.{self.np_range[0].stable}"

    @property
    def name(self, /) -> str:
        return f"{NAME}-{self.version}"

    @property
    def project_path(self, /) -> Path:
        return DIR_BUILD / self.name

    @property
    def dist_paths(self, /) -> DistInfo[Path]:
        return DistInfo(
            sdist=DIR_DIST / f"{self.name}.tar.gz",
            wheel=DIR_DIST / f"{self.name}-py3-none-any.whl",
        )

    @property
    def const_name(self, /) -> str:
        return f"NUMPY_GE_{self.np_range[0].stable}".replace(".", "_")

    @override
    def __str__(self, /) -> str:
        return self.name

    @override
    def __repr__(self, /) -> str:
        clsname = type(self).__name__
        return f"<{clsname} np_range={self.np_range} py_range={self.py_range}>"

    def _render_to_string(self, fname: str, /) -> str:
        np_start, np_stop = self.np_range
        py_start, py_stop = self.py_range
        context = {
            "project": self,
            "np_start": np_start,
            "np_stop": np_stop,
            "py_start": py_start,
            "py_stop": py_stop,
        }
        return _get_template(fname).render(**context)

    def _run_command(self, /, *cmd: str) -> subprocess.CompletedProcess[str]:
        return _run_command(*cmd, cwd=self.project_path)

    def _lint_project(self, /) -> None:
        # ruff check and format the generated code
        for ruff_cmd in ("check", "format"):
            _ = self._run_command(
                "uvx",
                "ruff",
                ruff_cmd,
                "--no-cache",
                "--preview",
                "--quiet",
            )

    def _create_project(self, /) -> None:
        project_dir = self.project_path
        project_dir.mkdir(parents=True, exist_ok=True)

        for fname in ("LICENSE", "README.md"):
            _ = shutil.copy2(str(DIR_ROOT / fname), str(project_dir / fname))

        # pyproject.toml
        pyproject_path = project_dir / "pyproject.toml"
        _ = pyproject_path.write_text(self._render_to_string("pyproject.toml"))

        # src/numpy_typing_compat/
        module_dir = project_dir / "src" / NAME
        module_dir.mkdir(parents=True, exist_ok=True)

        # src/numpy_typing_compat/py.typed
        py_typed_path = module_dir / "py.typed"
        _ = py_typed_path.write_text("")

        # src/numpy_typing_compat/__init__.py
        init_file = module_dir / "__init__.py"
        _ = init_file.write_text(self._render_to_string("__init__.py"))

        self._lint_project()

    def _validate_wheel(self, /) -> None:
        py_flag = f"--python={self.py_range[0]}"

        with tempfile.TemporaryDirectory() as tmpdir:
            # create a temporary uv project
            _ = _run_command(
                "uv",
                "init",
                "--bare",
                "--no-cache",
                "--name=nptc-test",
                py_flag,
                cwd=tmpdir,
            )

            # install the wheel
            wheel = str(self.dist_paths.wheel)
            _ = _run_command("uv", "add", py_flag, wheel, cwd=tmpdir)

            # try to import the package, and ensure satisfiable version constraints
            _ = _run_command(
                "uv",
                "run",
                py_flag,
                "python",
                "-c",
                f"import {NAME} as nptc; assert nptc._check_version()",
                cwd=tmpdir,
            )

            # validate the static type annotations
            pyright = "basedpyright"
            _ = _run_command("uv", "add", py_flag, pyright, cwd=tmpdir)
            _ = _run_command(
                "uv",
                "run",
                py_flag,
                pyright,
                "--level=warning",
                "--ignoreexternal",
                f"--verifytypes={NAME}",
                cwd=tmpdir,
            )

    def build(self, /) -> None:
        """Create and `uv build` the projects."""
        self._create_project()

        completed = self._run_command("uv", "build", f"--out-dir={DIR_DIST}")

        # verify that the build was successful
        paths: list[Path] = []
        for match in re.finditer(r"Successfully built (/[\w\-\./]+)", completed.stderr):
            out_path = Path.cwd() / match.group(1)
            assert out_path.is_file(), out_path
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

        paths_expect = self.dist_paths
        assert path_sdist == paths_expect.sdist, (path_sdist, paths_expect.sdist)
        assert path_wheel == paths_expect.wheel, (path_wheel, paths_expect.wheel)

        self._validate_wheel()


PROJECTS = [
    Project(
        np_range=(Version(1, 22), Version(1, 23)),
        py_range=(Version(3, 8), Version(3, 11)),
    ),
    Project(
        np_range=(Version(1, 23), Version(1, 25)),
        py_range=(Version(3, 8), Version(3, 12)),
    ),
    Project(
        np_range=(Version(1, 25), Version(2, 0)),
        py_range=(Version(3, 9), Version(3, 13)),
    ),
    Project(
        np_range=(Version(2, 0), Version(2, 1)),
        py_range=(Version(3, 9), Version(3, 13)),
    ),
    Project(
        np_range=(Version(2, 1), Version(2, 2)),
        py_range=(Version(3, 10), Version(3, 14)),
    ),
    Project(
        np_range=(Version(2, 2), Version(2, 3)),
        py_range=(Version(3, 10), Version(3, 14)),
    ),
    Project(
        np_range=(Version(2, 3), Version(2, 4)),
        py_range=(Version(3, 11), Version(3, 15)),
    ),
    Project(
        np_range=(Version(2, 4), Version(2, 5)),
        py_range=(Version(3, 11), Version(3, 15)),
    ),
]


def main(*args: str) -> int:
    flags = Flags.from_args(set(args))
    cwd = Path.cwd()

    for project in PROJECTS:
        project.build()
        paths = project.dist_paths

        if not flags.silent:
            for path in paths:
                print(path.relative_to(cwd), file=sys.stdout)

    if not flags.keep and DIR_BUILD.exists():
        shutil.rmtree(DIR_BUILD)

    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
else:
    raise RuntimeError("This module is intended to be run as a script only.")
