"""Finite P5-only adapters around existing clients; no default credential lookup.

All public factories require an active P5 runtime before touching credentials.
Injected HTTP is synthetic and cannot establish official catalog provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import json
import time
from pathlib import Path
from urllib.parse import urlsplit, quote

import requests

from modules.p5_runtime import P5Stopped
from modules.sg_live_validation import OpenAIValidationBudget
from modules.shopee_catalog_client import ShopeeCatalogClient, SHOPEE_PARTNER_BASE_URL


class P5KeepaBudget:
    def __init__(self, runtime):
        self.runtime = runtime
        self.balance = None
        self.discovered = set()

    def reserve_keepa_call(self, endpoint, payload):
        self.runtime.require_current()
        with self.runtime.ledger._lock:
            return self._reserve_keepa_call(endpoint, payload)

    def _reserve_keepa_call(self, endpoint, payload):
        self.runtime.require_current()
        scope = self.runtime.scope
        units = tokens = 0
        candidate_request = None
        if endpoint == 'token':
            if set(payload) - {'key'}:
                raise P5Stopped('P5_KEEPA_PARAMETERS_REFUSED')
        elif endpoint == 'product':
            permitted = {'key', 'domain', 'asin', 'stats', 'rating', 'history', 'stock', 'buybox', 'videos', 'aplus'}
            if (set(payload) - permitted or payload.get('domain') != 5
                    or any(payload.get(k, 0) != 0 for k in ('stock', 'buybox', 'videos', 'aplus'))
                    or payload.get('stats', 1) != 1 or payload.get('rating', 0) not in (0, 1)
                    or payload.get('history', 0) not in (0, 1)):
                raise P5Stopped('P5_KEEPA_PARAMETERS_REFUSED')
            asins = payload.get('asin', '').split(',')
            allowed = (self.runtime.candidates.allowed_products() if scope.preparation_limit
                       else set(scope.asins) | self.discovered)
            if (not asins or len(set(asins)) != len(asins) or not set(asins) <= allowed):
                raise P5Stopped('P5_KEEPA_PRODUCTS_OUTSIDE_SCOPE')
            units = len(asins)
            tokens = units * (1 + int(payload.get('rating', 0)))
            candidate_request = {'endpoint': 'product', 'asins': asins}
        elif endpoint == 'query':
            if set(payload) != {'key', 'domain', 'selection'} or payload.get('domain') != 5:
                raise P5Stopped('P5_KEEPA_PARAMETERS_REFUSED')
            selection = json.loads(payload['selection'])
            if selection not in [json.loads(q) for q in scope.finder_queries]:
                raise P5Stopped('P5_FINDER_QUERY_NOT_APPROVED')
            if scope.preparation_limit and any(r.get('selection') == selection for r in
                    self.runtime.candidates.data['requests'].values()):
                raise P5Stopped('P5_FINDER_ALREADY_EXECUTED')
            candidate_request = {'endpoint': 'query', 'selection': selection}
            tokens = 1 + (selection['perPage'] + 4) // 5
        else:
            raise P5Stopped('P5_KEEPA_ENDPOINT_REFUSED')
        if tokens and (type(self.balance) is not int or self.balance < tokens):
            raise P5Stopped('P5_KEEPA_TOKEN_BALANCE_INSUFFICIENT')
        return self.runtime.ledger.reserve('keepa', units=units, tokens=tokens,
            candidate_request=candidate_request if scope.preparation_limit else None)

    def complete_keepa_call(self, reservation, data, status):
        ledger = self.runtime.ledger
        row = next(r for r in ledger.data['reservations'] if r['id'] == reservation)
        actual = data.get('tokensConsumed') if isinstance(data, dict) else None
        balance = data.get('tokensLeft') if isinstance(data, dict) else None
        if (type(actual) is not int or actual < 0
                or type(balance) is not int):
            raise P5Stopped('P5_KEEPA_CONSUMPTION_UNKNOWN')
        success = status == 200 and not data.get('error') and actual <= row['tokens']
        request = ledger.data.get('candidates', {}).get('requests', {}).get(reservation, {})
        finder_asins = None
        if success and (request.get('endpoint') == 'query' or 'asinList' in data):
            found = data['asinList']
            maximum = request.get('selection', {}).get('perPage', 50)
            if (not isinstance(found, list) or len(found) > maximum or len(found) != len(set(found))
                    or any(not isinstance(a, str) or len(a) != 10 or not a.isalnum() or a != a.upper() for a in found)):
                raise P5Stopped('P5_FINDER_RESPONSE_INVALID')
            self.discovered.update(found)
            if self.runtime.scope.preparation_limit:
                if request.get('endpoint') != 'query':
                    raise P5Stopped('P5_UNEXPECTED_FINDER_RESPONSE')
                finder_asins = found
        ledger.finish(reservation, success=success, actual_tokens=actual, finder_asins=finder_asins)
        self.balance = balance
        if not success:
            raise P5Stopped('P5_KEEPA_RESPONSE_FAILED')

    def fail_keepa_call(self, reservation):
        ledger = self.runtime.ledger
        row = next(r for r in ledger.data['reservations'] if r['id'] == reservation)
        if row['state'] == 'RESERVED':
            ledger.finish(reservation, success=False)


class P5CatalogPolicy:
    def __init__(self, runtime):
        self.runtime = runtime

    def before(self, client, path, parameters):
        self.runtime.require_current()
        scope = self.runtime.scope
        if (client.marketplace != scope.marketplace or str(client.credentials.shop_id) != scope.shop_id
                or client.base_url != SHOPEE_PARTNER_BASE_URL
                or (not self.runtime.permit.offline_test and not client.uses_default_transport)):
            raise P5Stopped('P5_CATALOG_IDENTITY_MISMATCH')
        expected = {
            '/api/v2/product/get_category': {'language'},
            '/api/v2/product/get_brand_list': {'category_id', 'status', 'offset', 'page_size'},
            '/api/v2/product/get_attribute_tree': {'category_id_list', 'language'},
        }
        if path not in expected or set(parameters) != expected[path]:
            raise P5Stopped('P5_CATALOG_ENDPOINT_REFUSED')
        if 'category_id' in parameters:
            if (int(parameters['category_id']) not in scope.category_ids or parameters['page_size'] != '100'
                    or parameters['status'] != '1' or int(parameters['offset']) < 0):
                raise P5Stopped('P5_BRAND_PAGING_REFUSED')
        if 'category_id_list' in parameters:
            ids = [int(v) for v in parameters['category_id_list'].split(',')]
            if not ids or not set(ids) <= set(scope.category_ids):
                raise P5Stopped('P5_ATTRIBUTE_SCOPE_REFUSED')
        if 'language' in parameters and parameters['language'] != 'en':
            raise P5Stopped('P5_CATALOG_LANGUAGE_REFUSED')
        return self.runtime.ledger.reserve('shopee')

    def finish(self, reservation, *, success):
        self.runtime.ledger.finish(reservation, success=success)


class P5HTTP:
    """One physical attempt per call. Caller retries hit the sticky run stop.

    Only the image analyzer streams bodies; its existing size/pixel/deadline
    checks remain authoritative. No global requests/urllib monkey patching.
    """
    HOSTS = {'bridge': {'sheets.googleapis.com'}, 'auth': {'oauth2.googleapis.com'},
             'image': {'m.media-amazon.com', 'images-na.ssl-images-amazon.com'},
             'openai': {'api.openai.com'}}

    def __init__(self, runtime, kind, *, session=None):
        self.runtime, self.kind = runtime, kind
        self._session = session if session is not None else requests.Session()
        # No urllib3 automatic retries in production P5 sessions.
        if session is None:
            self._session.trust_env = False
            self._session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))
        elif not runtime.permit or not runtime.permit.offline_test:
            raise P5Stopped('P5_SYNTHETIC_HTTP_REQUIRES_TEST_PERMIT')

    def request(self, method, url, **kwargs):
        self.runtime.require_current()
        if self.kind == 'openai' and not self.runtime.permit.offline_test and not self.runtime.permit.openai_pricing_ref:
            raise P5Stopped('P5_CURRENT_OPENAI_PRICING_UNVERIFIED')
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in self.HOSTS[self.kind]
                or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.fragment
                or method.upper() != ('POST' if self.kind in {'auth', 'openai'} else 'GET')):
            raise P5Stopped('P5_HTTP_ROUTE_REFUSED')
        if self.kind == 'auth' and parsed.path != '/token':
            raise P5Stopped('P5_AUTH_ENDPOINT_REFUSED')
        if self.kind == 'openai' and url != 'https://api.openai.com/v1/responses':
            raise P5Stopped('P5_OPENAI_ENDPOINT_REFUSED')
        kwargs['allow_redirects'] = False
        kwargs['timeout'] = (5, 20)
        reservation = None
        try:
            usd = Decimal(0)
            if self.kind == 'openai':
                usd = P5OpenAIBudget.check_payload(self.runtime.scope, kwargs.get('json', {}))
            reservation = self.runtime.ledger.reserve(self.kind, usd=usd)
            response = self._session.request(method, url, **kwargs)
            if response.status_code != 200:
                raise P5Stopped('P5_HTTP_RESPONSE_FAILED')
            if self.kind == 'image' and kwargs.get('stream'):
                return P5ImageResponse(response, self.runtime.ledger, reservation)
            if self.kind != 'image':
                body = response.json()
                if not isinstance(body, dict) or body.get('error'):
                    raise P5Stopped('P5_HTTP_BODY_INVALID')
            self.runtime.ledger.finish(reservation, success=True)
            return response
        except Exception:
            if reservation is not None:
                row = next(r for r in self.runtime.ledger.data['reservations'] if r['id'] == reservation)
                if row['state'] == 'RESERVED':
                    self.runtime.ledger.finish(reservation, success=False)
            raise P5Stopped('P5_HTTP_ACTION_STOPPED') from None

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)

    def close(self):
        close = getattr(self._session, 'close', None)
        if close is not None:
            close()


class P5ImageResponse:
    def __init__(self, response, ledger, reservation):
        self.response, self.ledger, self.reservation = response, ledger, reservation

    def __getattr__(self, name):
        return getattr(self.response, name)

    def iter_content(self, chunk_size):
        total, started = 0, time.monotonic()
        try:
            for chunk in self.response.iter_content(chunk_size=chunk_size):
                total += len(chunk)
                if total > 5 * 1024 * 1024 or time.monotonic() - started > 30:
                    raise P5Stopped('P5_IMAGE_SIZE_TIMEOUT')
                yield chunk
            self.ledger.finish(self.reservation, success=True)
        except Exception:
            self._fail_pending()
            raise P5Stopped('P5_IMAGE_ACQUISITION_STOPPED') from None

    def _fail_pending(self):
        row = next(r for r in self.ledger.data['reservations'] if r['id'] == self.reservation)
        if row['state'] == 'RESERVED':
            self.ledger.finish(self.reservation, success=False)

    def close(self):
        try:
            self._fail_pending()
        finally:
            self.response.close()


class P5OpenAIBudget(OpenAIValidationBudget):
    """Reuse the price calculator; the shared P5 ledger owns reservations."""
    def __init__(self, runtime):
        self.runtime = runtime
        # The existing image inspector checks this nominal budget type.
        super().__init__(limit_usd=Decimal('1'))

    @staticmethod
    def check_payload(scope, payload):
        if payload.get('model') not in scope.openai_models:
            raise P5Stopped('P5_MODEL_NOT_APPROVED')
        cost = OpenAIValidationBudget.ceiling(payload)
        images = 0
        def copy_text(v):
            nonlocal images
            if isinstance(v, dict):
                if v.get('type') == 'input_image':
                    images += 1
                    return {'type': 'input_image'}
                return {k: copy_text(c) for k, c in v.items()}
            return [copy_text(c) for c in v] if isinstance(v, list) else v
        bound = len(json.dumps(copy_text(payload), ensure_ascii=False).encode('utf-8')) + 8192 + images * 36000
        if (bound > scope.openai_input_bound or payload['max_output_tokens'] > scope.openai_output_tokens
                or images > scope.openai_images):
            raise P5Stopped('P5_OPENAI_INPUT_OUTPUT_LIMIT')
        return cost

    def reserve(self, payload):
        # BudgetedOpenAISession invokes this; P5HTTP reserves at physical send.
        self.runtime.require_current()
        self.check_payload(self.runtime.scope, payload)


@dataclass(frozen=True, repr=False)
class P5Secrets:
    """Resolved only after explicit action. Never serialized into the scope."""
    credential_ref: str
    marketplace: str
    shop_id: str
    shopee_credentials: object = field(repr=False)
    keepa_key: str = field(default='', repr=False)
    openai_key: str = field(default='', repr=False)
    google_credential_file: str = field(default='', repr=False)


def make_catalog_client(runtime, secrets, *, request_json=None):
    runtime.require_current()
    if (not isinstance(secrets, P5Secrets) or secrets.credential_ref != runtime.scope.credential_ref
            or secrets.marketplace != runtime.scope.marketplace
            or secrets.shop_id != runtime.scope.shop_id
            or str(secrets.shopee_credentials.shop_id) != secrets.shop_id):
        raise P5Stopped('P5_CREDENTIAL_REFERENCE_MISMATCH')
    if request_json is not None and not runtime.permit.offline_test:
        raise P5Stopped('P5_MOCK_CATALOG_REFUSED')
    client = ShopeeCatalogClient(secrets.shopee_credentials, marketplace=runtime.scope.marketplace,
        request_json=request_json, request_policy=P5CatalogPolicy(runtime))
    client.ledger = runtime.ledger
    return client


def make_keepa_client(runtime, secrets, *, transport=None):
    runtime.require_current()
    if (not isinstance(secrets, P5Secrets) or secrets.credential_ref != runtime.scope.credential_ref
            or secrets.marketplace != runtime.scope.marketplace
            or secrets.shop_id != runtime.scope.shop_id):
        raise P5Stopped('P5_CREDENTIAL_REFERENCE_MISMATCH')
    if transport is not None and not runtime.permit.offline_test:
        raise P5Stopped('P5_MOCK_KEEPA_REFUSED')
    from modules.cache import KeepaCache
    from modules.keepa_client import KeepaExpansionClient
    from modules.keepa_bounded_transport import install_bounded_keepa_transport
    import keepa
    cache_path = runtime.scope.directory / 'keepa.sqlite3'
    if not cache_path.is_file():
        raise P5Stopped('P5_CACHE_INSTALLATION_REQUIRED')
    api = keepa.Keepa(secrets.keepa_key, check_key=False, logging_level='CRITICAL')
    install_bounded_keepa_transport(api, P5KeepaBudget(runtime), transport=transport)
    class ScopedKeepaClient(KeepaExpansionClient):
        def verify_products_by_asin(self, asins, **kwargs):
            runtime.require_current()
            if runtime.scope.preparation_limit and not set(asins) <= runtime.candidates.allowed_products():
                raise P5Stopped('P5_KEEPA_PRODUCTS_OUTSIDE_SCOPE')
            return super().verify_products_by_asin(asins, **kwargs)

        def find_related_products(self, source_asin, search_pages, search_mode='strict', filter_criteria=None):
            runtime.require_current()
            if source_asin not in runtime.scope.asins or search_pages != 1 or search_mode != 'strict':
                raise P5Stopped('P5_EXPANSION_PLAN_REFUSED')
            return super().find_related_products(source_asin, search_pages, search_mode, filter_criteria)

        def _diagnose_and_fallback(self, source, original_error):
            # The legacy diagnostic includes a resend of the original query.
            # Exact-parameter checks alone cannot distinguish that automatic
            # resend from the one planned Finder request.
            return [], 'P5では自動診断・fallbackを実行しません。取得条件と残枠を確認してください。', []
    return ScopedKeepaClient(domain='JP', api=api, cache=KeepaCache(cache_path))


def make_image_inspector(runtime, secrets, *, api_session=None, image_session=None):
    runtime.require_current()
    if (not isinstance(secrets, P5Secrets) or secrets.credential_ref != runtime.scope.credential_ref
            or secrets.marketplace != runtime.scope.marketplace or secrets.shop_id != runtime.scope.shop_id):
        raise P5Stopped('P5_CREDENTIAL_REFERENCE_MISMATCH')
    from modules.weapon_image_inspection import BudgetedLiveWeaponImageInspector
    class ScopedInspector(BudgetedLiveWeaponImageInspector):
        def inspect(self, evidence):
            runtime.require_current()
            allowed = ({a for s in runtime.candidates.data['selections'].values() for a in s['asins']}
                       if runtime.scope.preparation_limit else runtime.scope.asins)
            if evidence.text.candidate_asin not in allowed:
                raise P5Stopped('P5_IMAGE_PRODUCT_OUTSIDE_SCOPE')
            return super().inspect(evidence)
    return ScopedInspector(api_key=secrets.openai_key, budget=P5OpenAIBudget(runtime),
        api_session=P5HTTP(runtime, 'openai', session=api_session),
        image_session=P5HTTP(runtime, 'image', session=image_session))


def make_category_provider(runtime, secrets, *, session=None):
    runtime.require_current()
    if (not isinstance(secrets, P5Secrets) or secrets.credential_ref != runtime.scope.credential_ref
            or secrets.marketplace != runtime.scope.marketplace or secrets.shop_id != runtime.scope.shop_id):
        raise P5Stopped('P5_CREDENTIAL_REFERENCE_MISMATCH')
    from modules.category_ai_openai import OpenAIResponsesCategoryProvider
    class ScopedProvider(OpenAIResponsesCategoryProvider):
        def select(self, request, profile):
            runtime.require_current()
            allowed = ({a for s in runtime.candidates.data['selections'].values() for a in s['asins']}
                       if runtime.scope.preparation_limit else runtime.scope.asins)
            if request.product.marketplace != runtime.scope.marketplace or request.product.asin not in allowed:
                raise P5Stopped('P5_AI_PRODUCT_OUTSIDE_SCOPE')
            return super().select(request, profile)
    return ScopedProvider(secrets.openai_key, session=P5HTTP(runtime, 'openai', session=session))


class P5BridgeTransport:
    """Reuse Bridge parsing; bind all refresh attempts to the P5 auth transport.

    No ADC discovery or metadata-server fallback. An approved credential file
    reference must be provided by the trusted integration, never by daily UI.
    """
    def __init__(self, runtime, *, credential_file, spreadsheet_id):
        self.runtime = runtime
        self.credential_file, self.spreadsheet_id = credential_file, spreadsheet_id

    def read_values(self, spreadsheet_id, cell_range):
        self.runtime.require_current()
        if (not spreadsheet_id or spreadsheet_id != self.runtime.scope.bridge_spreadsheet_id
                or spreadsheet_id != self.spreadsheet_id or cell_range != 'A:C'):
            raise P5Stopped('P5_BRIDGE_BINDING_MISMATCH')
        import google.auth
        from google.auth.transport.requests import Request
        # Do not hand arbitrary external-account/executable configurations to
        # google-auth. Only these two local credential formats are supported.
        data = json.loads(Path(self.credential_file).read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('type') not in {'authorized_user', 'service_account'}:
            raise P5Stopped('P5_GOOGLE_CREDENTIAL_TYPE_REFUSED')
        request = Request(session=P5HTTP(self.runtime, 'auth'))
        credentials, _ = google.auth.load_credentials_from_dict(data,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'], request=request)
        headers = {}
        url = f'https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe="")}/values/A%3AC'
        credentials.before_request(request, 'GET', url, headers)
        return P5HTTP(self.runtime, 'bridge').get(url, headers=headers,
            params={'majorDimension': 'ROWS'}).json()
