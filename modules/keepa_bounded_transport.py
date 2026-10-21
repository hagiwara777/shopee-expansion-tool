"""Bound every actual HTTP send for an explicitly budgeted Keepa 1.5 client.

No automatic retry or redirects. A send ceiling is not a monetary/token ceiling.
SDK parsing and candidate generation remain shared across marketplaces.
"""
import requests


def install_bounded_keepa_transport(api, budget, *, transport=None):
    send = requests.get if transport is None else transport
    failed = False

    def request_impl(request_type, payload, wait=True, raw_response=False, is_json=True):
        nonlocal failed
        if failed:
            raise RuntimeError('Keepa action stopped; explicit new action required')
        if request_type not in {'product', 'query', 'token'}:
            raise ValueError('Unsupported bounded Keepa endpoint')
        reservation = None
        try:
            if hasattr(budget, 'reserve_keepa_call'):
                reservation = budget.reserve_keepa_call(request_type, payload)
            else:
                budget.reserve_keepa_request()
            response = send(f'https://api.keepa.com/{request_type}/?', params=payload,
                            timeout=api._timeout, allow_redirects=False)
        except Exception:
            failed = True
            if reservation is not None:
                budget.fail_keepa_call(reservation)
            raise RuntimeError('Bounded Keepa send stopped') from None
        if reservation is not None:
            try:
                budget.complete_keepa_call(reservation, response.json(), response.status_code)
            except Exception:
                failed = True
                budget.fail_keepa_call(reservation)
                raise RuntimeError('Keepa consumption unverified; reservation retained') from None
        if response.status_code != 200:
            failed = True
            raise RuntimeError('Bounded Keepa acquisition failed; explicit retry required')
        if not is_json:
            return response
        try:
            data = response.json()
        except Exception:
            failed = True
            raise RuntimeError('Invalid bounded Keepa JSON') from None
        if not isinstance(data, dict):
            failed = True
            raise RuntimeError('Invalid bounded Keepa response')
        if 'tokensLeft' in data:
            api.tokens_left = data['tokensLeft']
            api.status.tokensLeft = data['tokensLeft']
        for key in ('refillIn', 'refillRate', 'timestamp'):
            if key in data:
                setattr(api.status, key, data[key])
        return response if raw_response else data

    def request(request_type, payload, wait=True, raw_response=False, is_json=True):
        # SG Continuous exposes this lock so legacy bounded sends and Core's
        # token/product pair cannot overlap on the same persistent request grant.
        call_guard = getattr(budget, 'core_keepa_call', None)
        if getattr(budget, 'has_core_keepa_concurrency_guard', False) and callable(call_guard):
            with call_guard():
                return request_impl(request_type, payload, wait, raw_response, is_json)
        return request_impl(request_type, payload, wait, raw_response, is_json)

    api._request = request
    return api
