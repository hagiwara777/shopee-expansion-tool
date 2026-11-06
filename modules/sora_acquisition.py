"""Session-only, input-bound acquisition; every continuation is a separate click."""

from copy import deepcopy
from dataclasses import dataclass, field

from modules.asin_resolver import verify_preview_rows
from modules.sp_api_catalog import CATALOG_BATCH_SIZE, SpApiCatalogError, planned_catalog_calls


class _CapturedBatch:
    provider_name = 'sp_api_catalog_2022_04_01'
    product_field_prefix = 'spapi'
    verification_label = 'SP_API_VERIFIED'
    not_found_label = 'SP_API_NOT_FOUND'

    def __init__(self, products):
        self.products = products

    def verify_products_by_asin(self, asins):
        return self.products


@dataclass
class SoraAcquisition:
    rows: tuple[dict, ...]
    marketplace: str
    input_files: tuple[str, ...]
    completed_asins: set[str] = field(default_factory=set, init=False)
    _verified: dict[str, dict] = field(default_factory=dict, init=False, repr=False)
    auth_calls: int = field(default=0, init=False)
    catalog_calls: int = field(default=0, init=False)
    attempts: int = field(default=0, init=False)
    error: str = field(default='', init=False)

    def __post_init__(self):
        self.rows = tuple(deepcopy(self.rows))
        if self.marketplace not in {'SG', 'PH'}:
            raise ValueError('対象国を確認してください。')
        planned_catalog_calls(self.asins)
        if not self.rows or len({r['row_id'] for r in self.rows}) != len(self.rows):
            raise ValueError('取得対象の行が不正です。')

    @property
    def asins(self):
        return tuple(dict.fromkeys(row['asin'] for row in self.rows))

    @property
    def pending_asins(self):
        return tuple(asin for asin in self.asins if asin not in self.completed_asins)

    @property
    def verified_rows(self):
        return [self._verified[row['row_id']] for row in self.rows if row['row_id'] in self._verified]

    @property
    def complete(self):
        return not self.pending_asins

    def advance(self, client):
        if self.complete:
            raise ValueError('取得は完了しています。')
        pending = self.pending_asins
        self.error = ''
        self.attempts += 1

        def capture(batch, products):
            if (not batch or len(batch) > CATALOG_BATCH_SIZE or len(set(batch)) != len(batch)
                    or not set(batch) <= set(self.pending_asins) or not set(products) <= set(batch)):
                raise SpApiCatalogError('取得結果の対象が一致しないため停止しました。')
            batch_rows = [r for r in self.rows if r['asin'] in batch]
            verified = verify_preview_rows(batch_rows, _CapturedBatch(products))
            self._verified.update({r['row_id']: r for r in verified})
            self.completed_asins.update(batch)

        try:
            client.verify_products_by_asin(pending, on_batch=capture)
            if not self.complete:
                raise SpApiCatalogError('取得結果の完了を確認できません。残りの商品は未確認です。')
        except SpApiCatalogError as error:
            self.error = str(error)
        except Exception:
            self.error = '商品情報の取得を停止しました。取得済みの商品は保持しています。'
        finally:
            self.auth_calls += client.auth_calls
            self.catalog_calls += client.catalog_calls
