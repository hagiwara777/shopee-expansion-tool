"""Legacy SG work-store API and schema; no migration to the P2 store."""
import sqlite3  # Existing callers/tests patch this shared sqlite3 module.
from modules.beta_work_store import BetaWorkStore, WorkStoreError as SGWorkError, STATES, encode, timestamp

SCHEMA = 'SG_INITIAL_BETA_WORK_V1'


class SGWorkStore(BetaWorkStore):
    SCHEMA = SCHEMA
    AUDIT_EVENTS = False

    @classmethod
    def create(cls, path, *, shop_id, marketplace='SG'):
        if marketplace != 'SG':
            raise SGWorkError('Legacy SG work store requires SG')
        return super().create(path, marketplace='SG', shop_id=shop_id)

    def __init__(self, path, *, shop_id, marketplace='SG'):
        if marketplace != 'SG':
            raise SGWorkError('Legacy SG work store requires SG')
        super().__init__(path, marketplace='SG', shop_id=shop_id)
