"""On-demand Shopee refresh for one representative shop per marketplace.

The credential file is provisioned outside this module and outside Git. A
failed or ambiguous refresh is never retried with the previous refresh token.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Callable, Iterator, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


REFRESH_PATH = "/api/v2/auth/access_token/get"
PRODUCTION_BASE_URL = "https://partner.shopeemobile.com"
REFRESH_MARGIN_SECONDS = 120
_MAX_EXPIRE_SECONDS = 86400
_TIMEOUT_SECONDS = 30
_MARKETS = frozenset({"PH", "SG", "MY", "TH"})


class TokenManagerError(RuntimeError):
    """A safe, secret-free failure requiring operator review when blocked."""


@dataclass(frozen=True, repr=False)
class ShopeeAuthContext:
    marketplace: str
    partner_id: int
    shop_id: int
    access_token: str

    def __repr__(self) -> str:
        return "ShopeeAuthContext(<redacted>)"


@dataclass(frozen=True, repr=False)
class PartnerBinding:
    marketplace: str
    partner_id: int
    shop_id: int
    partner_key: str

    def __repr__(self) -> str:
        return "PartnerBinding(<redacted>)"


@dataclass(frozen=True, repr=False)
class TokenRecord:
    schema_version: int
    marketplace: str
    partner_id: int
    shop_id: int
    access_token: str
    refresh_token: str
    access_expires_at: int | None
    acquired_at_lower_bound: int | None
    generation: int
    state: str
    reason_code: str | None

    def __repr__(self) -> str:
        return "TokenRecord(<redacted>)"


Transport = Callable[[str, Mapping[str, str], Mapping[str, object], int], Mapping[str, Any]]


class ShopeeTokenManager:
    def __init__(
        self,
        marketplace: str,
        *,
        credential_path: Path | None = None,
        transport: Transport | None = None,
        clock: Callable[[], float] = time.time,
        refresh_margin_seconds: int = REFRESH_MARGIN_SECONDS,
        base_url: str = PRODUCTION_BASE_URL,
    ) -> None:
        normalized = str(marketplace).strip().upper()
        if normalized not in _MARKETS:
            raise TokenManagerError("Unsupported marketplace.")
        if not isinstance(refresh_margin_seconds, int) or refresh_margin_seconds < 0:
            raise TokenManagerError("Invalid refresh margin.")
        self.marketplace = normalized
        self.credential_path = Path(credential_path) if credential_path else default_credential_path(normalized)
        self.transport = transport or _post_refresh
        self.clock = clock
        self.refresh_margin_seconds = refresh_margin_seconds
        self.base_url = base_url.rstrip("/")

    def get_context(self, binding: PartnerBinding) -> ShopeeAuthContext:
        if (
            binding.marketplace != self.marketplace
            or not _positive_int(binding.partner_id)
            or not _positive_int(binding.shop_id)
            or not isinstance(binding.partner_key, str)
            or not binding.partner_key
        ):
            raise TokenManagerError("Shopee token binding is invalid.")
        with _exclusive_lock(self.credential_path):
            record = _read_record(self.credential_path)
            _check_binding(record, binding)
            if record.state != "READY":
                raise TokenManagerError("Shopee token requires operator review.")
            now = int(self.clock())
            if record.access_expires_at is not None and record.access_expires_at - now > self.refresh_margin_seconds:
                return _context(record)
            in_flight = _replace_record(record, state="IN_FLIGHT", reason_code="REFRESH_STARTED")
            _atomic_write(self.credential_path, in_flight)
            if _read_record(self.credential_path) != in_flight:
                raise TokenManagerError("Shopee token persistence verification failed.")
            timestamp = int(self.clock())
            query = {
                "partner_id": str(binding.partner_id),
                "timestamp": str(timestamp),
                "sign": hmac.new(
                    binding.partner_key.encode("utf-8"),
                    f"{binding.partner_id}{REFRESH_PATH}{timestamp}".encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest(),
            }
            body = {
                "partner_id": binding.partner_id,
                "shop_id": binding.shop_id,
                "refresh_token": record.refresh_token,
            }
            try:
                payload = self.transport(self.base_url + REFRESH_PATH, query, body, _TIMEOUT_SECONDS)
                access_token, refresh_token, expire_in = _validate_response(payload, binding)
                ready = _replace_record(
                    record,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    access_expires_at=now + expire_in,
                    acquired_at_lower_bound=now,
                    generation=record.generation + 1,
                    state="READY",
                    reason_code=None,
                )
                _atomic_write(self.credential_path, ready)
                if _read_record(self.credential_path) != ready:
                    raise TokenManagerError("Shopee token persistence verification failed.")
                return _context(ready)
            except Exception:
                # IN_FLIGHT is durable. A crash or unknown remote outcome must
                # never cause the old one-use refresh token to be sent again.
                raise TokenManagerError("Shopee token refresh requires operator review.") from None


def default_credential_path(marketplace: str) -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / "ShopeeOpenPlatform" / "token-manager" / f"{marketplace}.json"


def _context(record: TokenRecord) -> ShopeeAuthContext:
    return ShopeeAuthContext(record.marketplace, record.partner_id, record.shop_id, record.access_token)


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _replace_record(record: TokenRecord, **changes: object) -> TokenRecord:
    values = {name: getattr(record, name) for name in TokenRecord.__dataclass_fields__}
    values.update(changes)
    return TokenRecord(**values)


def _read_record(path: Path) -> TokenRecord:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != set(TokenRecord.__dataclass_fields__):
            raise ValueError
        record = TokenRecord(**raw)
        if (
            record.schema_version != 1
            or record.marketplace not in _MARKETS
            or not _positive_int(record.partner_id)
            or not _positive_int(record.shop_id)
            or not isinstance(record.access_token, str)
            or not record.access_token
            or not isinstance(record.refresh_token, str)
            or not record.refresh_token
            or (record.access_expires_at is not None and not _positive_int(record.access_expires_at))
            or (record.acquired_at_lower_bound is not None and not _positive_int(record.acquired_at_lower_bound))
            or not isinstance(record.generation, int)
            or isinstance(record.generation, bool)
            or record.generation < 0
            or record.state not in {"READY", "IN_FLIGHT", "BLOCKED"}
            or (record.reason_code is not None and not isinstance(record.reason_code, str))
        ):
            raise ValueError
        return record
    except Exception:
        raise TokenManagerError("Shopee token credential is unavailable or invalid.") from None


def _check_binding(record: TokenRecord, binding: PartnerBinding) -> None:
    if (record.marketplace, record.partner_id, record.shop_id) != (
        binding.marketplace, binding.partner_id, binding.shop_id
    ):
        raise TokenManagerError("Shopee token binding mismatch.")


def _validate_response(payload: object, binding: PartnerBinding) -> tuple[str, str, int]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("error", ""), str) or payload.get("error", "") != "":
        raise TokenManagerError("Shopee refresh response was invalid.")
    response = payload
    access = response.get("access_token")
    refresh = response.get("refresh_token")
    expire = response.get("expire_in")
    if (
        not isinstance(access, str) or not access.strip()
        or not isinstance(refresh, str) or not refresh.strip()
        or not _positive_int(expire) or expire > _MAX_EXPIRE_SECONDS
        or response.get("partner_id") != binding.partner_id
        or response.get("shop_id") != binding.shop_id
    ):
        raise TokenManagerError("Shopee refresh response was invalid.")
    return access, refresh, expire


def _atomic_write(path: Path, record: TokenRecord) -> None:
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".token-", suffix=".tmp", delete=False) as stream:
            temporary = stream.name
            json.dump({name: getattr(record, name) for name in TokenRecord.__dataclass_fields__}, stream, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        _harden_windows_acl(Path(temporary))
        os.replace(temporary, path)
    except Exception:
        raise TokenManagerError("Shopee token persistence failed.") from None
    finally:
        if temporary is not None:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _harden_windows_acl(path.parent)
        lock_path = path.with_suffix(path.suffix + ".lock")
        with open(lock_path, "a+b") as stream:
            _harden_windows_acl(lock_path)
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                if path.exists():
                    _harden_windows_acl(path)
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    except TokenManagerError:
        raise
    except Exception:
        raise TokenManagerError("Shopee token lock failed.") from None


def _harden_windows_acl(path: Path) -> None:
    if os.name != "nt":
        return
    try:
        import csv
        import ctypes
        from ctypes import wintypes

        identity = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True, text=True, check=True,
        )
        sid = next(csv.reader(identity.stdout.splitlines()))[1]
        if not re.fullmatch(r"S-1-(?:[0-9]+-)+[0-9]+", sid):
            raise ValueError

        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        dacl_info = 0x00000004
        protected_dacl = 0x80000000
        advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD),
        ]
        advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
        advapi.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
        advapi.SetFileSecurityW.restype = wintypes.BOOL
        advapi.GetFileSecurityW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        ]
        advapi.GetFileSecurityW.restype = wintypes.BOOL
        advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD),
        ]
        advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p

        flags = "OICI" if path.is_dir() else ""
        sddl = f"D:P(A;{flags};FA;;;{sid})(A;{flags};FA;;;SY)(A;{flags};FA;;;BA)"
        descriptor = ctypes.c_void_p()
        if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), None
        ):
            raise OSError
        try:
            if not advapi.SetFileSecurityW(str(path), dacl_info | protected_dacl, descriptor):
                raise OSError
        finally:
            kernel.LocalFree(descriptor)

        size = wintypes.DWORD()
        advapi.GetFileSecurityW(str(path), dacl_info, None, 0, ctypes.byref(size))
        if not size.value:
            raise OSError
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi.GetFileSecurityW(
            str(path), dacl_info, buffer, size.value, ctypes.byref(size)
        ):
            raise OSError
        readback_ptr = ctypes.c_void_p()
        if not advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            buffer, 1, dacl_info, ctypes.byref(readback_ptr), None
        ):
            raise OSError
        try:
            readback = ctypes.wstring_at(readback_ptr)
        finally:
            kernel.LocalFree(readback_ptr)

        if not re.fullmatch(r"D:P(?:AI)?(?:\([^()]+\))+", readback):
            raise ValueError
        entries = re.findall(r"\(([^()]+)\)", readback)
        principals = set()
        for entry in entries:
            fields = entry.split(";")
            if len(fields) != 6 or fields[0] != "A" or fields[2] != "FA":
                raise ValueError
            if fields[1] not in {"", "OICI"} or fields[3] or fields[4]:
                raise ValueError
            principals.add(fields[5])
        if sid not in principals or principals - {
            sid, "SY", "BA", "OW", "S-1-5-18", "S-1-5-32-544"
        }:
            raise ValueError
    except Exception:
        raise TokenManagerError("Shopee token file permissions could not be verified.") from None


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def _post_refresh(url: str, query: Mapping[str, str], body: Mapping[str, object], timeout: int) -> Mapping[str, Any]:
    request = Request(
        f"{url}?{urlencode(query)}",
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with build_opener(_RejectRedirects()).open(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, Mapping):
            raise ValueError
        return result
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeError):
        raise TokenManagerError("Shopee refresh request failed or returned an invalid response.") from None
