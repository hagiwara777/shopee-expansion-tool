from dataclasses import asdict
import json
import logging
import pytest
from pathlib import Path
from types import SimpleNamespace
from streamlit.testing.v1 import AppTest
from test_sg_live_runtime import grant


@pytest.fixture(autouse=True)
def working_warning_logger(monkeypatch):
    # Same local repair as existing AppTest fixtures for this installed runtime.
    def warning(self,message,*args,**kwargs):
        if self.isEnabledFor(logging.WARNING): self._log(logging.WARNING,message,args,**kwargs)
    monkeypatch.setattr(logging.Logger,"warning",warning)


def test_live_ui_open_and_rerun_do_not_acquire_data(tmp_path,grant,monkeypatch):
    from modules import sg_live_runtime
    import app_sg_candidate
    calls=[]
    class Runtime:
        def __init__(self,**kwargs):
            calls.append("local initialization")
            self.workflow=SimpleNamespace(product_review=SimpleNamespace(clear_review_results=lambda: None))
            self.category_engine=None
            self.ledger=SimpleNamespace(data={"catalog_requests":0,"attribute_requests":0,"brand_page_counts":{"11":0},"openai":{"reserved_upper_bound_usd":"0"}})
        def refresh_catalog(self): calls.append("explicit catalog action"); return 1
    monkeypatch.setattr(sg_live_runtime,"SGLiveRuntime",Runtime)
    # Patch the callback actually used by the entry. The app can already be
    # imported by beta-entry tests, so patching its source module is too late.
    monkeypatch.setattr(app_sg_candidate,"render_sg_category_mapper",lambda **kwargs:None)
    path=tmp_path/"grant.json"; path.write_text(json.dumps(asdict(grant)))
    source=f"from app_sg_candidate import render_sg_candidate\nrender_sg_candidate(live_grant_path={str(path)!r})"
    app=AppTest.from_string(source).run()
    assert not app.exception and not calls
    app.button(key="sg_live_open").click().run()
    assert not app.exception and calls==["local initialization"]
    app.run(); assert calls==["local initialization"]
    app.button(key="sg_live_refresh_catalog").click().run()
    assert not app.exception and calls==["local initialization","explicit catalog action"]


def test_live_ui_invalid_grant_does_not_initialize(tmp_path,monkeypatch):
    from modules import sg_live_runtime
    calls=[]; monkeypatch.setattr(sg_live_runtime,"SGLiveRuntime",lambda **k:calls.append(k))
    path=tmp_path/"grant.json"; path.write_text("{}")
    source=f"from app_sg_candidate import render_sg_candidate\nrender_sg_candidate(live_grant_path={str(path)!r})"
    app=AppTest.from_string(source).run()
    assert not app.exception and app.error and not calls
