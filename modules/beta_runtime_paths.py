"""Per-render paths for the common beta shell; never mutate process settings."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import dotenv_values


@dataclass(frozen=True)
class BetaRuntimePaths:
    ph_root: Path
    ph_api_env: Path


_paths = ContextVar('beta_runtime_paths', default=None)


class BetaRuntimePathError(ValueError):
    pass


def current_beta_paths():
    return _paths.get()


def beta_env_value(name, default=''):
    paths = current_beta_paths()
    if name in os.environ or paths is None:
        return os.environ.get(name, default)
    return dotenv_values(paths.ph_api_env).get(name) or default


@contextmanager
def beta_runtime_paths(ph_root=None, ph_api_env=None):
    if (ph_root is None) != (ph_api_env is None):
        raise BetaRuntimePathError('Both PH runtime paths are required.')
    paths = None
    if ph_root is not None:
        root, env = Path(ph_root), Path(ph_api_env)
        if not root.is_absolute() or not env.is_absolute() or not root.is_dir() or not env.is_file():
            raise BetaRuntimePathError('Existing PH runtime paths are required.')
        paths = BetaRuntimePaths(root.resolve(), env.resolve())
    token = _paths.set(paths)
    try:
        yield
    finally:
        _paths.reset(token)
