"""P5-only, bounded discovery and durable human selection in the existing ledger.

These records bind material, not human identity or official API provenance.
No credentials, network, new database, permit loader, or Safety decisions here.
"""
import copy
import json
import re
from functools import wraps

from modules.sg_continuous_runtime import _digest


def stop(reason):
    from modules.p5_runtime import P5Stopped
    raise P5Stopped(reason)


def validate_discovery_scope(scope):
    if (type(scope.preparation_limit) is not int or not 0 <= scope.preparation_limit <= 50
            or type(scope.resolver_inputs) is not tuple
            or (scope.resolver_inputs and not scope.preparation_limit)):
        stop('P5_SELECTION_PLAN_INVALID')
    inputs = []
    for raw in scope.resolver_inputs:
        value = json.loads(raw)
        if (not isinstance(value, dict) or set(value) != {'source_id', 'input_title', 'origin'}
                or any(not isinstance(v, str) or not v.strip() for v in value.values())
                or not re.fullmatch(r'R[0-9]{4}', value['source_id'])):
            stop('P5_RESOLVER_INPUT_INVALID')
        inputs.append(value['source_id'])
    if len(inputs) != len(set(inputs)):
        stop('P5_RESOLVER_INPUT_AMBIGUOUS')
    if scope.preparation_limit and len(scope.finder_queries) > 1:
        stop('P5_ONE_FINDER_PAGE_REQUIRED')


def validate_saved_candidates(ledger):
    data = ledger.data['candidates']
    if (not isinstance(data, dict) or set(data) != {'requests', 'finder', 'proposals', 'batches', 'selections'}
            or any(not isinstance(data[k], dict) for k in ('requests', 'finder', 'batches', 'selections'))
            or not isinstance(data['proposals'], list)):
        stop('P5_CANDIDATE_LEDGER_INVALID')
    reservations = {r['id']: r for r in ledger.data['reservations']}
    queries = []
    for rid, request in data['requests'].items():
        if rid not in reservations or reservations[rid]['kind'] != 'keepa':
            stop('P5_DISCOVERY_RESERVATION_MISSING')
        if request['endpoint'] == 'query':
            if request['selection'] not in [json.loads(q) for q in ledger.grant.finder_queries]:
                stop('P5_FINDER_QUERY_NOT_APPROVED')
            queries.append(_digest(request['selection']))
        elif request['endpoint'] != 'product':
            stop('P5_DISCOVERY_REQUEST_INVALID')
    if len(queries) != len(set(queries)):
        stop('P5_FINDER_ALREADY_EXECUTED')
    for rid, found in data['finder'].items():
        request = data['requests'].get(rid, {})
        if (request.get('endpoint') != 'query' or reservations[rid]['state'] != 'COMPLETE'
                or not isinstance(found, list) or len(found) > request['selection']['perPage']
                or len(found) != len(set(found))
                or any(not isinstance(a, str) or not re.fullmatch('[A-Z0-9]{10}', a) for a in found)):
            stop('P5_FINDER_RECEIPT_INVALID')
    allowed_sources = {json.loads(v)['source_id']: json.loads(v) for v in ledger.grant.resolver_inputs}
    for row in data['proposals']:
        _require_resolver_source(row, allowed_sources)
    if len({r['asin'] for r in data['proposals']}) > ledger.grant.preparation_limit:
        stop('P5_RESOLVER_PROPOSAL_LIMIT')
    selected = []
    for bid, batch in data['batches'].items():
        if bid != _digest(batch) or batch['source_type'] not in {'EXPANSION', 'RESOLVER'}:
            stop('P5_CANDIDATE_BATCH_CHANGED')
    for bid, selection in data['selections'].items():
        batch = data['batches'].get(bid)
        if (batch is None or not selection['asins'] or len(selection['asins']) != len(set(selection['asins']))
                or not set(selection['asins']) <= {_asin(r) for r in batch['rows']}
                or not selection['reviewer'].strip() or not selection['note'].strip()
                or selection['identity'] != ('CONFIRMED' if batch['source_type'] == 'RESOLVER' else 'NOT_APPLICABLE')):
            stop('P5_SELECTION_RECORD_INVALID')
        selected.extend(selection['asins'])
    if len(set(selected)) > ledger.grant.preparation_limit:
        stop('P5_PREPARATION_LIMIT_EXCEEDED')


def _asin(row):
    return row.get('candidate_asin') or row.get('asin')


def _require_resolver_source(row, inputs):
    source = inputs.get(row.get('source_id'))
    if (source is None or row.get('input_title') != source['input_title']
            or not isinstance(row.get('asin'), str) or not re.fullmatch('[A-Z0-9]{10}', row['asin'])
            or row.get('source_id_known') is False):
        stop('P5_RESOLVER_SOURCE_OUTSIDE_SCOPE')


def _locked(action):
    """Use the ledger's existing process/thread lease for selection writes too."""
    @wraps(action)
    def run(self, *args, **kwargs):
        self.runtime.require_current()
        with self.runtime.ledger._lock:
            return action(self, *args, **kwargs)
    return run


class P5Candidates:
    def __init__(self, runtime):
        self.runtime = runtime

    @property
    def data(self):
        self.runtime.require_current()
        if not self.runtime.scope.preparation_limit:
            stop('P5_TWO_STAGE_SCOPE_REQUIRED')
        return self.runtime.ledger.data['candidates']

    def allowed_products(self):
        d = self.data
        return (set(self.runtime.scope.asins) | {a for found in d['finder'].values() for a in found}
                | {r['asin'] for r in d['proposals']})

    @_locked
    def propose_resolver(self, rows, *, human_confirmed, reviewer, note):
        """Human chooses bounded detail targets; existence is not identity proof."""
        self._human(human_confirmed, reviewer, note)
        rows = copy.deepcopy(list(rows))
        d = self.data
        inputs = {json.loads(v)['source_id']: json.loads(v) for v in self.runtime.scope.resolver_inputs}
        if not rows:
            stop('P5_EXPLICIT_SELECTION_REQUIRED')
        proposals = copy.deepcopy(d['proposals'])
        for row in rows:
            _require_resolver_source(row, inputs)
            if row.get('parse_status') == 'UNKNOWN' or row.get('identity_status') in {'UNKNOWN', 'MISMATCH'}:
                stop('P5_RESOLVER_IDENTITY_UNRESOLVED')
            proposal = {k: row[k] for k in ('source_id', 'input_title', 'asin')}
            proposal.update(origin=inputs[row['source_id']]['origin'], reviewer=reviewer.strip(), note=note.strip())
            if not any(all(p[k] == proposal[k] for k in ('source_id', 'input_title', 'asin')) for p in proposals):
                proposals.append(proposal)
        if len({p['asin'] for p in proposals}) > self.runtime.scope.preparation_limit:
            stop('P5_RESOLVER_PROPOSAL_LIMIT')
        d['proposals'] = proposals
        self.runtime.ledger.persist()

    @_locked
    def offer(self, source_type, rows, *, filter_criteria=None):
        """Record the actual producer material; never silently select any row."""
        d = self.data
        rows = copy.deepcopy(list(rows))
        if not rows or len({_asin(r) for r in rows}) != len(rows):
            stop('P5_UNIQUE_CANDIDATE_BATCH_REQUIRED')
        found = {a for values in d['finder'].values() for a in values}
        for row in rows:
            if source_type == 'EXPANSION':
                if (_asin(row) not in found or row.get('seed_asin') not in self.runtime.scope.asins
                        or row.get('source') != 'keepa_product_finder_strict'):
                    stop('P5_EXPANSION_RESULT_OUTSIDE_SCOPE')
            elif source_type == 'RESOLVER':
                if (row.get('status') != 'FOUND' or row.get('verification') != 'KEEPA_VERIFIED'
                        or row.get('identity_status') in {'UNKNOWN', 'MISMATCH'}
                        or not any(all(row.get(k) == p[k] for k in ('source_id', 'input_title', 'asin'))
                                   for p in d['proposals'])):
                    stop('P5_RESOLVER_IDENTITY_UNRESOLVED')
            else:
                stop('P5_SOURCE_TYPE_INVALID')
        batch = {'source_type': source_type, 'rows': rows}
        if filter_criteria is not None and filter_criteria.active:
            from modules.candidate_filters import partition_rows
            if len(partition_rows(rows, None, filter_criteria).matched_rows) != len(rows):
                stop('P5_FILTER_SELECTION_REQUIRED')
            batch['filter_criteria'] = filter_criteria.to_dict()
        bid = _digest(batch)
        if bid not in d['batches']:
            d['batches'][bid] = batch
            self.runtime.ledger.persist()
        return bid

    @staticmethod
    def _human(confirmed, reviewer, note):
        if (confirmed is not True or not isinstance(reviewer, str) or not reviewer.strip()
                or not isinstance(note, str) or not note.strip()):
            stop('P5_EXPLICIT_HUMAN_SELECTION_REQUIRED')

    @_locked
    def select(self, bid, asins, *, human_confirmed, reviewer, note, identity='UNKNOWN'):
        self._human(human_confirmed, reviewer, note)
        d = self.data
        batch = d['batches'].get(bid)
        asins = list(asins)
        if (batch is None or not asins or len(asins) != len(set(asins))
                or not set(asins) <= {_asin(r) for r in batch['rows']}):
            stop('P5_SELECTION_OUTSIDE_BATCH')
        if batch['source_type'] == 'RESOLVER' and identity != 'CONFIRMED':
            stop('P5_RESOLVER_IDENTITY_UNRESOLVED')
        previous = d['selections'].get(bid)
        if previous:
            if set(previous['asins']) != set(asins):
                stop('P5_SELECTION_ALREADY_FIXED')
            return
        for old_bid in d['selections']:
            old_batch = d['batches'][old_bid]
            if (old_batch['source_type'] == batch['source_type'] and
                    (batch['source_type'] == 'EXPANSION' or
                     {r['source_id'] for r in old_batch['rows']} & {r['source_id'] for r in batch['rows']})):
                stop('P5_SELECTION_ALREADY_FIXED')
        total = set(asins) | {a for s in d['selections'].values() for a in s['asins']}
        if len(total) > self.runtime.scope.preparation_limit:
            stop('P5_PREPARATION_LIMIT_EXCEEDED')
        # One product cannot acquire contradictory source histories across batches.
        if any(set(asins) & set(s['asins']) for s in d['selections'].values()):
            stop('P5_PRODUCT_ALREADY_SELECTED')
        d['selections'][bid] = {'asins': asins, 'reviewer': reviewer.strip(), 'note': note.strip(),
            'identity': identity if batch['source_type'] == 'RESOLVER' else 'NOT_APPLICABLE'}
        self.runtime.ledger.persist()

    @_locked
    def handoff(self, bid, *, rows_override=None):
        """Rebuild final Candidate and sidecars together, using existing validators."""
        from modules.prelisting_candidate_csv import (expansion_rows_to_prelisting_candidates,
            resolver_rows_to_prelisting_candidates, rows_to_prelisting_candidate_csv)
        from modules.ingredient_safety import facts_for_candidate_rows, rows_to_ingredient_safety_sidecar
        from modules.product_text_safety import (facts_for_candidate_rows as text_facts,
            rows_to_product_text_safety_sidecar)
        from modules.ph_image_safety import create_image_sidecar
        d = self.data
        selection = d['selections'].get(bid)
        if selection is None:
            stop('P5_EXPLICIT_SELECTION_REQUIRED')
        batch = d['batches'][bid]
        rows = copy.deepcopy([r for r in batch['rows'] if _asin(r) in selection['asins']])
        if rows_override is None:
            from modules.p5_material_updates import current_rows
            rows = current_rows(self.runtime, bid, rows)
        else:
            rows = copy.deepcopy(rows_override)
        candidates = (expansion_rows_to_prelisting_candidates(rows) if batch['source_type'] == 'EXPANSION'
                      else resolver_rows_to_prelisting_candidates(rows).output_rows)
        content = rows_to_prelisting_candidate_csv(candidates)
        return {'candidate_content': content, 'filename': 'prelisting_candidates_p5.csv', 'producer_rows': rows,
            'ingredient_content': rows_to_ingredient_safety_sidecar(content, candidates, facts_for_candidate_rows(candidates, rows)),
            'text_content': rows_to_product_text_safety_sidecar(content, candidates, text_facts(candidates, rows)),
            'image_content': create_image_sidecar(content, candidates, rows)}

    def require_record(self, record):
        from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
        d = self.data
        from modules.p5_material_updates import require_record_generation
        require_record_generation(self.runtime, record)
        # Source/Candidate identity is checked per product; unrelated batches may be added.
        actual = parse_prelisting_candidate_csv(record['source']['candidate'].encode('utf-8'),
                                                filename=record['source']['filename'])
        actual_row = next((r for r in actual.rows if r.candidate_asin == record['asin']), None)
        for bid, selection in d['selections'].items():
            if record['asin'] not in selection['asins']:
                continue
            expected = self.handoff(bid)
            parsed = parse_prelisting_candidate_csv(expected['candidate_content'], filename=expected['filename'])
            expected_row = next(r for r in parsed.rows if r.candidate_asin == record['asin'])
            producer = next(r for r in expected['producer_rows'] if _asin(r) == record['asin'])
            from modules.product_text_safety import parse_product_text_safety_sidecar
            actual_text = parse_product_text_safety_sidecar(record['source']['text'].encode('utf-8'),
                filename='p5_text.csv', candidate_content=record['source']['candidate'].encode('utf-8'), candidates=actual)
            expected_text = parse_product_text_safety_sidecar(expected['text_content'],
                filename='p5_text.csv', candidate_content=expected['candidate_content'], candidates=parsed)
            from modules.ingredient_safety import parse_ingredient_safety_sidecar
            actual_ingredients = parse_ingredient_safety_sidecar(record['source']['ingredients'].encode('utf-8'),
                filename='p5_ingredients.csv', candidate_content=record['source']['candidate'].encode('utf-8'), candidates=actual)
            expected_ingredients = parse_ingredient_safety_sidecar(expected['ingredient_content'],
                filename='p5_ingredients.csv', candidate_content=expected['candidate_content'], candidates=parsed)
            from modules.ph_image_safety import parse_image_sidecar
            expected_images = parse_image_sidecar(expected['image_content'],
                candidate_content=expected['candidate_content'], candidates=parsed)
            image = next(r['fact'] for r in expected_images['rows'] if r['fact']['candidate_asin'] == record['asin'])
            actual_image = (record.get('weapon') or {}).get('images', {})
            if (actual_row == expected_row and record['facts'] == producer.get('classification_facts')
                    and actual_ingredients.facts_by_asin[record['asin']] == expected_ingredients.facts_by_asin[record['asin']]
                    and all(actual_image.get(k) == image.get(k) for k in
                            ('candidate_asin', 'provider', 'image_urls', 'root_category_id', 'capture_error'))
                    and actual_text.facts_by_asin[record['asin']] == expected_text.facts_by_asin[record['asin']]):
                origin = (next(json.loads(v)['origin'] for v in self.runtime.scope.resolver_inputs
                               if json.loads(v)['source_id'] == producer['source_id'])
                          if d['batches'][bid]['source_type'] == 'RESOLVER' else producer['seed_asin'])
                binding = {'scope_digest': self.runtime.scope.digest, 'batch': bid, 'origin': origin,
                    'source_type': d['batches'][bid]['source_type'], **copy.deepcopy(selection)}
                if record['source'].get('p5_selection', binding) != binding:
                    stop('P5_SELECTION_HISTORY_CHANGED')
                return binding
        stop('P5_PRODUCT_NOT_SELECTED_OR_SOURCE_CHANGED')
