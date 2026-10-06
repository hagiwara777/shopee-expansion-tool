"""Local SG deployment preflight. Never initializes a DB or calls an API."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from modules.sg_live_runtime import SGLiveRunGrant
from modules.product_review_transport import SGProductEvidenceLoader
from modules.sg_beta_release import require_sg_beta_operation

ROOT = Path(__file__).resolve().parents[1]
INPUT_NAMES = frozenset({'candidate.csv', 'product_text.csv', 'raw_images.json'})
GATE_NAMES = frozenset({'prelisting_gate_eligible_sg_resolver.csv', 'prelisting_gate_eligible_sg_expansion.csv'})


class SGBetaEnvironmentError(ValueError):
    pass


def _git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def preflight(config_path):
    """Require the pinned, clean formal release and exact initial input bundle.

    This validates settings only. The grant still needs genuine owner approval;
    neither this file nor a successful preflight establishes that approval.
    """
    try:
        config = json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
        keys = {'schema_version', 'marketplace', 'release_commit', 'repository_path',
                'python_path', 'grant_path', 'api_env_path', 'google_credentials_path',
                'data_root', 'inputs_dir', 'input_sha256', 'gate_filename', 'port'}
        if (set(config) != keys or type(config['schema_version']) is not int or config['schema_version'] != 1 or config['marketplace'] != 'SG'
                or type(config['port']) is not int or config['port'] != 8502 or config['gate_filename'] not in GATE_NAMES
                or not re.fullmatch(r'[a-f0-9]{40}', config['release_commit'])):
            raise ValueError
        paths = {key: Path(config[key]) for key in ('repository_path', 'python_path', 'grant_path',
                 'api_env_path', 'google_credentials_path', 'data_root', 'inputs_dir')}
        if any(not path.is_absolute() for path in paths.values()):
            raise ValueError
        if paths['repository_path'].resolve() != ROOT.resolve():
            raise ValueError
        if any(not paths[key].is_file() for key in ('python_path','grant_path','api_env_path','google_credentials_path')):
            raise ValueError
        if _git('rev-parse', 'HEAD') != config['release_commit'] or _git('status','--porcelain','--untracked-files=no'):
            raise ValueError
        _git('merge-base','--is-ancestor',config['release_commit'],'refs/remotes/origin/main')
        require_sg_beta_operation()
        grant = SGLiveRunGrant.from_file(paths['grant_path'])
        data_root = paths['data_root'].resolve()
        if data_root == ROOT.resolve() or ROOT.resolve() in data_root.parents:
            raise ValueError
        grant.validate(data_root/grant.digest/'validation.sqlite3')
        hashes = config['input_sha256']
        names = INPUT_NAMES | {config['gate_filename']}
        if set(hashes) != names:
            raise ValueError
        contents = {name: (paths['inputs_dir']/name).read_bytes() for name in names}
        if any(not re.fullmatch(r'[a-f0-9]{64}', hashes[name]) or
               hashlib.sha256(content).hexdigest() != hashes[name] for name,content in contents.items()):
            raise ValueError
        loader = SGProductEvidenceLoader(candidate_content=contents['candidate.csv'],
            text_content=contents['product_text.csv'], image_content=contents['raw_images.json'],
            gate_content=contents[config['gate_filename']], gate_filename=config['gate_filename'])
        from modules.category_mapper_sg import parse_sg_category_mapper_input
        source = parse_sg_category_mapper_input(contents[config['gate_filename']], filename=config['gate_filename'])
        if {row.candidate_asin for row in source.rows} != set(grant.allowed_asins):
            raise ValueError
        # Validation above checks the corresponding raw evidence; no human
        # Category/Brand/Safety approval is imported from an earlier DB.
        del loader
        return config
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ArithmeticError, subprocess.SubprocessError):
        raise SGBetaEnvironmentError('SG beta settings, adopted code or input files need confirmation.') from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    try:
        preflight(args.config)
    except SGBetaEnvironmentError:
        print('SG_BETA_ENVIRONMENT_NOT_READY')
        return 1
    print('PASS: SG beta environment preflight (no API calls)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
