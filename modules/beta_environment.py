"""Unified launcher preflight, preserving the existing SG acceptance contract."""
import argparse
import json
from pathlib import Path

from modules import sg_beta_environment as sg


class BetaEnvironmentError(ValueError):
    pass


def preflight(config_path):
    try:
        c = json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
        keys = {'schema_version', 'repository_path', 'release_commit', 'python_path',
                'sg_config_path', 'ph_runtime_root', 'ph_api_env_path', 'server_data_root', 'port'}
        if set(c) != keys or type(c['schema_version']) is not int or c['schema_version'] != 1:
            raise ValueError
        if type(c['port']) is not int or c['port'] != 8503:
            raise ValueError
        paths = {key: Path(c[key]) for key in keys if key.endswith('_path') or key.endswith('_root')}
        if any(not p.is_absolute() for p in paths.values()):
            raise ValueError
        configured_sg = sg.preflight(paths['sg_config_path'])
        if (paths['repository_path'].resolve() != sg.ROOT.resolve()
                or c['release_commit'] != configured_sg['release_commit']
                or paths['python_path'].resolve() != Path(configured_sg['python_path']).resolve()):
            raise ValueError
        ph_root = paths['ph_runtime_root'].resolve()
        data = paths['server_data_root'].resolve()
        sg_data = Path(configured_sg['data_root']).resolve()
        if not (ph_root / 'cache' / 'keepa_cache.sqlite3').is_file() or not paths['ph_api_env_path'].is_file():
            raise ValueError
        roots = (sg.ROOT.resolve(), ph_root, sg_data)
        if any(data == root or root in data.parents or data in root.parents for root in roots):
            raise ValueError
        if ph_root == sg_data or ph_root in sg_data.parents or sg_data in ph_root.parents:
            raise ValueError
        return c
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        raise BetaEnvironmentError('Unified beta deployment needs confirmation.') from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    try:
        preflight(args.config)
    except BetaEnvironmentError:
        print('BETA_ENVIRONMENT_NOT_READY')
        return 1
    print('PASS: unified PH/SG beta preflight (no API calls)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
