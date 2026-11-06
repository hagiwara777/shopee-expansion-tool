"""Local ASIN-only inputs. CSV product descriptions never become safety facts."""

from dataclasses import dataclass
import csv
from io import StringIO
import re

from modules.sp_api_catalog import ASIN_PATTERN, planned_catalog_calls


class SoraInputError(ValueError):
    """A locally chosen, Japanese diagnostic; never include file contents."""


@dataclass(frozen=True)
class AsinInput:
    asins: tuple[str, ...]
    data_row_count: int
    duplicate_count: int
    empty_asin_count: int = 0


def _result(values, *, empty_count=0):
    asins = tuple(dict.fromkeys(values))
    if not asins:
        raise SoraInputError('取り込めるASINがありません。ASIN欄を確認してください。')
    planned_catalog_calls(asins)
    return AsinInput(asins, len(values) + empty_count, len(values) - len(asins), empty_count)


def parse_asin_text(text: str) -> AsinInput:
    values = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for value in re.split(r'[\s,]+', line.strip()):
            if not value:
                continue
            asin = value.upper()
            if not ASIN_PATTERN.fullmatch(asin):
                raise SoraInputError(f'{line_number}行目のASINが違う形式です。半角英数字10文字のASINだけを貼ってください。')
            values.append(asin)
    return _result(values)


def parse_fromax_keepa_csv(content: bytes) -> AsinInput:
    if content.startswith(b'PK') or b'\x00' in content:
        raise SoraInputError('CSV形式ではありません。FROMAXのKeepaからCSVを書き出してください。')
    for encoding in ('utf-8-sig', 'cp932'):
        try:
            text = content.decode(encoding)
            break
        except UnicodeError:
            continue
    else:
        raise SoraInputError('CSVの文字コードを読めません。UTF-8のCSVで保存してください。')
    try:
        rows = list(csv.reader(StringIO(text, newline=''), strict=True))
    except csv.Error:
        raise SoraInputError('CSVの区切りや引用符が違う形式です。FROMAXからCSVを書き出し直してください。') from None
    if not rows:
        raise SoraInputError('CSVが空です。ASIN列のあるFROMAXのKeepa CSVを入れてください。')
    headers = [cell.strip().casefold() for cell in rows[0]]
    if headers.count('asin') != 1:
        if headers.count('asin') > 1:
            raise SoraInputError('ASIN列が複数あります。ASIN列を1つにしてください。')
        raise SoraInputError('ASIN列がありません。先頭行にASIN列がある、カンマ区切りのFROMAXのKeepa CSVを入れてください。')
    column = headers.index('asin')
    values = []
    empty = 0
    for line_number, row in enumerate(rows[1:], 2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(headers):
            raise SoraInputError(f'{line_number}行目の列数が見出しと違います。CSVの区切りを確認してください。')
        asin = row[column].strip().upper()
        if not asin:
            empty += 1
            continue
        if not ASIN_PATTERN.fullmatch(asin):
            raise SoraInputError(f'{line_number}行目のASINが違う形式です。半角英数字10文字か確認してください。')
        values.append(asin)
    return _result(values, empty_count=empty)
