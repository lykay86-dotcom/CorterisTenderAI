"""Narrow read-only target and payload policy for manual provider probes."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from contextlib import suppress
from dataclasses import dataclass, field, replace
from enum import StrEnum
import ipaddress
import re
import socket
import ssl
from typing import Protocol, TypeVar
from urllib.parse import unquote, urlsplit

from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.manual_provider_protocol import (
    ManualProviderFtpsMode,
    ManualProviderPayloadFormat,
    ManualProviderProtocolFamily,
    manual_provider_protocol_policy,
    normalize_manual_protocol_endpoint,
)


class ManualProbeTransportReason(StrEnum):
    TARGET_BLOCKED = "target_blocked"
    DNS_BLOCKED = "dns_blocked"
    RESPONSE_STATUS = "response_status"
    RESPONSE_TYPE = "response_type"
    RESPONSE_TOO_LARGE = "response_too_large"
    FTP_LISTING_TOO_LARGE = "ftp_listing_too_large"
    FTP_SAMPLE_MISSING = "ftp_sample_missing"
    FTP_PASSIVE_BOUNCE = "ftp_passive_bounce"


class ManualProbeTransportError(RuntimeError):
    def __init__(self, reason: ManualProbeTransportReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class ManualTargetPolicyError(ManualProbeTransportError):
    pass


@dataclass(frozen=True, slots=True)
class ManualProbeTarget:
    family: ManualProviderProtocolFamily
    hostname: str = field(repr=False)
    port: int
    path: str = field(repr=False)
    scheme: str


@dataclass(frozen=True, slots=True)
class ResolvedManualProbeTarget:
    target: ManualProbeTarget = field(repr=False)
    addresses: tuple[str, ...] = field(repr=False)

    @property
    def port(self) -> int:
        return self.target.port


class ManualProbeTargetPolicy:
    """Fail-closed endpoint and all-answer DNS classification."""

    def validate_endpoint(
        self,
        endpoint: str,
        family: ManualProviderProtocolFamily,
        *,
        ftps_mode: ManualProviderFtpsMode | None = None,
    ) -> ManualProbeTarget:
        try:
            policy = manual_provider_protocol_policy(family)
            if (
                family is ManualProviderProtocolFamily.FTPS
                and ftps_mode is ManualProviderFtpsMode.EXPLICIT
            ):
                policy = replace(policy, default_port=21)
            normalized = normalize_manual_protocol_endpoint(endpoint, policy=policy)
            parsed = urlsplit(normalized)
        except (TypeError, ValueError):
            raise ManualTargetPolicyError(
                ManualProbeTransportReason.TARGET_BLOCKED, "Endpoint отклонён политикой цели."
            ) from None
        decoded = unquote(parsed.path)
        if any(ord(character) < 32 or ord(character) == 127 for character in decoded):
            raise ManualTargetPolicyError(
                ManualProbeTransportReason.TARGET_BLOCKED, "Endpoint отклонён политикой цели."
            )
        port = parsed.port or policy.default_port
        if family is ManualProviderProtocolFamily.FTPS:
            expected = 21 if ftps_mode is ManualProviderFtpsMode.EXPLICIT else 990
            if port != expected:
                raise ManualTargetPolicyError(
                    ManualProbeTransportReason.TARGET_BLOCKED,
                    "Endpoint отклонён политикой цели.",
                )
        return ManualProbeTarget(
            family=family,
            hostname=parsed.hostname or "",
            port=port,
            path=parsed.path or "/",
            scheme=parsed.scheme,
        )

    def validate_resolved_addresses(
        self,
        target: ManualProbeTarget,
        addresses: tuple[str, ...],
    ) -> ResolvedManualProbeTarget:
        if not addresses or len(addresses) > 16:
            raise ManualTargetPolicyError(
                ManualProbeTransportReason.DNS_BLOCKED, "DNS-ответ отклонён политикой цели."
            )
        normalized: list[str] = []
        for raw in addresses:
            try:
                address = ipaddress.ip_address(raw)
            except ValueError:
                raise ManualTargetPolicyError(
                    ManualProbeTransportReason.DNS_BLOCKED,
                    "DNS-ответ отклонён политикой цели.",
                ) from None
            if not _allowed_address(address):
                raise ManualTargetPolicyError(
                    ManualProbeTransportReason.DNS_BLOCKED,
                    "DNS-ответ отклонён политикой цели.",
                )
            normalized.append(address.compressed.casefold())
        return ResolvedManualProbeTarget(target, tuple(dict.fromkeys(normalized)))


@dataclass(frozen=True, slots=True)
class ManualProbeResponse:
    status_code: int
    content_type: str
    body: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class ManualFtpProbeResponse:
    names: tuple[str, ...]
    passive_address: str = field(repr=False)
    passive_port: int
    sample_name: str
    sample: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class ManualProbeCredentials:
    api_key: str | None = field(default=None, repr=False)
    username: str | None = field(default=None, repr=False)
    password: str | None = field(default=None, repr=False)


class ManualProbeResolver(Protocol):
    async def resolve(self, hostname: str) -> tuple[str, ...]: ...


class ManualHttpProbePort(Protocol):
    async def get(
        self,
        target: ManualProbeTarget,
        pinned_address: str,
        cancellation_token: CollectorCancellationToken,
        credentials: ManualProbeCredentials,
    ) -> ManualProbeResponse: ...


class ManualFtpProbePort(Protocol):
    async def read_sample(
        self,
        target: ManualProbeTarget,
        pinned_address: str,
        suffix: str,
        ftps_mode: ManualProviderFtpsMode | None,
        cancellation_token: CollectorCancellationToken,
        credentials: ManualProbeCredentials,
    ) -> ManualFtpProbeResponse: ...


class SystemManualProbeResolver:
    MAX_ANSWERS = 16
    TIMEOUT_SECONDS = 5.0

    async def resolve(self, hostname: str) -> tuple[str, ...]:
        loop = asyncio.get_running_loop()
        async with asyncio.timeout(self.TIMEOUT_SECONDS):
            records = await loop.getaddrinfo(
                hostname,
                None,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
        addresses = tuple(dict.fromkeys(str(item[4][0]) for item in records))
        if not addresses or len(addresses) > self.MAX_ANSWERS:
            raise ManualTargetPolicyError(
                ManualProbeTransportReason.DNS_BLOCKED,
                "DNS-ответ отклонён политикой цели.",
            )
        return addresses


class PinnedHttpsProbePort:
    TIMEOUT_SECONDS = 20.0
    MAX_HEADER_BYTES = 32_768
    MAX_BODY_BYTES = 1_048_576

    def __init__(self, context: ssl.SSLContext | None = None) -> None:
        self._context = context or ssl.create_default_context()

    async def get(
        self,
        target: ManualProbeTarget,
        pinned_address: str,
        cancellation_token: CollectorCancellationToken,
        credentials: ManualProbeCredentials,
    ) -> ManualProbeResponse:
        cancellation_token.throw_if_cancelled()
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(self.TIMEOUT_SECONDS):
                reader, writer = await asyncio.open_connection(
                    pinned_address,
                    target.port,
                    ssl=self._context,
                    server_hostname=target.hostname,
                )
                headers = [
                    f"GET {target.path} HTTP/1.1",
                    f"Host: {target.hostname}",
                    "Accept: application/json, application/xml, application/rss+xml, application/atom+xml",
                    "Accept-Encoding: identity",
                    "Connection: close",
                    "User-Agent: CorterisTenderAI/manual-health-v1",
                ]
                if credentials.api_key is not None:
                    headers.append(f"Authorization: Bearer {credentials.api_key}")
                writer.write(("\r\n".join(headers) + "\r\n\r\n").encode("ascii"))
                await writer.drain()
                raw_headers = await reader.readuntil(b"\r\n\r\n")
                if len(raw_headers) > self.MAX_HEADER_BYTES:
                    raise ManualProbeTransportError(
                        ManualProbeTransportReason.RESPONSE_TOO_LARGE,
                        "HTTP headers превышают безопасный лимит.",
                    )
                status, content_type, chunked = _parse_http_headers(raw_headers)
                raw_body = await reader.read(self.MAX_BODY_BYTES + 1)
                if len(raw_body) > self.MAX_BODY_BYTES:
                    raise ManualProbeTransportError(
                        ManualProbeTransportReason.RESPONSE_TOO_LARGE,
                        "Ответ источника превышает лимит.",
                    )
                body = _decode_chunked(raw_body, self.MAX_BODY_BYTES) if chunked else raw_body
                cancellation_token.throw_if_cancelled()
                return ManualProbeResponse(status, content_type, body)
        except (ManualProbeTransportError, asyncio.CancelledError):
            raise
        except Exception:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.RESPONSE_STATUS,
                "HTTPS probe завершился безопасной ошибкой.",
            ) from None
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()


class PinnedFtpsProbePort:
    TIMEOUT_SECONDS = 25.0
    MAX_LINE_BYTES = 2048
    MAX_LISTING_BYTES = 65_536
    MAX_SAMPLE_BYTES = 1_048_576

    def __init__(self, context: ssl.SSLContext | None = None) -> None:
        self._context = context or ssl.create_default_context()

    async def read_sample(
        self,
        target: ManualProbeTarget,
        pinned_address: str,
        suffix: str,
        ftps_mode: ManualProviderFtpsMode | None,
        cancellation_token: CollectorCancellationToken,
        credentials: ManualProbeCredentials,
    ) -> ManualFtpProbeResponse:
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(self.TIMEOUT_SECONDS):
                is_ftps = target.family is ManualProviderProtocolFamily.FTPS
                implicit = is_ftps and ftps_mode is not ManualProviderFtpsMode.EXPLICIT
                if not is_ftps and (
                    credentials.username is not None or credentials.password is not None
                ):
                    raise ManualProbeTransportError(
                        ManualProbeTransportReason.TARGET_BLOCKED,
                        "Credentials запрещены для plaintext FTP probe.",
                    )
                reader, writer = await asyncio.open_connection(
                    pinned_address,
                    target.port,
                    ssl=self._context if implicit else None,
                    server_hostname=target.hostname if implicit else None,
                )
                await _ftp_expect(reader, {220}, self.MAX_LINE_BYTES)
                if is_ftps and not implicit:
                    await _ftp_command(reader, writer, "AUTH TLS", {234}, self.MAX_LINE_BYTES)
                    await writer.start_tls(self._context, server_hostname=target.hostname)
                username = credentials.username or "anonymous"
                password = credentials.password or "anonymous@invalid"
                code = await _ftp_command(
                    reader, writer, f"USER {username}", {230, 331}, self.MAX_LINE_BYTES
                )
                if code == 331:
                    await _ftp_command(
                        reader, writer, f"PASS {password}", {230}, self.MAX_LINE_BYTES
                    )
                if is_ftps:
                    await _ftp_command(reader, writer, "PBSZ 0", {200}, self.MAX_LINE_BYTES)
                    await _ftp_command(reader, writer, "PROT P", {200}, self.MAX_LINE_BYTES)
                if target.path not in {"", "/"}:
                    await _ftp_command(
                        reader, writer, f"CWD {target.path}", {250}, self.MAX_LINE_BYTES
                    )
                names, passive_address, passive_port = await self._read_data_command(
                    reader,
                    writer,
                    target,
                    pinned_address,
                    "NLST",
                    self.MAX_LISTING_BYTES,
                    use_tls=is_ftps,
                )
                listing = tuple(
                    line.strip()
                    for line in names.decode("utf-8", errors="strict").splitlines()
                    if line.strip()
                )
                sample_name = select_ftp_sample(listing, suffix)
                sample, _, _ = await self._read_data_command(
                    reader,
                    writer,
                    target,
                    pinned_address,
                    f"RETR {sample_name}",
                    self.MAX_SAMPLE_BYTES,
                    use_tls=is_ftps,
                )
                cancellation_token.throw_if_cancelled()
                await _ftp_command(reader, writer, "QUIT", {221}, self.MAX_LINE_BYTES)
                return ManualFtpProbeResponse(
                    listing,
                    passive_address,
                    passive_port,
                    sample_name,
                    sample,
                )
        except (ManualProbeTransportError, asyncio.CancelledError):
            raise
        except Exception:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.RESPONSE_STATUS,
                "FTPS probe завершился безопасной ошибкой.",
            ) from None
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()

    async def _read_data_command(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        target: ManualProbeTarget,
        pinned_address: str,
        command: str,
        maximum: int,
        *,
        use_tls: bool,
    ) -> tuple[bytes, str, int]:
        writer.write(b"EPSV\r\n")
        await writer.drain()
        _, line = await _ftp_expect(reader, {229}, self.MAX_LINE_BYTES)
        match = re.search(rb"\(\|\|\|(\d{1,5})\|\)", line)
        if match is None:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.FTP_PASSIVE_BOUNCE,
                "FTPS passive response отклонён.",
            )
        port = int(match.group(1))
        validate_ftp_passive_endpoint(pinned_address, port, (pinned_address,))
        data_reader, data_writer = await asyncio.open_connection(
            pinned_address,
            port,
            ssl=self._context if use_tls else None,
            server_hostname=target.hostname if use_tls else None,
        )
        try:
            await _ftp_command(reader, writer, command, {125, 150}, self.MAX_LINE_BYTES)
            payload = await data_reader.read(maximum + 1)
            if len(payload) > maximum:
                raise ManualProbeTransportError(
                    ManualProbeTransportReason.RESPONSE_TOO_LARGE,
                    "FTPS payload превышает безопасный лимит.",
                )
        finally:
            data_writer.close()
            await data_writer.wait_closed()
        await _ftp_expect(reader, {226, 250}, self.MAX_LINE_BYTES)
        return payload, pinned_address, port


class ManualProviderProbeTransport:
    """One-shot bounded orchestration over pinned, injected I/O ports.

    The exposed surface contains only HTTP GET and passive FTP listing/sample
    reads.  It cannot express upload, delete, rename, recursion or active mode.
    """

    MAX_HTTP_BODY_BYTES = 1_048_576
    MAX_FTP_SAMPLE_BYTES = 1_048_576
    MAX_FTP_ENTRIES = 100

    def __init__(
        self,
        *,
        resolver: ManualProbeResolver,
        http: ManualHttpProbePort | None = None,
        ftp: ManualFtpProbePort | None = None,
        policy: ManualProbeTargetPolicy | None = None,
    ) -> None:
        self._resolver = resolver
        self._http = http
        self._ftp = ftp
        self._policy = policy or ManualProbeTargetPolicy()

    async def probe_http(
        self,
        endpoint: str,
        family: ManualProviderProtocolFamily,
        payload_format: ManualProviderPayloadFormat,
        cancellation_token: CollectorCancellationToken,
        credentials: ManualProbeCredentials | None = None,
    ) -> bytes:
        if family not in {ManualProviderProtocolFamily.API, ManualProviderProtocolFamily.RSS}:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.TARGET_BLOCKED, "Протокол проверки не поддерживается."
            )
        if self._http is None:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.TARGET_BLOCKED, "HTTP transport не настроен."
            )
        cancellation_token.throw_if_cancelled()
        target = self._policy.validate_endpoint(endpoint, family)
        answers = await _cancelable(self._resolver.resolve(target.hostname), cancellation_token)
        resolved = self._policy.validate_resolved_addresses(target, answers)
        cancellation_token.throw_if_cancelled()
        response = await _cancelable(
            self._http.get(
                target,
                resolved.addresses[0],
                cancellation_token,
                credentials or ManualProbeCredentials(),
            ),
            cancellation_token,
        )
        cancellation_token.throw_if_cancelled()
        return validate_http_probe_response(
            response,
            payload_format,
            max_body_bytes=self.MAX_HTTP_BODY_BYTES,
        )

    async def probe_ftp(
        self,
        endpoint: str,
        family: ManualProviderProtocolFamily,
        suffix: str,
        cancellation_token: CollectorCancellationToken,
        *,
        ftps_mode: ManualProviderFtpsMode | None = None,
        credentials: ManualProbeCredentials | None = None,
    ) -> bytes:
        if family not in {ManualProviderProtocolFamily.FTP, ManualProviderProtocolFamily.FTPS}:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.TARGET_BLOCKED, "Протокол проверки не поддерживается."
            )
        if self._ftp is None:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.TARGET_BLOCKED, "FTP transport не настроен."
            )
        selected_credentials = credentials or ManualProbeCredentials()
        if family is ManualProviderProtocolFamily.FTP and (
            selected_credentials.username is not None or selected_credentials.password is not None
        ):
            raise ManualProbeTransportError(
                ManualProbeTransportReason.TARGET_BLOCKED,
                "Credentials запрещены для plaintext FTP probe.",
            )
        cancellation_token.throw_if_cancelled()
        target = self._policy.validate_endpoint(endpoint, family, ftps_mode=ftps_mode)
        answers = await _cancelable(self._resolver.resolve(target.hostname), cancellation_token)
        resolved = self._policy.validate_resolved_addresses(target, answers)
        cancellation_token.throw_if_cancelled()
        response = await _cancelable(
            self._ftp.read_sample(
                target,
                resolved.addresses[0],
                suffix,
                ftps_mode,
                cancellation_token,
                selected_credentials,
            ),
            cancellation_token,
        )
        validate_ftp_passive_endpoint(
            response.passive_address,
            response.passive_port,
            resolved.addresses,
        )
        selected = select_ftp_sample(
            response.names,
            suffix,
            max_entries=self.MAX_FTP_ENTRIES,
        )
        if selected != response.sample_name or len(response.sample) > self.MAX_FTP_SAMPLE_BYTES:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.RESPONSE_TOO_LARGE,
                "FTP sample отклонён безопасной проверкой.",
            )
        cancellation_token.throw_if_cancelled()
        return bytes(response.sample)


def validate_http_probe_response(
    response: ManualProbeResponse,
    payload_format: ManualProviderPayloadFormat,
    *,
    max_body_bytes: int = 1_048_576,
) -> bytes:
    if response.status_code != 200:
        raise ManualProbeTransportError(
            ManualProbeTransportReason.RESPONSE_STATUS, "Источник вернул неподдерживаемый статус."
        )
    if max_body_bytes < 1 or len(response.body) > max_body_bytes:
        raise ManualProbeTransportError(
            ManualProbeTransportReason.RESPONSE_TOO_LARGE, "Ответ источника превышает лимит."
        )
    media_type = response.content_type.partition(";")[0].strip().casefold()
    allowed = {
        ManualProviderPayloadFormat.JSON: {"application/json", "application/problem+json"},
        ManualProviderPayloadFormat.XML: {"application/xml", "text/xml"},
        ManualProviderPayloadFormat.RSS: {"application/rss+xml", "application/xml", "text/xml"},
        ManualProviderPayloadFormat.ATOM: {"application/atom+xml", "application/xml", "text/xml"},
    }[payload_format]
    if media_type not in allowed:
        raise ManualProbeTransportError(
            ManualProbeTransportReason.RESPONSE_TYPE, "Тип ответа не соответствует настройке."
        )
    return bytes(response.body)


def select_ftp_sample(
    names: tuple[str, ...],
    suffix: str,
    *,
    max_entries: int = 100,
) -> str:
    if len(names) > max_entries:
        raise ManualProbeTransportError(
            ManualProbeTransportReason.FTP_LISTING_TOO_LARGE,
            "FTP listing превышает безопасный лимит.",
        )
    normalized_suffix = suffix.casefold()
    for name in names:
        if (
            isinstance(name, str)
            and name
            and "/" not in name
            and "\\" not in name
            and name not in {".", ".."}
            and name.casefold().endswith(normalized_suffix)
        ):
            return name
    raise ManualProbeTransportError(
        ManualProbeTransportReason.FTP_SAMPLE_MISSING, "Подходящий FTP sample не найден."
    )


def validate_ftp_passive_endpoint(
    address: str,
    port: int,
    allowed_addresses: tuple[str, ...],
) -> tuple[str, int]:
    try:
        candidate = ipaddress.ip_address(address)
        allowed = {ipaddress.ip_address(item).compressed for item in allowed_addresses}
    except ValueError:
        raise ManualProbeTransportError(
            ManualProbeTransportReason.FTP_PASSIVE_BOUNCE,
            "FTP passive endpoint отклонён.",
        ) from None
    if (
        not _allowed_address(candidate)
        or candidate.compressed not in allowed
        or not 1024 <= port <= 65535
    ):
        raise ManualProbeTransportError(
            ManualProbeTransportReason.FTP_PASSIVE_BOUNCE, "FTP passive endpoint отклонён."
        )
    return candidate.compressed, port


def _parse_http_headers(raw: bytes) -> tuple[int, str, bool]:
    lines = raw.split(b"\r\n")
    if not lines or len(lines[0].split()) < 2:
        raise ManualProbeTransportError(
            ManualProbeTransportReason.RESPONSE_STATUS, "HTTP status отклонён."
        )
    try:
        status = int(lines[0].split()[1])
    except (ValueError, IndexError):
        raise ManualProbeTransportError(
            ManualProbeTransportReason.RESPONSE_STATUS, "HTTP status отклонён."
        ) from None
    headers: dict[str, str] = {}
    for raw_line in lines[1:]:
        if not raw_line:
            continue
        name, separator, value = raw_line.partition(b":")
        if not separator:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.RESPONSE_STATUS, "HTTP headers отклонены."
            )
        try:
            headers[name.decode("ascii").strip().casefold()] = value.decode("ascii").strip()
        except UnicodeDecodeError:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.RESPONSE_STATUS, "HTTP headers отклонены."
            ) from None
    return (
        status,
        headers.get("content-type", "application/octet-stream"),
        headers.get("transfer-encoding", "").casefold() == "chunked",
    )


def _decode_chunked(payload: bytes, maximum: int) -> bytes:
    result = bytearray()
    cursor = 0
    while True:
        end = payload.find(b"\r\n", cursor)
        if end < 0:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.RESPONSE_STATUS, "Chunked response отклонён."
            )
        raw_size = payload[cursor:end].partition(b";")[0]
        try:
            size = int(raw_size, 16)
        except ValueError:
            raise ManualProbeTransportError(
                ManualProbeTransportReason.RESPONSE_STATUS, "Chunked response отклонён."
            ) from None
        cursor = end + 2
        if size == 0:
            return bytes(result)
        if size < 0 or cursor + size + 2 > len(payload):
            raise ManualProbeTransportError(
                ManualProbeTransportReason.RESPONSE_STATUS, "Chunked response отклонён."
            )
        result.extend(payload[cursor : cursor + size])
        if len(result) > maximum or payload[cursor + size : cursor + size + 2] != b"\r\n":
            raise ManualProbeTransportError(
                ManualProbeTransportReason.RESPONSE_TOO_LARGE,
                "Chunked response превышает безопасный лимит.",
            )
        cursor += size + 2


async def _ftp_expect(
    reader: asyncio.StreamReader,
    accepted: set[int],
    maximum: int,
) -> tuple[int, bytes]:
    line = await reader.readline()
    if not line or len(line) > maximum or len(line) < 3 or not line[:3].isdigit():
        raise ManualProbeTransportError(
            ManualProbeTransportReason.RESPONSE_STATUS, "FTPS response отклонён."
        )
    code = int(line[:3])
    if len(line) > 3 and line[3:4] == b"-":
        terminator = line[:3] + b" "
        for _ in range(50):
            continuation = await reader.readline()
            if not continuation or len(continuation) > maximum:
                break
            line = continuation
            if continuation.startswith(terminator):
                break
    if code not in accepted:
        raise ManualProbeTransportError(
            ManualProbeTransportReason.RESPONSE_STATUS, "FTPS command отклонён."
        )
    return code, line


async def _ftp_command(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    command: str,
    accepted: set[int],
    maximum: int,
) -> int:
    writer.write(command.encode("utf-8") + b"\r\n")
    await writer.drain()
    code, _ = await _ftp_expect(reader, accepted, maximum)
    return code


_T = TypeVar("_T")


async def _cancelable(
    operation: Awaitable[_T],
    cancellation_token: CollectorCancellationToken,
) -> _T:
    task = asyncio.ensure_future(operation)
    cancelled = asyncio.create_task(cancellation_token.wait_cancelled())
    try:
        done, _ = await asyncio.wait({task, cancelled}, return_when=asyncio.FIRST_COMPLETED)
        if cancelled in done:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            cancellation_token.throw_if_cancelled()
        return await task
    finally:
        cancelled.cancel()
        with suppress(asyncio.CancelledError):
            await cancelled


def _allowed_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped.is_global
    return address.is_global


__all__ = [
    "ManualProbeResponse",
    "ManualProbeCredentials",
    "ManualFtpProbePort",
    "ManualFtpProbeResponse",
    "ManualHttpProbePort",
    "ManualProbeResolver",
    "ManualProbeTarget",
    "ManualProbeTargetPolicy",
    "ManualProbeTransportError",
    "ManualProbeTransportReason",
    "ManualTargetPolicyError",
    "ManualProviderProbeTransport",
    "PinnedFtpsProbePort",
    "PinnedHttpsProbePort",
    "ResolvedManualProbeTarget",
    "SystemManualProbeResolver",
    "select_ftp_sample",
    "validate_ftp_passive_endpoint",
    "validate_http_probe_response",
]
