"""P5 trusted-operator composition. No approval loader or credential discovery.

The operator-supplied authority verifies original Owner evidence; an APPROVED
string/dict is not that interface. Python objects do not prove human origin.
No production authority or credential resolver is installed by this module.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal

from modules.p5_runtime import P5ExecutionPermit, P5Runtime, P5Stopped
from modules.sg_continuous_runtime import _digest


OBSERVATIONS = frozenset({'repository', 'release', 'source_digest', 'entrypoint',
    'execution_target', 'machine', 'port', 'loopback', 'storage', 'credential', 'primary_sources', 'pricing', 'plan'})
OPERATIONS = frozenset({'keepa.token', 'keepa.product', 'keepa.query', 'shopee.category',
    'shopee.brand', 'shopee.attribute', 'bridge', 'auth', 'image', 'openai',
    'material.update', 'p2.save', 'output'})
BUDGETS = ('keepa_requests', 'keepa_products', 'keepa_tokens', 'shopee_requests',
           'bridge_requests', 'auth_requests', 'image_requests', 'openai_requests', 'openai_usd')


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
    def __init__(self, *, authority, observe, resolve_secrets, clock=None, synthetic=False, checkpoint=None):
        self.authority, self.observe, self.resolve_secrets = authority, observe, resolve_secrets
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.synthetic = synthetic
        self.checkpoint = checkpoint

    def _check(self, scope, reference):
        scope.validate()
        approval = self.authority.verify_original(reference)
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
        if (not isinstance(observed, dict) or set(observed) != OBSERVATIONS
                or any(not v for v in observed.values())
                or observed['release'] != scope.release
                or observed['execution_target'] != scope.execution_target
                or observed['loopback'] is not True or type(observed['port']) is not int
                or not 1 <= observed['port'] <= 65535
                or _digest(observed) != approval.observations_digest):
            raise P5Stopped('P5_EXECUTION_OBSERVATION_MISMATCH')
        if (observed['plan'] != asdict(scope)
                or observed['credential'] != {'reference': scope.credential_ref,
                    'marketplace': scope.marketplace, 'shop': scope.shop_id}
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
