"""P5 trusted human review and same-entrypoint composition, with no loaders.

The operator reads original Owner evidence through an explicitly supplied
trusted channel and compares it with the current private execution ticket.
This is a human trust boundary, not independent proof of human origin.
No operator/approval is registered by import, JSON, CLI or environment.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4

from modules.p5_live_adapter import OperatorApproval, P5TrustedAdapter, P5CodeIdentity
from modules.p5_runtime import P5Runtime, P5Stopped
from modules.sg_continuous_runtime import _digest


@dataclass(frozen=True, repr=False)
class OriginalOwnerRecord:
    reference: str
    owner_ref: str
    body: str
    recorded_at: datetime
    approval: OperatorApproval

    @property
    def digest(self):
        approval = asdict(self.approval)
        if self.approval.category_permission_trial is None:
            approval.pop('category_permission_trial')  # Preserve existing reviewed record digests.
        approval['approved_at'] = self.approval.approved_at.isoformat()
        approval['expires_at'] = self.approval.expires_at.isoformat()
        approval['operations'] = sorted(self.approval.operations)
        return _digest([self.reference, self.owner_ref, self.body, self.recorded_at.isoformat(), approval])


class P5OwnerAuthority:
    def __init__(self, *, read_original, read_ticket, reviewed_record, reviewed_ticket,
                 clock=None):
        # Only the trusted operator supplies these after comparing the original
        # instruction's target, operations, limits, expiry/end and revocation.
        # A Category permission trial also needs the original shop designation
        # and explicit permission to test its still-unverified effective rights.
        # A deserialized APPROVED field is deliberately not accepted here.
        if type(reviewed_record) is not OriginalOwnerRecord or not callable(read_original) or not callable(read_ticket):
            raise P5Stopped('P5_OWNER_APPROVAL_UNVERIFIED')
        self.read_original, self.read_ticket = read_original, read_ticket
        try:
            self.reviewed_digest = reviewed_record.digest
        except Exception:
            raise P5Stopped('P5_OWNER_APPROVAL_UNVERIFIED') from None
        self.ticket_digest = _digest(reviewed_ticket)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def verify_original(self, reference):
        try:
            current = self.read_original(reference)
            approval = current.approval
            now = self.clock()
            if (type(current) is not OriginalOwnerRecord or not current.body.strip()
                    or current.reference != reference or current.digest != self.reviewed_digest
                    or type(approval) is not OperatorApproval
                    or current.owner_ref != approval.owner_ref
                    or current.reference != approval.original_instruction_ref
                    or current.recorded_at.tzinfo is None
                    or not current.recorded_at <= approval.approved_at <= now < approval.expires_at
                    or approval.revoked is not False
                    or not approval.end_condition_ref.strip()
                    or approval.ticket_digest != self.ticket_digest
                    or _digest(self.read_ticket()) != self.ticket_digest):
                raise ValueError()
            return approval
        except Exception:
            raise P5Stopped('P5_OWNER_APPROVAL_UNVERIFIED') from None


class P5Checkpoint:
    def __init__(self, setup, *, required_bytes):
        self.setup, self.required_bytes = setup, required_bytes

    def __call__(self, runtime, reason):
        from modules.p5_setup import checkpoint
        if reason not in {'output', 'session-end', 'material-update'}:
            raise P5Stopped('P5_CHECKPOINT_REASON_INVALID')
        return checkpoint(runtime, setup=self.setup, checkpoint_id=uuid4().hex,
                          required_bytes=self.required_bytes)


class P5Operator:
    """Installed only by an explicitly approved trusted process initializer.

    There is no default initializer or module-path/config import option. The
    installed record still has to pass original-source and OS checks at start
    and on every send/output. Installation and real records remain live gates.
    """
    def __init__(self, *, authority, observer, credentials, checkpoint, approval_reference):
        from modules.p5_windows import WindowsP5Observer
        from modules.p5_live_adapter import P5ServiceCredentials
        if (type(authority) is not P5OwnerAuthority or type(observer) is not WindowsP5Observer
                or type(credentials) is not P5ServiceCredentials or type(checkpoint) is not P5Checkpoint
                or not isinstance(approval_reference, str) or not approval_reference.strip()):
            raise P5Stopped('P5_TRUSTED_OPERATOR_REQUIRED')
        self.authority, self.observer, self.credentials = authority, observer, credentials
        self.checkpoint, self.approval_reference = checkpoint, approval_reference

    def compose(self, scope):
        adapter = P5TrustedAdapter(authority=self.authority, observe=self.observer.observe,
            resolve_secrets=self.credentials, code_identity=P5CodeIdentity(), checkpoint=self.checkpoint)
        return adapter.compose(scope, approval_reference=self.approval_reference)


_installed_operator = None


def register_operator(operator):
    """Explicit in-process injection by the trusted initializer; never UI input."""
    global _installed_operator
    if type(operator) is not P5Operator:
        raise P5Stopped('P5_TRUSTED_OPERATOR_REQUIRED')
    if _installed_operator is not None and _installed_operator is not operator:
        raise P5Stopped('P5_OPERATOR_ALREADY_REGISTERED')
    _installed_operator = operator


class PendingP5Runtime:
    def __init__(self, scope, operator):
        self.scope, self.operator = scope, operator
        self.runtime = P5Runtime(scope)  # no permit or I/O

    def can_request_start(self):
        return type(self.operator) is P5Operator

    def start(self):
        if not self.can_request_start():
            raise P5Stopped('P5_TRUSTED_OPERATOR_REQUIRED')
        if self.runtime.permit is None:
            self.runtime = self.operator.compose(self.scope)
        self.runtime.start()

    def __getattr__(self, name):
        return getattr(self.runtime, name)


def configured_runtime(scope):
    return PendingP5Runtime(scope, _installed_operator)
