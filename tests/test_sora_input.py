import pytest

from modules.sora_input import SoraInputError, parse_asin_text, parse_fromax_keepa_csv
from modules.sp_api_catalog import SpApiCatalogError, planned_catalog_calls


@pytest.mark.parametrize('encoding', ['utf-8-sig', 'cp932'])
def test_fromax_uses_asin_even_with_blank_title_and_weight_and_deduplicates(encoding):
    data = ('ASIN,商品名,梱包重量(g)\n'
            'B000000001,タオル,120\n'
            'B000000002,,\n'
            ' b000000001 ,,\n'
            ',ASINなし,\n').encode(encoding)
    parsed = parse_fromax_keepa_csv(data)
    assert parsed.asins == ('B000000001', 'B000000002')
    assert (parsed.data_row_count, parsed.duplicate_count, parsed.empty_asin_count) == (4, 1, 1)


@pytest.mark.parametrize(('content', 'message'), [
    (b'title,weight\ntowel,100\n', 'ASIN列がありません'),
    (b'ASIN,asin\nB000000001,B000000002\n', 'ASIN列が複数'),
    (b'ASIN\tTitle\nB000000001\ttowel', 'カンマ区切り'),
    (b'ASIN,Title\nB000000001', '2行目の列数'),
    (b'ASIN,Title\nnot-an-asin,towel', '2行目のASIN'),
    (b'ASIN,Title\n"B000000001,towel', '引用符'),
    (b'PK\x03\x04', 'CSV形式ではありません'),
    (b'A\x00S\x00I\x00N', 'CSV形式ではありません'),
    (b'\x81', '文字コード'),
    (b'', 'CSVが空'),
    (b'ASIN,title\n,towel\n', '取り込めるASINがありません'),
])
def test_wrong_csv_has_specific_japanese_error_without_echoing_data(content, message):
    with pytest.raises(SoraInputError, match=message) as error:
        parse_fromax_keepa_csv(content)
    assert 'not-an-asin' not in str(error.value)


def test_text_and_csv_agree_with_duplicates_and_all_500_survive():
    asins = [f'B{i:09d}' for i in range(500)]
    pasted = parse_asin_text(',\n'.join(asins + asins[:1]))
    uploaded = parse_fromax_keepa_csv(('ASIN,商品名,重さ\n' + '\n'.join(a + ',,' for a in asins)).encode())
    assert pasted.asins == uploaded.asins == tuple(asins)
    assert pasted.duplicate_count == 1
    assert planned_catalog_calls(uploaded.asins) == 25
    with pytest.raises(SpApiCatalogError, match='500'):
        parse_asin_text('\n'.join(asins + ['B999999999']))


def test_invalid_text_is_rejected_instead_of_silently_dropping_it():
    with pytest.raises(SoraInputError, match='2行目'):
        parse_asin_text('B000000001\nhttps://example.com/')
