"""P5 trusted-operator composition. No approval loader or credential discovery.

The operator-supplied authority verifies original Owner evidence; an APPROVED
string/dict is not that interface. Python objects do not prove human origin.
No production authority is installed. Credential references have no defaults.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import inspect
from types import CodeType, FunctionType

from modules.p5_runtime import P5ExecutionPermit, P5Runtime, P5Stopped
from modules.sg_continuous_runtime import _digest


OBSERVATIONS = frozenset({'repository', 'release', 'source_digest', 'entrypoint',
    'execution_target', 'machine', 'port', 'loopback', 'storage', 'credential', 'primary_sources', 'pricing', 'plan'})
OPERATIONS = frozenset({'keepa.token', 'keepa.product', 'keepa.query', 'shopee.category',
    'shopee.brand', 'shopee.attribute', 'bridge', 'auth', 'image', 'openai',
    'material.update', 'p2.save', 'output'})
BUDGETS = ('keepa_requests', 'keepa_products', 'keepa_tokens', 'shopee_requests',
           'bridge_requests', 'auth_requests', 'image_requests', 'openai_requests', 'openai_usd')


class P5CodeIdentity:
    """Observe this imported checkout and the running entrypoint, never config.

    This is a trusted process boundary, not protection against arbitrary code
    running as the same OS user. No fetch, checkout or release installation.
    """
    @staticmethod
    def _require_loaded_source(module, path):
        # A clean file alone is insufficient: an older function may still be
        # executing after the file was replaced. Compare loaded functions and
        # methods with the current source, including nested code constants.
        def normalized(code):
            return code.replace(co_filename='<P5>', co_consts=tuple(
                normalized(c) if isinstance(c, CodeType) else c for c in code.co_consts))
        def check(expected, namespace):
            for code in expected.co_consts:
                if not isinstance(code, CodeType) or code.co_name.startswith('<'):
                    continue
                actual = namespace.get(code.co_name)
                if isinstance(actual, type) and actual.__module__ == module.__name__:
                    check(code, vars(actual))
                    continue
                if isinstance(actual, (classmethod, staticmethod)):
                    actual = actual.__func__
                if isinstance(actual, property):
                    actual = actual.fget
                actual = inspect.unwrap(actual)
                if not isinstance(actual, FunctionType) or normalized(actual.__code__) != normalized(code):
                    raise ValueError()
        check(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True), vars(module))

    def observe(self):
        root = Path(__file__).resolve().parent.parent
        try:
            entrypoint = Path(sys.modules['__main__'].__file__).resolve()
            relative = entrypoint.relative_to(root).as_posix()
            if relative != 'app_beta.py':
                raise ValueError()
            # Reject mixed imports from an older checkout, even with equal HEAD.
            from modules import p5_transport  # explicit start only; no credential I/O
            for name in ('p5_live_adapter', 'p5_runtime', 'p5_transport', 'shopee_catalog_client'):
                module = sys.modules.get('modules.' + name)
                path = root / 'modules' / (name + '.py')
                if module is None or Path(module.__file__).resolve() != path:
                    raise ValueError()
                self._require_loaded_source(module, path)
            def git(*args):
                result = subprocess.run(['git', '-C', str(root), *args], check=True,
                    capture_output=True, timeout=10)
                return result.stdout.decode('utf-8').strip()
            if (Path(git('rev-parse', '--show-toplevel')).resolve() != root
                    or git('remote', 'get-url', 'origin') != 'https://github.com/hagiwara777/shopee-expansion-tool.git'
                    or git('status', '--porcelain', '--untracked-files=normal')):
                raise ValueError()
            release = git('rev-parse', 'HEAD')
            git('ls-files', '--error-unmatch', '--', relative)
            tree = git('rev-parse', 'HEAD^{tree}')
            # Recheck after observation so a changing checkout cannot produce a
            # mixed clean/release observation.
            if git('rev-parse', 'HEAD') != release or git('status', '--porcelain', '--untracked-files=normal'):
                raise ValueError()
            return dict(release=release, source_digest=sha256(tree.encode('ascii')).hexdigest(),
                        entrypoint=relative)
        except Exception:
            raise P5Stopped('P5_EXECUTION_CODE_UNVERIFIED') from None


@dataclass(frozen=True, repr=False)
class P5CredentialReference:
    """Non-secret references fixed by the trusted operator, not daily config."""
    reference: str
    marketplace: str
    shop_id: str
    audit_env: str
    google_credential_file: str
    bridge_spreadsheet_id: str

    def describe(self, scope):
        if (self.reference != scope.credential_ref or self.marketplace != scope.marketplace
                or self.shop_id != scope.shop_id or not self.bridge_spreadsheet_id
                or self.bridge_spreadsheet_id != scope.bridge_spreadsheet_id
                or any(not isinstance(p, str) or not p.strip() or not Path(p).is_absolute()
                       for p in (self.audit_env, self.google_credential_file))):
            raise P5Stopped('P5_APPROVED_CREDENTIAL_REFERENCE_REQUIRED')
        return dict(reference=self.reference, marketplace=self.marketplace, shop=self.shop_id,
                    binding_digest=_digest(asdict(self)))


class P5CredentialResolver:
    """Reuse the PH/SG reader lazily; Bridge supplies the access token later."""
    def __init__(self, reference):
        self.reference = reference

    def describe(self, scope):
        if type(self.reference) is not P5CredentialReference:
            raise P5Stopped('P5_APPROVED_CREDENTIAL_REFERENCE_REQUIRED')
        return self.reference.describe(scope)

    def __call__(self, scope):
        self.describe(scope)  # Must precede any secret file read.
        from dataclasses import replace
        from modules.shopee_catalog_client import load_shopee_catalog_credentials
        from modules.p5_transport import P5Secrets
        try:
            credentials = load_shopee_catalog_credentials(self.reference.audit_env,
                marketplace=scope.marketplace, require_access_token=False)
            if str(credentials.shop_id) != scope.shop_id:
                raise ValueError()
            # Never use a legacy token, including one present in audit.env.
            return P5Secrets(scope.credential_ref, scope.marketplace, scope.shop_id,
                replace(credentials, access_token=''),
                google_credential_file=self.reference.google_credential_file)
        except Exception:
            raise P5Stopped('P5_CREDENTIAL_RESOLUTION_STOPPED') from None


@dataclass(frozen=True, repr=False)
class OperatorApproval:
    owner_ref: str
    original_instruction_ref: str
    approved_at: datetime
    expires_at: datetime
    end_condition_ref: str
    ticket_digest: str
    scope_digest: str
    observations_digest: str
    operations: frozenset
    allocations: tuple  # immutable complete P5Scopes, PH/SG fixed allocation
    total_limits: tuple  # (budget name, ceiling), no market borrowing
    revoked: bool = False


class P5TrustedAdapter:
    def __init__(self, *, authority, observe, resolve_secrets, clock=None, synthetic=False, checkpoint=None,
                 code_identity=None):
        if type(synthetic) is not bool:
            raise P5Stopped('P5_SYNTHETIC_MODE_INVALID')
        self.authority, self.observe, self.resolve_secrets = authority, observe, resolve_secrets
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.synthetic = synthetic
        self.checkpoint = checkpoint
        self.code_identity = code_identity

    def _check(self, scope, reference):
        scope.validate()
        if not isinstance(reference, str) or not reference.strip():
            raise P5Stopped('P5_OWNER_APPROVAL_UNVERIFIED')
        try:
            approval = self.authority.verify_original(reference)
        except Exception:
            raise P5Stopped('P5_OWNER_APPROVAL_UNVERIFIED') from None
        now = self.clock()
        if (type(approval) is not OperatorApproval or approval.revoked is not False
                or any(not isinstance(v, str) or not v.strip() for v in
                    (approval.owner_ref, approval.original_instruction_ref, approval.end_condition_ref,
                     approval.ticket_digest))
                or approval.scope_digest != scope.digest
                or not isinstance(approval.approved_at, datetime) or not isinstance(approval.expires_at, datetime)
                or approval.approved_at.tzinfo is None or approval.expires_at.tzinfo is None
                or not approval.approved_at <= now < approval.expires_at
                or type(approval.operations) is not frozenset or not approval.operations
                or not approval.operations <= OPERATIONS):
            raise P5Stopped('P5_OWNER_APPROVAL_UNVERIFIED')
        allocations = approval.allocations
        totals = dict(approval.total_limits)
        if (not allocations or len(allocations) > 2 or scope not in allocations
                or len({s.marketplace for s in allocations}) != len(allocations)
                or set(totals) != set(BUDGETS)):
            raise P5Stopped('P5_MARKET_ALLOCATION_INVALID')
        for allocation in allocations:
            allocation.validate()
        for name in BUDGETS:
            ceiling = Decimal(str(totals[name]))
            if not ceiling.is_finite() or ceiling < 0 or sum(
                    (Decimal(str(getattr(s, name))) for s in allocations), Decimal(0)) > ceiling:
                raise P5Stopped('P5_MARKET_ALLOCATION_EXCEEDED')
        observed = self.observe(scope)
        if not isinstance(observed, dict):
            raise P5Stopped('P5_EXECUTION_OBSERVATION_MISMATCH')
        credential = dict(reference=scope.credential_ref, marketplace=scope.marketplace, shop=scope.shop_id)
        if not self.synthetic:
            if type(self.code_identity) is not P5CodeIdentity:
                raise P5Stopped('P5_EXECUTION_CODE_UNVERIFIED')
            if type(self.resolve_secrets) is not P5CredentialResolver:
                raise P5Stopped('P5_APPROVED_CREDENTIAL_REFERENCE_REQUIRED')
            credential = self.resolve_secrets.describe(scope)
            code = self.code_identity.observe()
            if any(observed.get(key) != value for key, value in code.items()):
                raise P5Stopped('P5_EXECUTION_CODE_MISMATCH')
        if (not isinstance(observed, dict) or set(observed) != OBSERVATIONS
                or any(not v for v in observed.values())
                or observed['release'] != scope.release
                or observed['execution_target'] != scope.execution_target
                or observed['loopback'] is not True or type(observed['port']) is not int
                or not 1 <= observed['port'] <= 65535
                or _digest(observed) != approval.observations_digest):
            raise P5Stopped('P5_EXECUTION_OBSERVATION_MISMATCH')
        if (observed['plan'] != asdict(scope)
                or observed['credential'] != credential
                or not isinstance(observed['storage'], dict)
                or observed['storage'].get('root') != str(scope.directory)
                or observed['storage'].get('store_id') != scope.store_id
                or not all(observed['storage'].get(k) for k in
                           ('volume', 'acl', 'identities', 'capacity_ok'))):
            raise P5Stopped('P5_EXECUTION_TARGET_MISMATCH')
        sources = observed['primary_sources']
        if (not isinstance(sources, dict) or set(sources) != {'category', 'brand', 'attribute'}
                or any(not isinstance(s, dict) or s.get('verified') is not True
                    or any(not s.get(k) for k in ('body_digest', 'version', 'app_shop_permission',
                                                 'paging', 'request_response', 'rate_limit'))
                    for s in sources.values())):
            raise P5Stopped('PRIMARY_SOURCE_UNVERIFIED')
        # The Attribute request contract remains unresolved in this release.
        # Even a self-declared verified flag cannot enable its live operation.
        if not self.synthetic and 'shopee.attribute' in approval.operations:
            raise P5Stopped('P5_ATTRIBUTE_LIVE_NOT_ENABLED')
        pricing = observed['pricing']
        if (not isinstance(pricing, dict) or pricing.get('verified') is not True
                or not pricing.get('reference') or not pricing.get('body_digest')):
            raise P5Stopped('P5_CURRENT_OPENAI_PRICING_UNVERIFIED')
        return approval

    def compose(self, scope, *, approval_reference):
        # No I/O/credential lookup at construction or rendering. Explicit start
        # calls this method after operator verification is available.
        approval = self._check(scope, approval_reference)
        permit = P5ExecutionPermit(scope.digest, approval.original_instruction_ref,
            ('category', 'brand', 'attribute'), offline_test=self.synthetic,
            openai_pricing_ref=self.observe(scope)['pricing']['reference'])
        runtime = P5Runtime(scope, permit=permit,
            execution_identity=lambda: (self.observe(scope)['release'], self.observe(scope)['execution_target']))
        def guard(operation=None):
            current = self._check(scope, approval_reference)
            if current != approval or (operation is not None and operation not in current.operations):
                raise P5Stopped('P5_OPERATION_NOT_APPROVED')
        runtime.authorization_guard = guard
        # Resolver is called lazily only after a valid start and permission check.
        runtime.credential_resolver = lambda: self.resolve_secrets(scope)
        runtime.checkpoint_hook = self.checkpoint
        return runtime
