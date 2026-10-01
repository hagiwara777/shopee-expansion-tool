"""Native Streamlit status display for every SG SLS state."""
import pytest
import logging
from test_app_category_mapper_sg import _standard_logger_warning
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("state,action,label,element", [
    ("UNCHECKED",None,"UNCHECKED","info"),
    ("EVALUATED","CATEGORY_ALLOW","ALLOW候補","info"),
    ("EVALUATED","CATEGORY_REVIEW","REVIEW","warning"),
    ("EVALUATED","CATEGORY_EXCLUDE","EXCLUDE","error"),
    ("UNAVAILABLE",None,"UNAVAILABLE","error"),
])
def test_sg_native_status_display(state,action,label,element,monkeypatch):
    monkeypatch.setattr(logging.Logger,"warning",_standard_logger_warning)
    code = f'''from modules.category_mapper_sg import SGMapperRecommendation
from modules.sls_category_rules_sg import SgSlsCategoryResult
from modules.category_mapper_sg_ui import _render_sls
item=SGMapperRecommendation("SG","EXPANSION","B000000000","B000000001","Test","Maker","Category","","GATE_ELIGIBLE",sls_result=SgSlsCategoryResult(check_state={state!r},action={action!r},reason_codes=("NO_CATEGORY_STOP",)))
_render_sls(item)
'''
    app=AppTest.from_string(code).run()
    assert not app.exception
    assert any("SG SLS: "+label in str(item.value) for item in getattr(app,element))
    assert any("listing_ready" in str(item.value) for item in app.caption)
    assert len(app.button) == len(app.download_button) == 0
