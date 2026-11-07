"""SG material requirements and exact input binding, offline."""
from dataclasses import replace
import pytest
from modules.ingredient_safety import IngredientSafetyError
from modules.prelisting_gate_handoff import HandoffError, validate_packet
from modules.prelisting_gate_ui import required_safety_file_errors
from test_expansion_gate_handoff import packet


@pytest.mark.parametrize(('ingredient', 'text', 'missing'), [
    (False, False, 2), (False, True, 1), (True, False, 1), (True, True, 0),
])
def test_sg_required_safety_material_is_explicit(ingredient, text, missing):
    errors = required_safety_file_errors('SG', ingredient_present=ingredient,
                                        product_text_present=text)
    assert len(errors) == missing


def test_handoff_rejects_missing_material_changed_candidates_and_other_market():
    original = packet('SG')
    assert validate_packet(original, marketplace='SG', generation=original.generation).data_row_count == 1
    changed = replace(original, candidate=replace(original.candidate,
        content=original.candidate.content.replace(b'ordinary storage box', b'changed product')))
    with pytest.raises(IngredientSafetyError, match='candidate SHA-256 mismatch'):
        validate_packet(changed, marketplace='SG', generation=original.generation)
    with pytest.raises(HandoffError):
        validate_packet(replace(original, ingredient=None), marketplace='SG', generation=original.generation)
    with pytest.raises(HandoffError):
        validate_packet(original, marketplace='PH', generation=original.generation)
