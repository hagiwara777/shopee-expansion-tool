"""Identify bounded, explicitly headed ingredient lists without changing offsets.

Input is NFKC/lowercase text with newlines and HTML still present.  Ambiguous
headings or prose are not ingredient evidence; callers keep their normal stop.
"""
import html
import re


_LABEL = r"(?:原材料(?:[・/]\s*成分)?|全成分|成分)"
_BOUNDARY = r"(?:^|[。.!?！？;]|</?(?:p|div|li)\b[^>]*>|<br\b[^>]*>)[ \t]*"
_HEADER = re.compile(
    rf"(?:【\s*{_LABEL}\s*】|\[\s*{_LABEL}\s*\]|〈{_LABEL}〉|《{_LABEL}》|〔{_LABEL}〕|\({_LABEL}\)|<{_LABEL}>)\s*:?"
    rf"|<(?P<heading_tag>h[1-6]|strong|b)\b[^>]*>\s*{_LABEL}\s*:?\s*</(?P=heading_tag)>\s*:?"
    rf"|{_BOUNDARY}{_LABEL}[ \t]*:"
    rf"|{_BOUNDARY}{_LABEL}(?=[ \t]*(?:\r?\n|<br\b|$))"
    rf"|{_BOUNDARY}{_LABEL}[ \t]+(?=\S)",
    re.M | re.I,
)
_SECTION_LABEL = r"(?:ご?使用方法|使い方|効能(?:・効果)?|効果|商品説明|注意(?:事項)?|ご注意|使用上の注意|特徴|特長)"
_BRACKET_HEADING = rf"(?:【[^】\r\n]+】|\[[^\]\r\n]+\]|〈[^〉\r\n]+〉|《[^》\r\n]+》|〔[^〕\r\n]+〕|\(\s*{_SECTION_LABEL}\s*\))"
_BREAK = re.compile(rf"\r?\n|<br\b[^>]*>|</?(?:p|div|li|ul|ol|h[1-6]|strong|b)\b[^>]*>|{_BRACKET_HEADING}|[。！？!?]|(?<!\d)\.(?=\s|<|$)", re.I)
_SECTION = re.compile(
    rf"^(?:【|\[)?{_SECTION_LABEL}"
    r"(?:】|\])?(?:\s*:|\s+|$)"
)
_TAGS = re.compile(r"<[^>]*>")
# Ingredient entries are fragments, not claims or instructions.  Rejecting
# Japanese prose/English claim grammar is conservative and needs no chemical
# dictionary; an unfamiliar ingredient format simply retains the normal stop.
_PROSE = re.compile(
    r"[ぁ-ゖ]|配合|含有|効能|効果|効用|改善|美白|保湿|浸透|促進|抑制|予防"
    r"|\b(?:with|for|helps?|contains?|provides?|formulated)\b|[:。!?！？]", re.I,
)


def _entries(chunk: str) -> tuple[str, ...] | None:
    plain = html.unescape(_TAGS.sub("", chunk)).strip()
    if not plain:
        return ()
    if _SECTION.match(plain) or _PROSE.search(plain):
        return None
    entries = tuple(part.strip() for part in re.split(r"[,、・;]", plain))
    if any(not part or len(part) > 160 for part in entries):
        return None
    return entries


def ingredient_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Return confirmed list intervals; every index refers to ``text`` itself."""
    headers = tuple(_HEADER.finditer(text))
    spans = []
    for index, header in enumerate(headers):
        limit = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        start = header.end()
        cursor, end, count = start, start, 0
        previous_newline = False
        for boundary in (*_BREAK.finditer(text, start, limit), None):
            stop = boundary.start() if boundary is not None else limit
            entries = _entries(text[cursor:stop])
            if entries is None:
                break
            if entries:
                # A new unlabelled fragment after a complete list could be a
                # product claim.  Do not inherit the preceding list's heading.
                if count >= 2 and previous_newline and len(entries) < 2:
                    break
                count += len(entries)
                end = stop
            elif count and previous_newline and boundary is not None and ("\n" in boundary.group() or boundary.group().lower().startswith("<br")):
                break
            if boundary is None:
                break
            token = boundary.group().lower()
            if re.fullmatch(_BRACKET_HEADING, token):
                break
            if token[0] in ".。！？!?" or re.match(r"</(?:ul|ol)\b", token):
                break
            if count and re.match(r"</?(?:p|div|h[1-6]|strong|b)\b", token):
                break
            previous_newline = "\n" in token or token.startswith("<br")
            cursor = boundary.end()
        if count >= 2 and end > start:
            spans.append((start, end))
    return tuple(spans)
