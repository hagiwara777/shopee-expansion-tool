"""Offline transport failures exercise the same batching used by the UI."""

from types import SimpleNamespace
from datetime import datetime, timezone

import pytest
import requests

from modules.asin_resolver import preview_candidates, verify_preview_rows
from modules.sora_acquisition import SoraAcquisition
from modules.sora_run import evaluate_sora_run, prepare_sora_run
from modules.sp_api_catalog import JP_MARKETPLACE, SpApiCatalogClient, SpApiCredentials


CREDS = SpApiCredentials('test-client', 'test-only-secret', 'test-only-refresh')


def item(asin):
    return {'asin': asin, 'attributes': {}, 'summaries': [{
        'marketplaceId': JP_MARKETPLACE, 'itemName': '普通のタオル',
        'brand': '試験ブランド', 'browseClassification': {'displayName': 'タオル'}}]}


class Transport:
    def __init__(self, *, fail_batch=None, missing=(), malformed=False):
        self.requests = []
        self.fail_batch = fail_batch
        self.missing = set(missing)
        self.malformed = malformed
        self.batches = []

    def request(self, method, url, **kwargs):
        self.requests.append(method)
        assert kwargs['allow_redirects'] is False
        if method == 'POST':
            payload = {'access_token': 'test-only-token'}
        else:
            batch = tuple(kwargs['params']['identifiers'].split(','))
            self.batches.append(batch)
            if len(self.batches) == self.fail_batch:
                if self.malformed:
                    return SimpleNamespace(status_code=200, json=lambda: {'items': [item(batch[0]), item('B999999999')]})
                raise requests.Timeout('private raw error must not be shown')
            payload = {'items': [item(a) for a in batch if a not in self.missing]}
        return SimpleNamespace(status_code=200, json=lambda: payload)


def client(transport):
    clock = [0.0]
    return SpApiCatalogClient(CREDS, transport=transport, monotonic=lambda: clock[0],
                              sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))


def acquisition(asins):
    return SoraAcquisition(tuple(preview_candidates('\n'.join(asins))), 'SG', ('test.csv',))


def test_500_partial_failure_retains_validated_batches_and_resume_sends_remaining_only():
    asins = tuple(f'B{i:09d}' for i in range(500))
    progress = acquisition(asins)
    first = Transport(fail_batch=2, missing=(asins[3],))
    progress.advance(client(first))
    assert len(first.requests) == 3  # 1 auth, 1 good response, 1 failed send; no retries
    assert not progress.complete and progress.pending_asins == asins[20:]
    assert len(progress.verified_rows) == 20
    assert progress.verified_rows[3]['verification'] == 'SP_API_NOT_FOUND'
    saved = progress.verified_rows[0].copy()
    assert 'private raw error' not in progress.error
    assert (progress.auth_calls, progress.catalog_calls) == (1, 2)
    second = Transport()
    progress.advance(client(second))
    assert progress.complete and len(progress.verified_rows) == 500
    assert tuple(a for batch in second.batches for a in batch) == asins[20:]
    assert progress.verified_rows[0] == saved
    assert (progress.auth_calls, progress.catalog_calls, progress.attempts) == (2, 26, 2)
    run = prepare_sora_run(progress.verified_rows, marketplace='SG', auth_calls=progress.auth_calls,
                           catalog_calls=progress.catalog_calls)
    assert run.unverified_row_count == 1 and len(run.candidates.rows) == 499
    with pytest.raises(ValueError, match='完了'):
        progress.advance(client(second))
    assert len(second.requests) == 25


def test_invalid_second_batch_commits_none_of_that_batch():
    asins = tuple(f'B{i:09d}' for i in range(41))
    progress = acquisition(asins)
    transport = Transport(fail_batch=2, malformed=True)
    progress.advance(client(transport))
    assert len(progress.verified_rows) == 20
    assert progress.pending_asins == asins[20:]
    assert 'ASIN' in progress.error


def test_failure_before_first_response_has_no_completed_or_reusable_facts():
    progress = acquisition(['B000000001'])
    transport = Transport(fail_batch=1)
    progress.advance(client(transport))
    assert progress.pending_asins == ('B000000001',)
    assert progress.verified_rows == []
    assert (progress.auth_calls, progress.catalog_calls) == (1, 1)


@pytest.mark.parametrize('marketplace', ['SG', 'PH'])
def test_same_fact_handoff_and_safety_results_as_original_resolver(marketplace, monkeypatch):
    # Equal-input regression, not a claim of a new real-product acquisition.
    asins = ['B000000001', 'B000000002', 'B000000003']
    class FixedDatetime:
        @staticmethod
        def now(tz):
            return datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
    monkeypatch.setattr('modules.sp_api_catalog.datetime', FixedDatetime)
    class SafetyTransport(Transport):
        def request(self, method, url, **kwargs):
            response = super().request(method, url, **kwargs)
            payload = response.json()
            if method == 'GET':
                payload['items'][1]['attributes'] = {'bullet_point': [{'value': '全成分：水、香料、サリチル酸'}]}
                payload['items'][2]['attributes'] = {'bullet_point': [{'value': '医薬部外品'}]}
            return SimpleNamespace(status_code=200, json=lambda: payload)
    original = verify_preview_rows(preview_candidates('\n'.join(asins)), client(SafetyTransport()))
    progress = acquisition(asins)
    progress.marketplace = marketplace
    progress.advance(client(SafetyTransport()))
    original_run = prepare_sora_run(original, marketplace=marketplace, auth_calls=1, catalog_calls=1)
    new_run = prepare_sora_run(progress.verified_rows, marketplace=marketplace, auth_calls=1, catalog_calls=1)
    assert original_run.candidates == new_run.candidates
    assert original_run.ingredient_safety == new_run.ingredient_safety
    assert original_run.product_text_safety == new_run.product_text_safety
    original_result = evaluate_sora_run(original_run)
    new_result = evaluate_sora_run(new_run)
    assert [(r.candidate.candidate_asin, r.final_eligibility, r.reason_codes) for r in original_result.rows] == [
        (r.candidate.candidate_asin, r.final_eligibility, r.reason_codes) for r in new_result.rows]
    assert (new_result.eligible_count, new_result.review_count, new_result.exclude_count) == (1, 1, 1)
