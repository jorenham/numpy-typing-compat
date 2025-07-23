# /// script
# requires-python = ">=3.12"
# dependencies = ["uv", "jinja2"]
# ///

import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final, NamedTuple, final

import jinja2

NAME = "numpy_typing_compat"
REPO = "https://github.com/jorenham/numpy-typing-compat"

# build number (patch version) as YYYYMMDD
_TODAY = dt.date.today()
BUILD = _TODAY.year * 10_000 + _TODAY.month * 100 + _TODAY.day

DIR_ROOT = Path(__file__).parent
DIR_DIST = DIR_ROOT / "dist"
DIR_PROJECTS = DIR_ROOT / "projects"
DIR_TEMPLATES = DIR_ROOT / "templates"

JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(DIR_TEMPLATES),
    keep_trailing_newline=True,
)


def _get_template(fname: str) -> jinja2.Template:
    return JINJA_ENV.get_template(
        f"{fname}.jinja",
        globals={
            "NAME": NAME,
            "REPO": REPO,
            "BUILD": BUILD,
            "PROJECTS": PROJECTS,
        },
    )


class Version(NamedTuple):
    """A version tuple with a custom string representation."""

    major: int
    minor: int

    def __str__(self, /) -> str:
        return f"{self.major}.{self.minor}"

    def __repr__(self, /) -> str:
        clsname = type(self).__name__
        return f"<{clsname} {self.major}.{self.minor}>"


type VersionRange = tuple[Version, Version]


@final
class Project:
    np_range: Final[VersionRange]
    py_range: Final[VersionRange]

    def __init__(self, /, np_range: VersionRange, py_range: VersionRange) -> None:
        self.np_range = np_range
        self.py_range = py_range

    @property
    def version(self, /) -> str:
        return f"{self.np_range[0]}.{BUILD}"

    @property
    def distname(self, /) -> str:
        return f"{NAME}-{self.version}"

    @property
    def path_project(self, /) -> Path:
        return DIR_PROJECTS / self.distname

    @property
    def path_wheel(self, /) -> Path:
        return DIR_DIST / f"{self.distname}-py3-none-any.whl"

    @property
    def path_sdist(self, /) -> Path:
        return DIR_DIST / f"{self.distname}.tar.gz"

    @property
    def const_name(self, /) -> str:
        return f"NUMPY_GE_{self.np_range[0]}".replace(".", "_")

    def __str__(self, /) -> str:
        return self.distname

    def __repr__(self, /) -> str:
        clsname = type(self).__name__
        return f"<{clsname} np_range={self.np_range} py_range={self.py_range}>"

    def __fspath__(self, /) -> str:
        return str(self.path_project)

    def _render_to_string(self, fname: str, /) -> str:
        np_start, np_stop = self.np_range
        py_start, py_stop = self.py_range
        context = {
            "np_start": np_start,
            "np_stop": np_stop,
            "py_start": py_start,
            "py_stop": py_stop,
        }
        return _get_template(fname).render(**context)

    def _create_project(self, /) -> Path:
        project_dir = self.path_project
        project_dir.mkdir(parents=True, exist_ok=True)

        for fname in ("LICENSE", "README.md"):
            shutil.copy2(str(DIR_ROOT / fname), str(project_dir / fname))

        # pyproject.toml
        pyproject_path = project_dir / "pyproject.toml"
        _ = pyproject_path.write_text(self._render_to_string("pyproject.toml"))

        # src/numpy_typing_compat/
        module_dir = project_dir / "src" / NAME
        module_dir.mkdir(parents=True, exist_ok=True)

        # src/numpy_typing_compat/__init__.py
        init_file = module_dir / "__init__.py"
        _ = init_file.write_text(self._render_to_string("__init__.py"))

        # src/numpy_typing_compat/py.typed
        py_typed_path = module_dir / "py.typed"
        _ = py_typed_path.write_text("")

        return project_dir

    def build(self, /) -> None:
        self._create_project()

        cmd = [
            "uv",
            "build",
            f"--directory=./{self.path_project.relative_to(Path.cwd())}",
            f"--out-dir={DIR_DIST}",
        ]
        print("$", " ".join(cmd))

        completed = subprocess.run(cmd, capture_output=True, text=True)
        sys.stderr.write(completed.stderr)
        sys.stdout.write(completed.stdout)
        completed.check_returncode()

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

        assert path_wheel == self.path_wheel, (path_wheel, self.path_wheel)
        assert path_sdist == self.path_sdist, (path_sdist, self.path_sdist)

    @staticmethod
    def clean_generated() -> None:
        """Clean all projects sources."""
        if DIR_PROJECTS.exists():
            shutil.rmtree(str(DIR_PROJECTS))


PROJECTS = [
    Project(
        np_range=(Version(1, 22), Version(1, 25)),
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
        py_range=(Version(3, 11), Version(3, 14)),
    ),
]


def main() -> int:
    Project.clean_generated()

    for project in PROJECTS:
        project.build()

    # Project.clean_generated()

    return 0


if __name__ == "__main__":
    sys.exit(main())
