from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from modules.asin_resolver import build_ai_prompt, build_source_map
from modules.research_csv_adapter import ResearchCsvInput, import_research_csvs


def research(country='SG', host='shopee.sg', location='Japan'):
    return ResearchCsvInput('research.csv',
        ('Country,Location,Name,Product URL,Search Date\n'
         f'{country},{location},Ordinary towel,https://{host}/product/123/456,2026-11-01\n').encode('utf-8'))


@pytest.mark.parametrize(('marketplace', 'country', 'host', 'location', 'accepted'), [
    ('SG', 'SG', 'shopee.sg', 'Japan', 1),
    ('PH', 'PH', 'shopee.ph', 'Japan', 1),
    ('SG', 'PH', 'shopee.sg', 'Japan', 0),
    ('SG', 'SG', 'shopee.ph', 'Japan', 0),
    ('SG', 'SG', 'shopee.sg', 'Singapore', 0),
    ('PH', 'SG', 'shopee.sg', 'Japan', 0),
])
def test_selected_country_filter_and_resolver_prompt(marketplace, country, host, location, accepted):
    result = import_research_csvs([research(country, host, location)], marketplace=marketplace)
    assert len(result.resolver_rows) == accepted
    if accepted:
        assert result.resolver_rows[0]['source_id'].startswith('J'+marketplace)
        source = '\n'.join(f"{row['source_id']}\t{row['input_title']}" for row in result.resolver_rows)
        assert build_source_map(source) == {'R0001': 'Ordinary towel'}
        assert 'R0001\tOrdinary towel' in build_ai_prompt(source)


def test_research_csv_is_passed_to_prompt_in_same_screen(monkeypatch):
    import logging
    import streamlit as st
    from pathlib import Path

    def warning(logger, message, *args, **kwargs):
        if logger.isEnabledFor(logging.WARNING):
            logger._log(logging.WARNING, message, args, **kwargs)
    monkeypatch.setattr(logging.Logger, 'warning', warning)
    uploader = st.file_uploader
    upload = research()
    uploaded = SimpleNamespace(name=upload.filename, getvalue=lambda: upload.content)
    monkeypatch.setattr(st, 'file_uploader', lambda *args, **kwargs:
        [uploaded] if kwargs.get('key') == 'sora_research_files' else uploader(*args, **kwargs))
    monkeypatch.setattr('modules.sora_ui.load_sp_api_credentials',
                        lambda: pytest.fail('CSV import must not read secrets'))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=20).run()
    next(b for b in app.button if b.key == 'sora_import_research').click().run()
    assert not app.exception
    assert 'Ordinary towel' in app.text_area(key='sora_source_input').value
    next(b for b in app.button if b.key == 'sora_generate_prompt').click().run()
    assert 'R0001\tOrdinary towel' in app.code[0].value
