# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "jinja2 >=3.1.6",
#     "uv >=0.8.3",
# ]
# ///

# pyright: reportAny=false

import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Final, NamedTuple, final, override

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


def _sha256sum(path: str | Path, /) -> str:
    with Path(path).open("rb") as fp:
        digest = hashlib.file_digest(fp, "sha256")
    return digest.hexdigest()


def _fetch_json(
    url: str,
    /,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 5,
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """Make a JSON request to the given URL."""
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise IOError(f"Failed to fetch {url}: {response.status} {response.reason}")
        contents = response.read()
    return json.loads(contents)  # type: ignore[no-any-return]


def _run_command(
    *cmd: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    if not (quiet := "--quiet" in sys.argv):
        print(">>>", " ".join(cmd), file=sys.stderr)

    completed = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)

    if not quiet:
        _ = sys.stdout.write(completed.stdout)
        _ = sys.stderr.write(completed.stderr)

    try:
        completed.check_returncode()
    except subprocess.CalledProcessError:
        if quiet:
            _ = sys.stderr.write(completed.stderr)
        raise

    return completed


class Version(NamedTuple):
    """A version tuple with a custom string representation."""

    major: int
    minor: int

    @override
    def __str__(self, /) -> str:
        return f"{self.major}.{self.minor}"

    @override
    def __repr__(self, /) -> str:
        clsname = type(self).__name__
        return f"<{clsname} {self.major}.{self.minor}>"


type VersionRange = tuple[Version, Version]


class DistInfo[T](NamedTuple):
    sdist: T
    wheel: T


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
    def name(self, /) -> str:
        return f"{NAME}-{self.version}"

    @property
    def project_path(self, /) -> Path:
        return DIR_PROJECTS / self.name

    @property
    def dist_paths(self, /) -> DistInfo[Path]:
        return DistInfo(
            sdist=DIR_DIST / f"{self.name}.tar.gz",
            wheel=DIR_DIST / f"{self.name}-py3-none-any.whl",
        )

    @property
    def dist_hashes(self, /) -> DistInfo[str]:
        return DistInfo(
            sdist=_sha256sum(self.dist_paths.sdist),
            wheel=_sha256sum(self.dist_paths.wheel),
        )

    @property
    def const_name(self, /) -> str:
        return f"NUMPY_GE_{self.np_range[0]}".replace(".", "_")

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
            "np_start": np_start,
            "np_stop": np_stop,
            "py_start": py_start,
            "py_stop": py_stop,
        }
        return _get_template(fname).render(**context)

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

        # ruff check and format the generated code
        for ruff_cmd in ("check", "format"):
            _ = _run_command(
                "uvx",
                "ruff",
                ruff_cmd,
                "--no-cache",
                "--preview",
                "--quiet",
                cwd=self.project_path,
            )

    def build(self, /) -> None:
        """Create and `uv build` the projects."""
        self._create_project()

        completed = _run_command(
            "uv",
            "build",
            f"--directory=./{self.project_path.relative_to(Path.cwd())}",
            f"--out-dir={DIR_DIST}",
        )

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


def _fetch_latest_release_hashes() -> DistInfo[dict[Version, tuple[int, str]]]:
    # https://peps.python.org/pep-0691/
    # https://docs.pypi.org/api/index-api/#json_1
    data = _fetch_json(
        f"https://files.pythonhosted.org/simple/{NAME}",
        headers={
            "Host": "pypi.org",
            "Accept": "application/vnd.pypi.simple.v1+json",
        },
    )
    if "files" not in data:
        raise ValueError(f"Invalid response from PyPI: {data!r}")

    # keep only the latest sdist and wheel files for each numpy version
    # {Version: (build, sha256)}
    latest_sdists: dict[Version, tuple[int, str]] = {}
    latest_wheels: dict[Version, tuple[int, str]] = {}
    for file in data["files"]:
        fname: str = file["filename"]
        if fname.endswith(".whl"):
            # e.g. numpy_typing_compat-1.22.20250724-py3-none-any.whl
            pattern = rf"{NAME}-(\d)\.(\d+)\.(\d+)-py3-none-any\.whl"
            target = latest_wheels
        else:
            # e.g. numpy_typing_compat-1.25.20250724.tar.gz
            pattern = rf"{NAME}-(\d)\.(\d+)\.(\d+)\.tar\.gz"
            target = latest_sdists

        match = re.match(pattern, fname)
        assert match, file

        np_version = Version(int(match.group(1)), int(match.group(2)))
        build = int(match.group(3))
        assert build > 2025_06_00, file

        if np_version not in target or target[np_version][0] < build:
            target[np_version] = build, file["hashes"]["sha256"]

    return DistInfo(sdist=latest_sdists, wheel=latest_wheels)


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
]


def main(*args: str) -> int:
    latest_hashes: DistInfo[dict[Version, tuple[int, str]]]
    if "--always" in args:
        latest_hashes = DistInfo({}, {})
    else:
        latest_hashes = _fetch_latest_release_hashes()

    quiet = "--quiet" in args
    silent = "--silent" in args

    for project in PROJECTS:
        project.build()
        np_version = project.np_range[0]
        hashes = project.dist_hashes
        paths = project.dist_paths

        for build_hashes, hash_, path in zip(latest_hashes, hashes, paths, strict=True):
            pypi_build, pypi_hash = build_hashes.get(np_version, (0, ""))
            if pypi_hash == hash_:
                if not quiet:
                    print(
                        f"no changes since {np_version}.{pypi_build} - removing {path}",
                        file=sys.stderr,
                    )

                path.unlink()
            elif not silent:
                # only print the paths of new builds to stdout
                print(path.relative_to(Path.cwd()), file=sys.stdout)

    # TODO: remove sdist/wheel if their hashes match the latest existing PyPI
    # version of the numpy branch

    if "--keep" not in args and DIR_PROJECTS.exists():
        shutil.rmtree(DIR_PROJECTS)

    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
