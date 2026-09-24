"""Read one marketplace Access Token from a dedicated Google Sheets Bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol


MARKETPLACES = frozenset({"PH", "SG", "MY", "TH"})
BRIDGE_RANGE = "A:C"
_HEADERS = ("marketplace", "shop_id", "access_token")


class AccessTokenSourceError(RuntimeError):
    """A safe, detail-free failure; never includes Bridge content."""


@dataclass(frozen=True)
class AccessToken:
    value: str = field(repr=False)

    def __repr__(self) -> str:
        return "AccessToken([REDACTED])"

    __str__ = __repr__


class BridgeTransport(Protocol):
    def read_values(self, spreadsheet_id: str, cell_range: str) -> object: ...


class GoogleSheetsTransport:
    """Small read-only Sheets adapter; credentials are resolved only when called."""

    def __init__(self, request: Callable[..., object] | None = None) -> None:
        self._request = request

    def read_values(self, spreadsheet_id: str, cell_range: str) -> object:
        if self._request is not None:
            return self._request(spreadsheet_id, cell_range)
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
            )
            session = AuthorizedSession(credentials)
            from urllib.parse import quote

            url = (
                "https://sheets.googleapis.com/v4/spreadsheets/"
                f"{quote(spreadsheet_id, safe='')}/values/{quote(cell_range, safe='')}"
            )
            response = session.get(url, params={"majorDimension": "ROWS"}, timeout=10)
            if response.status_code != 200:
                raise AccessTokenSourceError("Google Sheet Access Token Source is unavailable.")
            return response.json()
        except AccessTokenSourceError:
            raise
        except Exception:
            pass
        raise AccessTokenSourceError("Google Sheet Access Token Source is unavailable.")


class GoogleSheetAccessTokenSource:
    def __init__(self, spreadsheet_id: str, transport: BridgeTransport | None = None) -> None:
        if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
            raise AccessTokenSourceError("Google Sheet Access Token Source is not configured.")
        self._spreadsheet_id = spreadsheet_id.strip()
        self._transport = transport or GoogleSheetsTransport()

    def get_access_token(self, marketplace: str, expected_shop_id: int) -> AccessToken:
        if marketplace not in MARKETPLACES or type(expected_shop_id) is not int or expected_shop_id <= 0:
            raise AccessTokenSourceError("Google Sheet Access Token Source binding is invalid.")
        try:
            payload = self._transport.read_values(self._spreadsheet_id, BRIDGE_RANGE)
        except Exception:
            payload = None
        if payload is None:
            raise AccessTokenSourceError("Google Sheet Access Token Source is unavailable.")
        if not isinstance(payload, dict) or "values" not in payload or payload.get("majorDimension", "ROWS") != "ROWS":
            raise AccessTokenSourceError("Google Sheet Access Token Source response is invalid.")
        rows = payload["values"]
        if not isinstance(rows, list) or not rows or rows[0] != list(_HEADERS):
            raise AccessTokenSourceError("Google Sheet Access Token Source header is invalid.")
        matches: list[str] = []
        seen: set[str] = set()
        for row in rows[1:]:
            if not isinstance(row, list) or len(row) != 3 or any(not isinstance(v, str) for v in row):
                raise AccessTokenSourceError("Google Sheet Access Token Source response is invalid.")
            row_marketplace, shop_id, token = row
            if (row_marketplace not in MARKETPLACES or row_marketplace in seen
                    or not shop_id.isascii() or not shop_id.isdecimal()
                    or len(shop_id) > 20 or int(shop_id) <= 0
                    or not token or any(character.isspace() or ord(character) < 32 for character in token)):
                raise AccessTokenSourceError("Google Sheet Access Token Source row is invalid.")
            seen.add(row_marketplace)
            if row_marketplace == marketplace:
                if int(shop_id) != expected_shop_id:
                    raise AccessTokenSourceError("Google Sheet Access Token Source binding is invalid.")
                matches.append(token)
        if len(matches) != 1:
            raise AccessTokenSourceError("Google Sheet Access Token Source row is missing or ambiguous.")
        return AccessToken(matches[0])
