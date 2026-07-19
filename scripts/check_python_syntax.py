"""Parse Python sources without creating ``.pyc`` artifacts.

This helper is intentionally small: verification callers can use it instead of
``compileall`` or ``py_compile``, both of which can create generated files in
the repository worktree.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SKIPPED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".pytest_tmp",
    ".venv",
    "__pycache__",
    "cache",
    "outputs",
    "work",
}


def iter_python_files(paths: list[Path]) -> list[Path]:
    """Return unique Python files below the supplied files or directories."""

    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.add(path)
            continue
        if not path.is_dir():
            raise FileNotFoundError(f"Python syntax target does not exist: {path}")
        for candidate in path.rglob("*.py"):
            if not any(part in SKIPPED_DIRECTORIES for part in candidate.parts):
                files.add(candidate)
    return sorted(files)


def parse_python_file(path: Path) -> None:
    """Compile source in memory only, preserving the current worktree."""

    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec", dont_inherit=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path("app.py"), Path("modules"), Path("tests"), Path("scripts")],
        help="Python files or directories to parse (default: application, modules, tests, scripts).",
    )
    arguments = parser.parse_args()

    try:
        python_files = iter_python_files(arguments.paths)
    except (FileNotFoundError, OSError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    failures: list[str] = []
    for path in python_files:
        try:
            parse_python_file(path)
        except (OSError, SyntaxError, UnicodeError) as error:
            line_number = getattr(error, "lineno", None)
            location = f":{line_number}" if line_number else ""
            failures.append(f"{path}{location}: {error}")

    if failures:
        print("FAIL: Python syntax check", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"PASS: Python syntax check ({len(python_files)} file(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
