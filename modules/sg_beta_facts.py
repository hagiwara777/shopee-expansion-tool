"""Explicit per-field product provenance for the SG initial beta (no acquisition)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import unicodedata

from modules.keepa_client import normalize_asin

ORIGINS = frozenset({'OWN_PRODUCT', 'SEED_FALLBACK', 'UNKNOWN', 'MISSING'})
FIELDS = ('title', 'brand', 'model', 'category_tree', 'description', 'features',
          'shortDescription', 'safetyWarning', 'itemHighlights', 'ingredients',
          'activeIngredients', 'specialIngredients')


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value)).casefold().split())


@dataclass(frozen=True)
class FieldFact:
    value: object
    origin: str
    source_asin: str
    acquired_market: str
    evidence_ref: str
    fetched_at: str

    def __post_init__(self):
        if (self.origin not in ORIGINS or not all(isinstance(v, str) for v in
                (self.source_asin, self.acquired_market, self.evidence_ref, self.fetched_at))):
            raise ValueError('Invalid product Fact provenance')
        digest(self.value)

    def owned_by(self, asin):
        try:
            captured = datetime.fromisoformat(self.fetched_at.replace('Z', '+00:00'))
            dated = captured.tzinfo is not None and captured <= datetime.now(timezone.utc)
        except ValueError:
            dated = False
        return (self.origin == 'OWN_PRODUCT' and self.source_asin == asin
                and self.acquired_market == 'JP' and bool(self.evidence_ref)
                and dated and self.value not in (None, '', [], ()))


@dataclass(frozen=True)
class ProductFacts:
    asin: str
    fields: dict[str, FieldFact]

    def __post_init__(self):
        if normalize_asin(self.asin) != self.asin or set(self.fields) != set(FIELDS):
            raise ValueError('Explicit full Fact field set and canonical ASIN required')
        if any(not isinstance(f, FieldFact) for f in self.fields.values()):
            raise ValueError('Invalid Fact field')
        for name in ('title', 'brand', 'model'):
            if not isinstance(self.fields[name].value, str):
                raise ValueError('Fact identity must be text')
        tree = self.fields['category_tree'].value
        if (not isinstance(tree, (list, tuple)) or any(not isinstance(n, dict)
                or set(n) != {'catId', 'name'} or type(n['catId']) is not int
                or n['catId'] <= 0 or not isinstance(n['name'], str) for n in tree)):
            raise ValueError('Invalid own product category tree')
        for name in FIELDS[4:]:
            if (not isinstance(self.fields[name].value, (list, tuple))
                    or any(not isinstance(s, str) for s in self.fields[name].value)):
                raise ValueError('Fact text must be an explicit string array')

    @property
    def binding(self):
        return digest(self.to_dict())

    def to_dict(self):
        return {'asin': self.asin, 'fields': {k: asdict(v) for k, v in self.fields.items()}}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {'asin', 'fields'}:
            raise ValueError('Invalid saved product Facts')
        return cls(value['asin'], {k: FieldFact(**v) for k, v in value['fields'].items()})


def facts_from_saved_keepa(product, *, evidence_ref, fetched_at='', source_format,
                          field_origins=None):
    """A raw response proves ownership, never an implicit cache JP default.

    Cache records require explicit provenance for each field. domain='JP'
    added by an older cache deserializer is deliberately not accepted as proof.
    """
    if source_format not in {'keepa_response', 'cache_snapshot'} or not isinstance(product, dict):
        raise ValueError('Explicit saved source format required')
    asin = normalize_asin(product.get('asin', ''))
    market = 'JP' if type(product.get('domainId')) is int and product['domainId'] == 5 else ''
    captured = product.get('fetched_at') or fetched_at
    if not isinstance(captured, str) or not isinstance(evidence_ref, str) or not evidence_ref:
        raise ValueError('Saved source identity required')
    origins = field_origins or product.get('field_origins', {})
    fields = {}
    for name in FIELDS:
        key = 'categoryTree' if name == 'category_tree' and source_format == 'keepa_response' else name
        value = product.get(key, '' if name in FIELDS[:3] else [])
        if name in FIELDS[4:] and isinstance(value, str):
            value = [value] if value.strip() else []
        if value is None:
            value = '' if name in FIELDS[:3] else []
        origin = ('OWN_PRODUCT' if source_format == 'keepa_response' else 'UNKNOWN')
        origin = origins.get(name, origin)
        if name == 'category_tree' and product.get('category_origin'):
            origin = product['category_origin']
        if value in ('', [], ()):
            origin = 'MISSING'
        fields[name] = FieldFact(value, origin, asin if origin == 'OWN_PRODUCT' else '',
                                 market, evidence_ref, captured)
    return ProductFacts(asin, fields)


@dataclass(frozen=True)
class CategoryRule:
    rule_id: str
    version: str
    category_id: int
    category_path: str
    leaf_names: tuple[str, ...]
    required_text: tuple[str, ...]
    excluded_text: tuple[str, ...]
    approval_ref: str
    scope: str = 'OFFLINE_ONLY'
    marketplace: str = 'SG'

    def __post_init__(self):
        if (self.marketplace not in {'PH', 'SG'}
                or type(self.category_id) is not int or self.category_id <= 0
                or not all(isinstance(s, str) and s.strip() for s in
                           (self.rule_id, self.version, self.category_path))
                or any(not isinstance(s, str) or not s.strip() for values in
                       (self.leaf_names, self.required_text, self.excluded_text) for s in values)):
            raise ValueError('Invalid limited Category rule')

    def matches(self, facts, *, mode):
        if (not self.approval_ref or not self.rule_id or not self.version
                or self.scope not in {'OFFLINE_ONLY', 'OPERATION_APPROVED'}
                or mode != 'OFFLINE' and self.scope != 'OPERATION_APPROVED'):
            return False
        needed = ('title', 'category_tree')
        if any(not facts.fields[k].owned_by(facts.asin) for k in needed):
            return False
        tree = facts.fields['category_tree'].value
        if not tree or normalized(tree[-1]['name']) not in {normalized(n) for n in self.leaf_names}:
            return False
        # Only owned evidence can satisfy a positive condition; all supplied
        # text may contradict it. Missing exclusions never prove no battery.
        owned = []
        all_text = []
        for name in ('title', 'model', *FIELDS[4:9]):
            f = facts.fields[name]
            texts = [f.value] if isinstance(f.value, str) else f.value
            all_text.extend(texts)
            if f.owned_by(facts.asin):
                owned.extend(texts)
        joined = normalized(' '.join(all_text))
        if any(normalized(t) in joined for t in self.excluded_text):
            return False
        return bool(self.required_text) and any(normalized(t) in normalized(' '.join(owned))
                                               for t in self.required_text)


def offline_wired_audio_rule(category_path):
    """Illustrative rule for tests; this function grants no operational approval."""
    return CategoryRule('SG_WIRED_AUDIO_OFFLINE', '1', 100578, category_path,
                        ('ヘッドホン', 'オーバーイヤーヘッドホン', 'イヤホン', 'Headphones'),
                        ('有線', 'wired', '3.5mm', '3.5 mm'),
                        ('Bluetooth', 'wireless', 'ワイヤレス', '充電', 'battery',
                         'ATH-M20xBT', 'replacement', '交換用', 'ear pads', 'イヤーパッド'),
                        'OWNER_BASIC_DESIGN_OFFLINE_DEMONSTRATION')
